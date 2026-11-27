"""Offline explanation and structured question answering."""

from abc import ABC, abstractmethod
import re

from .engine import evaluate
from .kg import records, select_breakers
from .normalize import canonical_tag, poles
from .rag import default_index
from .repairs import apply_fix, update_specs
from .topology import Drawing


class BaseComplianceLLM(ABC):
    """TODO(zicheng): plug in LLM provider."""

    @abstractmethod
    def explain_finding(self, finding: dict) -> dict:
        """Return a finding explanation with verified clause references."""

    @abstractmethod
    def answer(self, question: str, *, drawing: dict | None = None) -> dict:
        """Return structured QA, optional proposed patch and preview recheck."""


class DeterministicRAGExplainer(BaseComplianceLLM):
    def __init__(self, index=None):
        self.index = index or default_index()

    def explain_finding(self, finding):
        standard_refs = finding["standard_refs"]
        clauses = self.index.search(finding["message"], rule_id=finding["rule_id"],
                                    standard_refs=standard_refs, limit=max(3, len(standard_refs)))
        tags = "、".join(finding["tags"]) or "图纸"
        verdict = {"error": "红灯", "warning": "黄灯", "pass": "通过"}[finding["severity"]]
        action = finding["fix_suggestion"]["action"]
        text = f"{tags} · {finding['message']} · {verdict}。"
        if action:
            text += action
        return {"answer": text, "clause_ids": [c["clause_id"] for c in clauses],
                "clauses": clauses, "evidence": finding["evidence"],
                "fix_suggestion": finding["fix_suggestion"]}

    def _replacement(self, question, drawing):
        brand = next((p for p in ("正泰", "施耐德", "德力西", "ABB") if p in question.upper()), None)
        if not brand:
            return None
        normalized = question.upper()
        asked_current = re.search(r"(\d+)\s*A\b", normalized)
        asked_current = int(asked_current[1]) if asked_current else None
        series = next((p["series"] for p in records("breakers") if p["series"].upper() in normalized), None)
        found = []
        d = Drawing(drawing) if drawing else None
        if d:
            for node in d.of("QF"):
                model = (d.items[node]["specs"].get("model") or "").upper()
                tagged = bool(re.search(rf"(?<![A-Z0-9]){re.escape(d.tag(node))}(?![A-Z0-9])", normalized))
                if tagged or series and series.upper() in model and (
                    asked_current is None or d.value(node, "In_A") == asked_current
                ):
                    found.append(node)
        refs = self.index.search("替代 断路器 分断", standard_refs=("GB/T 14048.2-2020",), limit=2)
        result = {"intent": "replace_breaker", "clauses": refs,
                  "clause_ids": [c["clause_id"] for c in refs], "candidates": [],
                  "fix_suggestion": None, "recheck": None}
        if len(found) != 1:
            if asked_current:
                result["candidates"] = select_breakers(
                    brand=brand, min_current=asked_current, max_current=asked_current,
                    device_type="MCB" if series in {"C65N", "S200", "DZ47s", "NXB"} else None)
            result["answer"] = "请提供唯一断路器位号和图纸。候选按已知品牌及电流筛选，替换前还需核对极数、电压、分断能力和曲线。"
            return result
        node = found[0]
        specs = d.items[node]["specs"]
        current, voltage = d.value(node, "In_A"), d.value(node, "voltage_V")
        metric = "icu_kA" if d.value(node, "icu_kA") else "icn_kA"
        capacity = d.value(node, metric)
        curve = specs.get("curve")
        if not (current and voltage and capacity and poles(specs.get("poles"))) or (metric == "icn_kA" and not curve):
            result["answer"] = f"{d.tag(node)} 的额定电压、电流、极数、曲线或分断参数有待补全。"
            return result
        required = max(capacity, d.value(node, "Ik_kA") or 0)
        result["candidates"] = select_breakers(brand=brand, min_current=current, max_current=current,
                                               poles_required=specs["poles"], voltage=voltage,
                                               minimum_breaking=required, capacity_field=metric, curve=curve)
        if not result["candidates"]:
            result["answer"] = "离线目录暂时找不到满足已知条件的候选型号。"
            return result
        part = result["candidates"][0]
        fields = {key: part[key] for key in ("model", "In_A", "poles", metric, "frame_A", "curve")}
        ops = [update_specs(d, node, fields | {"spec": part["model"]})]
        fix = {"action": f"预览将 {d.tag(node)} 替换为 {part['model']}。", "operations": ops}
        recheck = evaluate(apply_fix(drawing, fix))
        result.update(fix_suggestion=fix, recheck={"status": recheck["status"], "counts": recheck["counts"],
                                                  "findings": [f for f in recheck["findings"] if
                                                               node in f["instance_ids"] and f["severity"] != "pass"]})
        result["answer"] = fix["action"] + f"复检全图红灯 {recheck['counts']['error']} 条，黄灯 {recheck['counts']['warning']} 条。"
        return result

    def answer(self, question, *, drawing=None):
        if any(token in question for token in ("替换", "更换", "换成")):
            replacement = self._replacement(question, drawing)
            if replacement:
                return replacement
        question_tags = {canonical_tag(tag) for tag in re.findall(r"[A-Za-z\u3400-\u9fff]+[0-9]+", question)}
        question_tags.update(re.findall(r"(?<![A-Z0-9])(?:KMF|KMR)(?![A-Z0-9])", question.upper()))
        findings = []
        if drawing:
            findings = [f for f in evaluate(drawing)["findings"] if f["severity"] != "pass"
                        and question_tags.intersection(f["tags"])]
        families = {"selectivity": ("级差", "倒挂", "选择性"), "ampacity": ("载流量", "截面"),
                    "control": ("互锁", "自锁", "急停")}
        preferred = {family for family, keys in families.items() if any(key in question for key in keys)}
        focused = [f for f in findings if f["family"] in preferred]
        if focused:
            findings = focused
        findings.sort(key=lambda f: (f["severity"] != "error", f["rule_id"], f["instance_ids"]))
        direct = list(dict.fromkeys(ref for finding in findings[:3] for ref in finding["standard_refs"]))
        clauses = self.index.search(question, standard_refs=direct, limit=max(4, len(direct)))
        if findings:
            text = " ".join(self.explain_finding(f)["answer"] for f in findings[:3])
        elif clauses:
            text = clauses[0]["summary"] + " " + clauses[0]["remediation_guide"]
        else:
            text = "本地条文库暂无匹配内容。"
        return {"intent": "explain_finding" if findings else "search_clauses",
                "answer": text, "clause_ids": [c["clause_id"] for c in clauses], "clauses": clauses,
                "findings": findings[:3], "fix_suggestion": findings[0]["fix_suggestion"] if findings else None,
                "recheck": None}
