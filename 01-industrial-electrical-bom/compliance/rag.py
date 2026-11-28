"""Local BM25, character TF-IDF and knowledge graph retrieval."""

from collections import Counter
from functools import lru_cache
from math import log, sqrt
import re

import networkx as nx

from .kg import build_kg, records

TOKEN = re.compile(r"[a-z]+(?:[_/-][a-z0-9]+)*\d*|\d+(?:\.\d+)*|[\u3400-\u9fff]+")
QUERY_HINTS = {
    "级差": ("GB 50054-2011 6.1.2",), "倒挂": ("GB 50054-2011 6.1.2",),
    "选择性": ("GB 50054-2011 6.1.2",), "载流量": ("GB 50054-2011 6.3.3",),
    "截面积": ("GB 50054-2011 6.3.3", "GB 50054-2011 3.2"),
    "热继电器": ("GB/T 5226.1-2019 7.3", "GB/T 14048.4-2020"),
    "互锁": ("GB/T 5226.1-2019 9.3",), "五防": ("GB 50060-2008 2.0.10",),
    "自锁": ("GB/T 5226.1-2019 9.2",), "急停": ("GB/T 5226.1-2019 9.2",),
    "端子号": ("GB/T 5226.1-2019 13",), "替代": ("GB/T 14048.2-2020",),
    "ATS": ("IEC 60947-6-1:2026",), "分断": ("GB/T 14048.2-2020", "GB 50054-2011 6.2"),
}


def _words(text):
    tokens = []
    for word in TOKEN.findall(text.lower()):
        if "\u3400" <= word[0] <= "\u9fff":
            tokens.extend(word)
            tokens.extend(word[i:i+2] for i in range(len(word) - 1))
        else:
            tokens.append(word)
    return tokens


def _ngrams(text):
    value = re.sub(r"[\W_]+", "", text.lower())
    return [value[i:i+n] for n in (2, 3) for i in range(len(value) - n + 1)]


def _idf(documents):
    frequencies = Counter(token for doc in documents for token in doc)
    return {token: log(1 + (len(documents) - n + 0.5) / (n + 0.5))
            for token, n in frequencies.items()}


def _normalize_vector(tokens, idf):
    vector = {word: (1 + log(tf)) * idf[word]
              for word, tf in Counter(tokens).items() if word in idf}
    norm = sqrt(sum(value * value for value in vector.values()))
    return {word: score / norm for word, score in vector.items()} if norm else {}


class ClauseIndex:
    def __init__(self):
        self.clauses = records("clauses")
        self.graph = build_kg()
        self.connected = self.graph.to_undirected()
        documents = [" ".join(str(c.get(k) or "") for k in
                              ("clause_id", "title", "summary", "constraint_formula", "remediation_guide", "excerpt"))
                     + " " + " ".join(c["applicable_classes"]) for c in self.clauses]
        self.words = [Counter(_words(text)) for text in documents]
        self.average_length = sum(d.total() for d in self.words) / len(self.words)
        self.word_idf = _idf(self.words)
        grams = [_ngrams(text) for text in documents]
        self.gram_idf = _idf([set(row) for row in grams])
        self.vectors = [_normalize_vector(row, self.gram_idf) for row in grams]

    def search(self, query, *, rule_id=None, class_codes=(), standard_refs=(), limit=4):
        if limit <= 0:
            return []
        compact = re.sub(r"\s+", "", query.upper())
        query_words = sorted(set(_words(query)))
        vector = _normalize_vector(_ngrams(query), self.gram_idf)
        seeds = {"symbol:" + c for c in class_codes}
        if rule_id:
            seeds.add("rule:" + rule_id)
        for node, attrs in self.graph.nodes(data=True):
            if attrs["type"] == "symbol":
                code = attrs["class_code"]
                if re.search(rf"(?<![A-Z0-9_]){re.escape(code)}(?:\d+)?(?![A-Z0-9_])", query.upper()):
                    seeds.add(node)
            if attrs["type"] == "alias" and len(attrs["label"]) >= 2 and attrs["label"][0] >= "\u3400":
                if attrs["label"] in query:
                    seeds.add(node)
        affinity = Counter()
        for seed in sorted(seeds):
            if seed in self.connected:
                for node, distance in nx.single_source_shortest_path_length(self.connected, seed, cutoff=3).items():
                    if node.startswith("clause:") and distance:
                        affinity[node[7:]] = max(affinity[node[7:]], 1 / distance)
        preferred = {ref for hint, refs in QUERY_HINTS.items() if hint.upper() in query.upper() for ref in refs}
        results = []
        for clause, words, document_vector in zip(self.clauses, self.words, self.vectors):
            cid = clause["clause_id"]
            length_term = 1.5 * (0.25 + 0.75 * words.total() / self.average_length)
            bm25 = sum(self.word_idf.get(word, 0) * (2.5 * words[word]) / (words[word] + length_term)
                       for word in query_words)
            cosine = sum(q * document_vector.get(word, 0) for word, q in vector.items())
            standard = clause["standard_code"].split("-", 1)[0]
            exact_code = re.sub(r"\s+", "", standard).upper()
            exact_base = re.sub(r"\s+", "", re.sub(r"\.\d+$", "", standard)).upper()
            exact = any(re.search(re.escape(code) + r"(?!\d)", compact) for code in (exact_code, exact_base))
            exact_section = exact and clause["section"] and clause["section"] in query
            score = (bm25 / (5 + bm25) + 2 * cosine + 0.45 * affinity[cid]
                     + 1.5 * exact + 2 * bool(exact_section) + 0.85 * (cid in preferred)
                     + 10 * (cid in standard_refs))
            if score > 0:
                results.append(clause | {"score": round(score, 6)})
        return sorted(results, key=lambda hit: (-hit["score"], hit["clause_id"]))[:limit]


@lru_cache(maxsize=1)
def default_index():
    return ClauseIndex()
