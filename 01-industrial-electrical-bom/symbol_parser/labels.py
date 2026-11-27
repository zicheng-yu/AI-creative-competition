"""Text normalization and one-to-one spatial tag/specification assignment."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from math import hypot
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

Point = tuple[float, float]
Box = tuple[float, float, float, float]

CATALOG = json.loads(
    Path(__file__).with_name("electrobench-catalog.json").read_text(encoding="utf-8")
)
CLASSES = CATALOG["classes"]
_ALIASES = CATALOG["aliases"]
_PREFIXES = set(_ALIASES) | {"PE", "WIRE_NO"}
_PREFIX_PATTERN = "|".join(
    re.escape(p)
    for p in sorted(_PREFIXES | set(_ALIASES.values()), key=lambda k: (-len(k), k))
)
_TAG = re.compile(
    rf"^(?P<prefix>{_PREFIX_PATTERN})[\s_\-]*([A-Z]{{0,2}}\d{{1,5}}[A-Z]?|[FR])(?=$|\s)(?:\s+(.+))?$",
    re.IGNORECASE,
)
_CANONICAL_PREFIX = {name.upper(): prefix for prefix, name in _ALIASES.items()}
_REPLACEMENTS = {
    "三极带零": "3P+N",
    "三极": "3P",
    "额定": "In=",
    "千伏安": "kVA",
    "千瓦": "kW",
    "千安": "kA",
    "交联电缆": "YJV-",
    "加": "+",
    "乘": "x",
}
_SPEC_SIGNAL = re.compile(
    r"\d|相|极|启|启停|停止|复位|正转|反转|保护|常开|常闭|联锁|延时|自动|电压|亮|绿|黄|红|故障|合位|分位|合闸|分闸|限流|串联|自投|熔断|触点|回路"
)
_RATINGS = (
    ("In_A", r"(?<![A-Za-z])In\s*=\s*(\d+(?:\.\d+)?)\s*A\b"),
    ("Ie_A", r"(?<![A-Za-z])Ie\s*=\s*(\d+(?:\.\d+)?)\s*A\b"),
    ("Ir_A", r"整定\s*(\d+(?:\.\d+)?)\s*A\b"),
    ("Icu_kA", r"Icu\s*=\s*(\d+(?:\.\d+)?)\s*kA\b"),
    ("kW", r"(\d+(?:\.\d+)?)\s*kW\b"),
    ("poles", r"(?<![\w.])(\d)P(?!\w)"),
)


@dataclass(frozen=True)
class TextMark:
    text: str
    bbox: Box
    confidence: float = 1.0

    @property
    def center(self) -> Point:
        x, y, w, h = self.bbox
        return x + w / 2, y + h / 2


@dataclass
class Component:
    code: str
    box: Box
    ports: dict[str, Point]
    confidence: float
    source: str
    tag: str = ""
    spec: str = ""
    model: str = ""
    bindings: dict[str, TextMark] = field(default_factory=dict)
    refined: bool = False
    # Vector matching consumes already read tags; detector-only components may be untagged.
    label_anchor: TextMark | None = None


def normal_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def split_tag(text: str) -> tuple[str, str, str] | None:
    text = normal_text(text).strip("[](){}|:;")
    text = re.sub(r"(?<=\d)(?=I(?:cu|e|n)=)", " ", text, flags=re.IGNORECASE)
    match = _TAG.fullmatch(text)
    if match is None:
        return None
    prefix = match.group("prefix").upper()
    prefix = _CANONICAL_PREFIX.get(prefix, prefix)
    return prefix, prefix + match.group(2).upper(), match.group(3) or ""


def normalize_spec(text: str) -> str:
    result = normal_text(text)
    for original, replacement in _REPLACEMENTS.items():
        result = result.replace(original, replacement)
    result = re.sub(r"(?<=\d)\s*安\b", "A", result)
    result = re.sub(r"(?<=\d)\s+(?=[AVWk]\b)", "", result)
    result = re.sub(r"\s*=\s*", "=", result)
    result = re.sub(
        r"(\d(?:kVA|kV|VA|kW|kA|V|A))(?=\d|(?:AC|DC)\d|I(?:cu|e|n)=)",
        r"\1 ",
        result,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"(\dP)(?=(?:I(?:cu|e|n)=|(?:AC|DC)\d))", r"\1 ", result, flags=re.IGNORECASE
    )


_SPEC_PATTERNS = {
    "QF": r"In=\d+(?:\.\d+)?A",
    "FU": r"\d+(?:\.\d+)?A",
    "QS": r"\d+(?:\.\d+)?(?:A|kV)",
    "M": r"\d+(?:\.\d+)?kW",
    "TA": r"\d+(?:\.\d+)?A",
    "PA": r"\d+(?:\.\d+)?A",
    "TV": r"\d+(?:\.\d+)?(?:kV|V)",
    "PV": r"\d+(?:\.\d+)?(?:kV|V)",
    "WL": r"YJV[-\w.+]+",
}


def check_rated_spec(code: str, text: str) -> bool:
    pattern = _SPEC_PATTERNS.get(code)
    if not pattern:
        return True
    text = normalize_spec(text)
    if (
        code == "QF"
        and "icu=" in text.casefold()
        and not re.search(r"Icu=\d+(?:\.\d+)?kA", text, re.IGNORECASE)
    ):
        return False
    return bool(re.search(pattern, text, re.IGNORECASE))


def specs(text: str, model: str) -> dict:
    result = {}
    if model:
        result["model"] = model
    if text:
        result["spec"] = normalized = normalize_spec(text)
        for key, pattern in _RATINGS:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                result[key] = int(value) if value.is_integer() else value
    return result


def prefix_of(code: str) -> str:
    return CLASSES[code]["prefix"]


def tag_distance(box: Box, label: TextMark) -> float:
    x, y, w, h = box
    tx, ty, tw, th = label.bbox
    # Tags outside the left/right sides align to the midline. A label above
    # a horizontal component normally starts near the left edge.
    level = ty + th / 2 - (y + h * 0.48)
    left = hypot(abs(x - tx - tw), level * 1.1)
    right = hypot(abs(tx - x - w), level * 1.1)
    above = hypot((tx - x) * 0.8, abs(y - ty - th))
    if ty + th / 2 > y + h * 0.16:
        above += max(w, h) * 0.35
    if tx > x + w * 0.17:
        left += max(w, h) * 0.5
    if tx + tw < x + w * 0.83:
        right += max(w, h) * 0.5
    return min(left, right, above)


def _assign(row_count, column_count, cost, limit):
    if not row_count or not column_count:
        return []
    matrix = np.full((row_count, column_count + row_count), limit)
    for row in range(row_count):
        for col in range(column_count):
            matrix[row, col] = min(cost(row, col), limit * 2)
    rows, columns = linear_sum_assignment(matrix)
    return [
        (r, c)
        for r, c in zip(rows, columns, strict=True)
        if c < column_count and matrix[r, c] < limit
    ]


def bind_labels(components: list[Component], marks: list[TextMark], scale: float):
    tags = [(mark, parsed) for mark in marks if (parsed := split_tag(mark.text))]
    options = [
        component
        for component in components
        if not component.tag and component.code not in {"WIRE_NO", "PE"}
    ]
    consumed = {item.label_anchor for item in components if item.label_anchor}
    tags = [(mark, parsed) for mark, parsed in tags if mark not in consumed]

    def tag_cost(row, col):
        candidate, (mark, (prefix, _tag, _spec)) = options[row], tags[col]
        if prefix != prefix_of(candidate.code):
            return float("inf")
        return tag_distance(candidate.box, mark) / scale + 3 * (1 - mark.confidence)

    for row, col in _assign(len(options), len(tags), tag_cost, 13.5):
        mark, (_, tag, spec) = tags[col]
        component = options[row]
        component.tag = tag
        component.label_anchor = mark
        component.bindings["tag"] = mark
        if spec:
            component.spec = spec
            component.bindings["spec"] = mark

    options = [
        component
        for component in components
        if component.label_anchor and not component.spec
    ]
    values = [
        mark
        for mark in marks
        if not split_tag(mark.text)
        and len(mark.text) <= 100
        and not mark.text.isdecimal()
        and _SPEC_SIGNAL.search(mark.text)
    ]

    def spec_cost(row, col):
        candidate, value = options[row], values[col]
        ax, ay, aw, ah = candidate.label_anchor.bbox
        x, y, w, h = value.bbox
        dy = (y + h / 2) - (ay + ah / 2)
        if not 0 < dy < scale * 8.5:
            return float("inf")
        left_alignment = abs(x - ax)
        right_alignment = abs((x + w) - (ax + aw))
        if ax < candidate.box[0] and x < candidate.box[0]:
            # OCR/font extents may overshoot a right-aligned label, especially
            # when the specification line is much wider than its identifier.
            right_alignment = max(0.0, right_alignment - 0.12 * max(w, aw))
        dx = min(left_alignment, right_alignment)
        return (abs(dy - max(ah, h) * 1.18) * 0.8 + 1.35 * dx) / scale + (
            1 - value.confidence
        ) * 2

    for row, col in _assign(len(options), len(values), spec_cost, 6.5):
        component, mark = options[row], values[col]
        component.spec = normalize_spec(mark.text)
        component.bindings["spec"] = mark
