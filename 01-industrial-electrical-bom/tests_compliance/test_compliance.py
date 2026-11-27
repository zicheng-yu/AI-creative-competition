import json
from pathlib import Path

import networkx as nx
import pytest

from compliance.engine import RULES, evaluate
from compliance.explainer import BaseComplianceLLM, DeterministicRAGExplainer
from compliance.kg import build_kg, cable_table, export_kg, records, select_breakers, select_cable
from compliance.normalize import canonical_tag, normalize_breaker_label
from compliance.repairs import apply_fix
from compliance.run_eval import _behavior, _parser_view, run
from electrobench.ampacity import AMPACITY_TABLE
from electrobench.catalog import ALIASES, CLASSES

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
IDS = sorted(p.parent.name for p in SAMPLES.glob("*/*/annotations.json"))


def sample(drawing_id):
    return json.loads(next(SAMPLES.glob(f"*/{drawing_id}/annotations.json")).read_text(encoding="utf-8"))


def findings(report, rule_id, severity=None):
    return [f for f in report["findings"] if f["rule_id"] == rule_id
            and (severity is None or f["severity"] == severity)]


def edge(source, target, kind="power", **attributes):
    return dict(source=source, target=target, kind=kind, **attributes)


def item(node, code, tag=None, *, extra=None, **specs):
    return dict(id=node, class_code=code, tag=node if tag is None else tag,
                specs=specs, extra=extra or {}, bbox_px=[8, 8, 8, 8], bbox_mm=[2, 96, 2, 2])


def diagram(items, edges, **attributes):
    return dict(instances=items, netlist={"edges": edges},
                sheet={"height_mm": 100, "width_mm": 100, "px_per_mm": 4}, **attributes)


@pytest.mark.parametrize("drawing_id", IDS)
def test_frozen_findings_and_coordinate_roundtrip(drawing_id):
    data = sample(drawing_id)
    report = evaluate(data)
    location = {i["id"]: i for i in data["instances"]}
    predicted = [f for f in report["findings"] if f["severity"] == "error"]
    assert [(f["rule_id"], f["instance_ids"]) for f in predicted] == [
        (f["rule_id"], f["instance_ids"]) for f in data["defects"]]
    for finding in predicted:
        for loc in finding["locations"]:
            for key in ("bbox_px", "bbox_mm"):
                assert loc[key] == location[loc["instance_id"]][key]
        assert finding["standard_refs"] and finding["evidence"] and finding["fix_suggestion"]["operations"]
    parsed = _parser_view(data)
    parsed["defects"] = [{"rule_id": "fake"}]
    assert _behavior(evaluate(parsed), only_red=True) == _behavior(report, only_red=True)


@pytest.mark.parametrize("drawing_id", [i for i in IDS if i.startswith("EBJS-D-")])
def test_apply_all_repairs_and_recheck(drawing_id):
    data = sample(drawing_id)
    fixed = data
    for finding in evaluate(data)["findings"]:
        if finding["severity"] == "error":
            fixed = apply_fix(fixed, finding["fix_suggestion"])
    report = evaluate(fixed)
    assert report["counts"]["error"] == 0
    assert not findings(report, "bom_detail_anchor_mismatch", "warning")
    assert not findings(report, "bom_summary_quantity_mismatch", "warning")
    assert evaluate(data)["counts"]["error"] == len(data["defects"])


def test_interlock_bypass_cannot_be_hidden_by_series_hint():
    data = sample("EBJS-S-FREV-002")
    data["netlist"]["edges"].append(edge("i011", "i017", "control"))
    report = evaluate(data)
    bad = findings(report, "interlock_missing", "error")
    assert len(bad) == 1
    assert bad[0]["evidence"]["coil_tag"] == "KMF"
    assert "i015" not in bad[0]["evidence"]["bypass_path"]
    assert not findings(evaluate(apply_fix(data, bad[0]["fix_suggestion"])), "interlock_missing", "error")


def test_branch_only_fallback_preserves_interlock():
    data = sample("EBJS-S-FREV-002")
    data["netlist"]["edges"] = [e for e in data["netlist"]["edges"] if e["kind"] != "control"]
    assert len(findings(evaluate(data), "interlock_missing", "pass")) == 2


def test_parallel_motor_feed_without_protection():
    data = diagram([item("f", "QF", In_A=32), item("k", "KM_MAIN"), item("r", "FR"),
                    item("m", "M"), item("bus", "WB")],
                   [edge("f", "k"), edge("k", "r"), edge("r", "m"), edge("bus", "m")])
    result = findings(evaluate(data), "motor_protection_missing", "error")[0]
    assert set(result["evidence"]["missing"]) == {"overload_FR", "short_circuit_QF_or_FU", "control_KM"}


