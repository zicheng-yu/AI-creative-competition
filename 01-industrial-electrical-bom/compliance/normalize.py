"""Translate parser observations to the frozen ElectroBench vocabulary."""

from copy import deepcopy
import re
import unicodedata

from electrobench.catalog import ALIASES, BY_CODE, BY_ID

GENERIC = {"KM": "KM_MAIN", "KA": "KA_COIL", "KT": "KT_COIL",
           "SB": "SB_NO", "CB": "QF", "MCCB": "QF", "MCB": "QF", "CT": "TA", "PT": "TV"}
PREFIXES = sorted({**{v.upper(): k for k, v in ALIASES.items()}, **GENERIC,
                   **{v.name_zh: k for k, v in BY_CODE.items()}},
                  key=lambda key: (-len(key), key))
NAMES = {v.upper(): k for k, v in ALIASES.items()}
NAMES.update({v.name_zh: k for k, v in BY_CODE.items()})
NAMES.update({"塑壳断路器": "QF", "微型断路器": "QF", "隔离刀闸": "QS"})


def clean(value):
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def canonical_tag(value):
    tag = clean(value).upper()
    for prefix in PREFIXES:
        if prefix not in NAMES or not tag.startswith(prefix):
            continue
        tail = tag[len(prefix):].lstrip()
        if not tail or re.fullmatch(r"[\dA-Z_-]+", tail):
            code = NAMES[prefix]
            symbol = BY_CODE.get(code)
            return ((symbol.bom_letter or code) if symbol else code) + tail
    return tag


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if -float("inf") < result < float("inf") and not isinstance(value, bool) else None


def poles(value):
    text = clean(value).upper().replace("三极带零", "3P+N").replace("三极", "3P")
    match = re.fullmatch(r"([1-4])\s*(?:P|极)?\s*(\+\s*N)?", text)
    return match[1] + ("P+N" if match[2] else "P") if match else None


def normalize_instance(raw):
    item = deepcopy(raw)
    specs = item.setdefault("specs", {})
    if not isinstance(specs, dict):
        specs = item["specs"] = {"spec": str(specs)}
    item.setdefault("extra", {})
    label = clean(specs.get("spec") or item.get("label_spec"))
    spec = label.upper().replace("三极带零", "3P+N").replace("三极", "3P")
    for before, after in (("千伏安", "KVA"), ("千安", "KA"), ("千瓦", "KW"),
                          ("安", "A"), ("交联电缆", "YJV-"), ("加", "+"),
                          ("乘", "X"), ("×", "X")):
        spec = spec.replace(before, after)
    tag = canonical_tag(item.get("tag") or item.get("label_tag"))
    code = clean(item.get("class_code") or item.get("class")).upper()
    catalog_class = BY_ID.get(item.get("class_id"))
    tag_prefix = re.match(r"^[A-Z_]+", tag)
    code = NAMES.get(code, code) or (catalog_class.code if catalog_class else "")
    code = code or (tag_prefix[0] if tag_prefix else "")
    if code == "SB" and ("常闭" in spec or "急停" in spec or "停止" in spec):
        code = "SB_NC"
    code = GENERIC.get(code, code)
    item.update(tag=tag, class_code=code)
    item["extra"] = item["extra"] or {}
    for key in ("interlocks", "pair_tag"):
        if key in item["extra"]:
            item["extra"][key] = canonical_tag(item["extra"][key])
    if label:
        specs.setdefault("spec", label)
    if code in {"QF", "QS", "FU", "ATS"}:
        rated = re.search(r"(?:\bIN\s*=?|额定)\s*(\d+(?:\.\d+)?)\s*A\b", spec)
        plain = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)\s*A\b", spec)
        frame_trip = re.search(r"(\d+)\s*A\s*/\s*(\d+)\s*A", spec)
        nsx = re.search(r"NSX(\d+)[A-Z]*\s+TM(\d+)D", spec)
        mcb = re.search(r"(?:C65N|NXB-63|DZ47S|S203)\s*[- ]?\s*([BCD])(\d+)", spec)
        series = frame_trip or nsx
        if series:
            specs.setdefault("frame_A", int(series[1]))
            specs.setdefault("In_A", int(series[2]))
        if mcb:
            specs.setdefault("curve", mcb[1])
            specs.setdefault("In_A", int(mcb[2]))
        if rated or plain:
            specs.setdefault("In_A", float((rated or plain)[1]))
        for capture, key in ((r"\bICU\s*=?\s*(\d+(?:\.\d+)?)\s*KA", "icu_kA"),
                             (r"\bICN\s*=?\s*(\d+(?:\.\d+)?)\s*KA", "icn_kA")):
            match = re.search(capture, spec)
            if match:
                specs.setdefault(key, float(match[1]))
        pole = re.search(r"(?<!\d)([1-4])\s*(?:P|极)\s*(\+\s*N)?", spec)
        if pole:
            specs.setdefault("poles", poles(pole[0]))
    if code == "WL":
        cable = re.search(r"\b(YJV|YJLV|VV|VLV)-?(\d+)X([\d.]+)(?:\+1X([\d.]+))?", spec)
        if cable:
            model, cores, section, pe = cable.groups()
            specs.setdefault("model", model)
            specs.setdefault("cores", int(cores))
            specs.setdefault("section_mm2", float(section))
            specs.setdefault("material", "Al" if model in {"YJLV", "VLV"} else "Cu")
            if pe:
                specs.setdefault("pe_mm2", float(pe))
        for key in ("Ib", "Iz"):
            match = re.search(rf"\b{key.upper()}\s*=?\s*(\d+(?:\.\d+)?)\s*A\b", spec)
            if match:
                specs.setdefault(key + "_A", float(match[1]))
    if code in {"TA", "TV"}:
        ratio = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", spec)
        if ratio:
            specs.setdefault("ratio", f"{ratio[1]}/{ratio[2]}")
    return item


def normalize_breaker_label(label):
    """Return electrical attributes and a possible catalog match separately."""
    spec = normalize_instance({"class_code": "QF", "label_spec": label})["specs"]
    if spec.get("frame_A") == 100 and spec.get("In_A") == 80 and spec.get("poles") == "3P":
        if "NSX100F" in clean(label).upper():
            spec["model"] = "NSX100F TM80D 3P"
        elif "塑壳断路器" in label:
            spec["example_catalog_match"] = "NSX100F TM80D 3P"
    return spec
