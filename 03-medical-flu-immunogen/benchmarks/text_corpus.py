"""Explicitly synthetic NLI and relevance labels, with held-out domains and templates."""
from dataclasses import dataclass


DOMAINS = {
    "train": {
        "archive": ("catalog", "folder", "inventory", "manifest", "register", "ledger"),
        "software": ("build", "package", "artifact", "release", "bundle", "module"),
        "library": ("loan", "receipt", "collection", "book", "journal", "issue"),
        "governance": ("approval", "annotation", "revision", "review", "decision", "notice"),
        "transport": ("route", "ticket", "station", "schedule", "vehicle", "platform"),
        "workspace": ("meeting", "agenda", "room", "summary", "policy", "minutes"),
    },
    "validation": {
        "museum": ("label", "exhibit", "gallery", "display", "poster", "tour"),
        "school": ("course", "class", "term", "lecture", "lesson", "exercise"),
    },
    "test": {
        "garden": ("greenhouse", "bench", "walkway", "planter", "sign", "map"),
        "audio": ("recording", "microphone", "transcript", "track", "session", "playlist"),
    },
}
NLI_TEMPLATES = {
    "train": ("The {item} has {n} entries.", "The {item} contains {n} entries.",
              "The {item} does not have {n} entries.", "The {item} was indexed."),
    "validation": ("The {item} lists {n} sections.", "The {item} includes {n} sections.",
                   "The {item} does not list {n} sections.", "The {item} has a label."),
    "test": ("The {item} contains {n} notes.", "The {item} holds {n} notes.",
             "The {item} does not contain {n} notes.", "The {item} was checked."),
}
RANK_TEMPLATES = {
    "train": ("Find the {item} for the {domain} desk.",
              "The {domain} desk keeps the {item} and instructions for checking it.",
              "The {domain} desk plans a delivery. The checklist covers {other}.",
              "Find the ticket for the {domain} desk."),
    "validation": ("Where is the {domain} {item} guidance?",
                   "This guide describes the {item} used by the {domain} staff.",
                   "The {other} was approved by the {domain} staff.",
                   "The city schedule was updated yesterday."),
    "test": ("Which record describes the {item} at the {domain} center?",
             "The {domain} center documents the {item} in the handbook.",
             "The handbook at the {domain} center lists the {other}.",
             "A poster describes office hours."),
}


@dataclass(frozen=True)
class Example:
    left: str
    right: str
    label: int
    group: str


def samples(model: str, split: str) -> list[Example]:
    rows = []
    for domain, items in DOMAINS[split].items():
        for index, item in enumerate(items):
            other = items[(index + 1) % len(items)]
            group = f"synthetic/{split}/{domain}/{item}"
            if model == "reranker":
                query, positive, close, generic = (
                    value.format(item=item, domain=domain, other=other)
                    for value in RANK_TEMPLATES[split]
                )
                distractor = f"The {item} appeared in a list of extra supplies."
                rows.extend(Example(query, text, label, group) for text, label in
                            [(close, 0), (positive, 1), (generic, 0), (distractor, 0)]
                            if text != query)
            else:
                premise, equivalent, negated, incomplete = NLI_TEMPLATES[split]
                for count in (index + 3, index + 13):
                    given = premise.format(item=item, n=count)
                    variants = [
                        (given, 0),
                        (equivalent.format(item=item, n=count), 0),
                        (premise.format(item=item, n=count + 1), 1),
                        (negated.format(item=item, n=count), 1),
                        (equivalent.format(item=other, n=count), 2),
                        (incomplete.format(item=item, n=count), 2),
                    ]
                    rows.extend(Example(given, claim, label, group) for claim, label in variants)
    return rows