def test_ampacity_full_inequality_and_smallest_section():
    data = diagram([item("QF1", "QF", In_A=70, poles="3P", model="breaker"),
                    item("WL1", "WL", spec="YJV-4x16", Ib_A=60, Iz_A=66)],
                   [edge("QF1", "WL1")])
    bad = findings(evaluate(data), "ampacity_insufficient", "error")[0]
    fixed = apply_fix(data, bad["fix_suggestion"])
    assert fixed["instances"][1]["specs"]["spec"] == "YJV-4x25"
    assert not findings(evaluate(fixed), "ampacity_insufficient", "error")
    with pytest.raises(ValueError, match="stale"):
        apply_fix(fixed, bad["fix_suggestion"])
    data["instances"][1]["specs"].update(Iz_A=87, Ib_A=71)
    assert findings(evaluate(data), "ampacity_insufficient", "error")[0]["fix_suggestion"]["operations"] == []


def test_rule_registry_filters_and_numerical_edges():
    data = diagram([item("QF1", "QF", In_A=80, frame_A=63, icu_kA=6, Ik_kA=7, poles="3P"),
                    item("QF2", "QF", In_A=60, icu_kA=10, poles="3P"),
                    item("WL1", "WL", spec="YJV-4x16+1x4", Ib_A=50, Iz_A=65, neutral_mm2=10,
                         mechanical_min_mm2=20, let_through_A2s=1e8, adiabatic_k=100)],
                   [edge("QF1", "QF2"), edge("QF2", "WL1")])
    report = evaluate(data)
    expected = {"breaker_frame_overload", "breaker_short_circuit_rating", "breaking_coordination_review",
                "selectivity_margin_low", "ampacity_margin_low", "cable_ampacity_table_mismatch",
                "cable_mechanical_minimum", "cable_neutral_section", "cable_pe_section",
                "cable_short_circuit_thermal"}
    assert len(RULES) >= 40
    assert expected <= {f["rule_id"] for f in report["findings"] if f["severity"] != "pass"}
    for rid in expected:
        filtered = evaluate(data, enabled_rules=expected, disabled_rules={rid})
        assert {f["rule_id"] for f in filtered["findings"]} == expected - {rid}
    with pytest.raises(ValueError, match="unknown rules"):
        evaluate(data, enabled_rules={"typo"})


def test_ats_kyn_and_bom_scopes():
    data = sample("EBJS-S-ATS-003")
    data["instances"][2]["extra"]["mechanical_interlock"] = True
    data["netlist"]["edges"] = [e for e in data["netlist"]["edges"]
                                if (e["source"], e["target"]) not in {("i012", "i013"), ("i002", "i003")}]
    data["bom_summary"][0]["qty"] = 20
    result = evaluate(data)
    assert findings(result, "ats_mechanical_interlock", "pass")
    assert findings(result, "ats_transfer_delay", "warning")
    assert findings(result, "ats_source_count", "warning")
    stale = findings(result, "bom_summary_quantity_mismatch", "warning")[0]
    assert not findings(evaluate(apply_fix(data, stale["fix_suggestion"])), stale["rule_id"], "warning")
    mv = evaluate(sample("EBJS-P-KYN-004"))
    assert len(findings(mv, "kyn_vacuum_breaker", "pass")) == 3
    assert len(findings(mv, "kyn_five_preventions", "warning")[0]["evidence"]["missing_or_unverified"]) == 5


def test_terminal_and_wire_identification():
    terminal = item("x", "XT", "XT1", model="EB-XT")
    terminal["ports"] = {"in": [0, 0]}
    data = diagram([item("f", "FU", "FU1", In_A=1), terminal],
                   [edge("f", "x", "control", target_port="out", source_wire_no="101", target_wire_no="102")])
    assert findings(evaluate(data), "control_terminal_missing", "warning")
    assert findings(evaluate(data), "control_wire_number_mismatch", "warning")


def test_knowledge_graph_and_catalog_queries():
    graph = build_kg()
    assert {node["layer"] for _, node in graph.nodes(data=True)} == {1, 2, 3}
    assert {a["class_id"] for _, a in graph.nodes(data=True) if a["type"] == "symbol"} == set(range(40))
    for symbol in CLASSES:
        node = f"symbol:{symbol.code}"
        assert graph.nodes[node]["iec81346"] == symbol.iec81346
        assert any(target.startswith("clause:GB/T 4728") for target in graph.successors(node))
    for rule in RULES.values():
        assert set(graph.successors(f"rule:{rule.id}")) == {f"clause:{ref}" for ref in rule.refs}
        assert all(graph.nodes[f"clause:{ref}"]["type"] == "clause" for ref in rule.refs)
    assert nx.has_path(graph, "alias:空开", "clause:GB 50054-2011 6.1.2")
    subgraph = export_kg(graph, ["alias:空开"], hops=2)
    assert "clause:GB 50054-2011 6.1.2" in {n["id"] for n in subgraph["nodes"]}
    assert cable_table("Cu") == dict(AMPACITY_TABLE)
    assert select_cable(55, 70)["section_mm2"] == 25
    assert select_cable(55, 70, "铝")["section_mm2"] == 35
    assert select_cable(80, 70) is None
    selection = select_breakers(min_current=1.6 * 50, max_current=100, poles_required="3P",
                               voltage=400, minimum_breaking=36)
    assert selection and all(p["In_A"] == 80 for p in selection)
    assert not select_breakers(min_current=32, voltage=400, minimum_breaking=6, device_type="MCB")
    assert len(records("clauses")) >= 20


