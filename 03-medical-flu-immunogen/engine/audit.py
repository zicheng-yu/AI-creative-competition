"""Audit source quotations using exact, versioned record membership."""
import re
import unicodedata

from .llm_adapter import Citation


BOUNDARY = "本阶段交付软件原型与离线评测，不以实验有效性或临床效果作为承诺。"
INSUFFICIENT = "[证据不足 / 待验证]"
_EFFECT_PROMISE = re.compile(
    r"临床保护率|保证保护|最优疫苗|最佳疫苗|保证疗效|湿实验有效|"
    r"guaranteed?\s+(?:clinical\s+)?(?:efficacy|protection)|best\s+vaccine",
    re.I,
)


def audit(citations: list[Citation], selected) -> tuple[list[dict], dict[str, int]]:
    rejection_counts = {"outside_selection": 0, "nonverbatim": 0, "effect_promise": 0}
    by_key = {record.key: record for record in selected}
    statements = []
    seen = set()
    for citation in citations:
        key = (citation.evidence_id, citation.dataset_version)
        record = by_key.get(key)
        if record is None:
            rejection_counts["outside_selection"] += 1
            continue
        if citation.text != record.raw_snippet:
            rejection_counts["nonverbatim"] += 1
            continue
        text = unicodedata.normalize("NFKC", citation.text)
        if _EFFECT_PROMISE.search(text):
            rejection_counts["effect_promise"] += 1
            continue
        if key in seen:
            continue
        seen.add(key)
        statements.append({
            "statement_id": f"S{len(statements) + 1}",
            "text": record.raw_snippet,
            "evidence_id": record.evidence_id,
            "dataset_version": record.dataset_version,
            "primary_ref": record.primary_ref,
            "evidence_tier": record.evidence_tier,
            "ingested_at": record.ingested_at,
        })
    return statements, rejection_counts