def test_alias_and_breaker_normalization():
    for prefix, alias in ALIASES.items():
        assert canonical_tag(alias + "1") == prefix + "1"
    alias = normalize_breaker_label("塑壳断路器 100A/80A 3极")
    canonical = normalize_breaker_label("NSX100F TM80D 3P")
    assert alias["example_catalog_match"] == canonical["model"]
    assert all(alias[name] == canonical[name] for name in ("poles", "In_A", "frame_A"))


@pytest.mark.parametrize(("question", "clause"), [
    ("QF2 级差倒挂怎么解决", "GB 50054-2011 6.1.2"),
    ("GB 50054 6.3.3 载流量", "GB 50054-2011 6.3.3"),
    ("正反转 KM_NC 如何互锁", "GB/T 5226.1-2019 9.3"),
    ("急停优先", "GB/T 5226.1-2019 9.2"),
    ("GB/T 5094 项目分类码", "GB/T 5094.2-2018"),
    ("KYN28 五防闭锁", "GB 50060-2008 2.0.10"),
    ("ATS 延时", "IEC 60947-6-1:2026"),
    ("GB 50055 电机短路保护", "GB 50055-2011 2.3.1"),
])
def test_rag_top_one(question, clause):
    response = DeterministicRAGExplainer().answer(question)
    assert response["clause_ids"][0] == clause
    assert response["clauses"][0]["source_url"].startswith("https://")


def test_finding_qa_and_brand_swap_preview():
    explainer = DeterministicRAGExplainer()
    assert isinstance(explainer, BaseComplianceLLM)
    response = explainer.answer("查一下 QF2 为什么报级差错误，国标怎么规定的？",
                                drawing=sample("EBJS-D-SEL-001"))
    assert response["findings"][0]["rule_id"] == "selectivity_inversion"
    assert "GB 50054-2011 6.1.2" in response["clause_ids"]
    data = diagram([item("QF1", "QF", model="C65N", spec="C65N C32 3P",
                         voltage_V=400, icn_kA=6)], [])
    replace = explainer.answer("把 C65N 32A 换成正泰对应型号并复检合规性", drawing=data)
    assert replace["recheck"]["counts"]["error"] == 0
    assert replace["candidates"][0]["model"] == "NXB-63 C32 3P"
    assert data["instances"][0]["specs"]["model"] == "C65N"


def test_evaluation_export_is_deterministic(tmp_path):
    out1, out2 = tmp_path / "first", tmp_path / "second"
    summary = run(SAMPLES, out1, out1)
    assert summary["totals"] == {"tp": 5, "fp": 0, "fn": 0, "precision": 1,
                                  "recall": 1, "conforming_errors": 0}
    assert run(SAMPLES, out2, out2) == summary
    assert len(summary["degradation_checks"]) == 3
    for file in ("eval_report.md", "eval_summary.json", "compliance_reports.json", "electrical_kg.json"):
        assert (out1 / file).read_bytes() == (out2 / file).read_bytes()
    frontend = json.loads((out1 / "compliance_reports.json").read_bytes())
    assert sorted(frontend["reports"]) == IDS
    for report in frontend["reports"].values():
        for finding in report["findings"]:
            if finding["severity"] != "pass":
                assert set(finding["rag"]["clause_ids"]) <= set(frontend["clauses"])


def test_additional_nameplate_measurement_and_wiring_evidence():
    data = diagram(
        [
            item("f", "QF", In_A=32, I2_A=60, icu_kA=6, Ik_kA=8, frame_A=63),
            item("k", "KM_MAIN", Ie_A=15), item("fr", "FR", Ir_A=10), item("m", "M", In_A=20),
            item("w", "WL", Ib_A=20, Iz_A=36, section_mm2=6, mechanical_min_mm2=10,
                 let_through_A2s=5000, adiabatic_k=10),
            item("a", "TA", ratio="100/5", load_A=30), item("v", "TV", ratio="380/100", circuit_V=10000),
            item("stop", "SB_NC", extra={"role": "emergency_stop"}), item("coil", "KM_COIL"),
            item("fu", "FU", In_A=2),
        ],
        [edge("f", "k"), edge("k", "fr"), edge("fr", "m"), edge("f", "w"),
         edge("fu", "stop", "control"), edge("stop", "coil", "control"),
         edge("fu", "coil", "control", source_wire_no="10", target_wire_no="11"),
         edge("coil", "missing", "control")],
    )
    expected = {
        "breaker_short_circuit_rating", "cable_mechanical_minimum", "cable_conventional_trip_current",
        "cable_short_circuit_thermal", "motor_contactor_rating", "motor_overload_setting", "ct_ratio_load",
        "vt_ratio_voltage", "control_emergency_stop_priority", "control_wire_number_mismatch",
        "netlist_dangling_edge",
    }
    report = evaluate(data, enabled_rules=expected)
    assert not report["not_evaluated_rule_ids"]
    assert {f["rule_id"] for f in report["findings"] if f["severity"] != "pass"} == expected
