import csv
import json
import subprocess
import sys

import ezdxf
import pytest
from openpyxl import load_workbook
from PIL import Image, ImageDraw

from netlist import build_bom, reconstruct


def symbol(node_id, klass, ports, **attributes):
    return {
        "id": node_id,
        "class_code": klass,
        "tag": node_id,
        "ports": ports,
        **attributes,
    }


def endpoints(netlist):
    return {frozenset((edge["source"], edge["target"])) for edge in netlist["edges"]}


def pair(a, b):
    return frozenset((a, b))


@pytest.mark.parametrize("with_dot", [False, True])
def test_crossing_requires_dot_even_when_lines_are_split(with_dot):
    sheet = {
        "id": "cross",
        "symbols": [
            symbol("W", "QF", {"out": (0, 5)}),
            symbol("E", "M", {"in": (10, 5)}),
            symbol("N", "QF", {"out": (5, 10)}),
            symbol("S", "M", {"in": (5, 0)}),
        ],
        "wires": [
            ((0, 5), (6, 5)),
            ((5, 5), (10, 5)),
            ((5, 0), (5, 5)),
            ((5, 5), (5, 10)),
        ],
        "junctions": [(5, 5)] if with_dot else [],
    }
    connections = endpoints(reconstruct({"sheets": [sheet]}))
    assert {pair("W", "E"), pair("N", "S")} <= connections
    assert len(connections) == (6 if with_dot else 2)


def test_primary_layering_tap_and_geometric_tolerance():
    sheet = {
        "id": "primary",
        "cabinet": "GGD",
        "symbols": [
            symbol("QF1", "QF", {"out": (4, 22)}, circuit="IN"),
            symbol("WB1", "WB", {"src": (4, 18), "f1": (8, 18)}, circuit="BUS"),
            symbol("QF2", "QF", {"in": (8, 15), "out": (8, 13)}, circuit="WL1"),
            symbol("M1", "M", {"in": (8, 4)}, circuit="WL1"),
            symbol("FU1", "FU", {"in": (2, 9)}, circuit="WL2"),
            symbol("WL1", "WL", {"in": (18, 7)}, circuit="WL1"),
        ],
        "wires": [
            ((3.95, 22), (4, 18)),
            ((8, 18), (8, 15)),
            ((8, 13), (8, 4)),
            ((2, 9), (8, 9)),
        ],
    }
    netlist = reconstruct({"sheets": [sheet]})
    assert netlist["children"]["QF1"] == ["WB1"]
    assert netlist["children"]["WB1"] == ["QF2"]
    assert pair("QF2", "FU1") in endpoints(netlist)
    assert pair("QF2", "M1") in endpoints(netlist)
    assert pair("QF2", "WL1") in endpoints(netlist)
    cable = next(edge for edge in netlist["edges"] if edge["target"] == "WL1")
    assert cable["origin"] == "circuit_label" and cable["route"] == []


def test_secondary_parallel_control_and_scoped_cross_page_labels():
    a = {
        "id": "A",
        "cabinet": "CTRL",
        "symbols": [
            symbol("S", "SB_NC", {"right": (1, 4)}),
            symbol("F", "KM_NO", {"left": (7, 7)}),
            symbol("R", "KM_NC", {"left": (7, 1)}),
        ],
        "wires": [
            ((1, 4), (8, 4)),
            ((4, 1), (4, 7)),
            ((4, 1), (7, 1)),
            ((4, 7), (7, 7)),
        ],
        "junctions": [(4, 4)],
        "wire_labels": [{"number": "12", "point": (8, 4)}],
    }
    b = {
        "id": "B",
        "cabinet": "CTRL",
        "symbols": [symbol("K", "KM_COIL", {"left": (7, 5)})],
        "wires": [((1, 5), (7, 5))],
        "wire_labels": [{"number": 12, "point": (1, 5)}],
    }
    c = {**b, "id": "C", "cabinet": "other"}
    result = reconstruct({"sheets": [a, b, c]})
    expected = {pair("A/S", "A/F"), pair("A/S", "A/R"), pair("A/S", "B/K")}
    assert expected <= endpoints(result)
    cross_sheet = next(
        e for e in result["edges"] if {e["source"], e["target"]} == {"A/S", "B/K"}
    )
    assert cross_sheet["kind"] == "control"
    assert [part["sheet_id"] for part in cross_sheet["route"]] == ["A", "B"]
    assert any(
        "A/S" in circuit.get("parallel_splits", []) for circuit in result["circuits"]
    )
    assert all("C/K" not in connected for connected in endpoints(result))


def test_dxf_arc_bridges_visible_crossing(tmp_path):
    doc = ezdxf.new()
    layout = doc.modelspace()
    dxf = {"layer": "WIRE"}
    layout.add_line((0, 0), (7, 0), dxfattribs=dxf)
    layout.add_arc((10, 0), 3, 0, 180, dxfattribs=dxf)
    layout.add_lwpolyline([(13, 0), (20, 0)], dxfattribs=dxf)
    layout.add_line((10, -5), (10, 7), dxfattribs=dxf)
    layout.add_line((0, 0), (10, -5), dxfattribs={"layer": "TITLE"})
    doc.saveas(tmp_path / "drawing.dxf")
    sheet = {
        "id": "cross",
        "file": "drawing.dxf",
        "symbols": [
            symbol("A", "QF", {"out": (0, 0)}),
            symbol("B", "M", {"in": (20, 0)}),
            symbol("C", "QF", {"out": (10, 7)}),
            symbol("D", "M", {"in": (10, -5)}),
        ],
    }
    result = reconstruct({"sheets": [sheet]}, tmp_path)
    assert endpoints(result) == {pair("A", "B"), pair("C", "D")}
    assert any(
        y > 2.9 for e in result["edges"] if e["source"] == "A" for _, y in e["points"]
    )


@pytest.mark.parametrize("with_dot", [False, True])
def test_raster_crossing_accepts_only_filled_junction(tmp_path, with_dot):
    image = Image.new("RGB", (61, 61), "white")
    ink = ImageDraw.Draw(image)
    ink.line([(5, 30), (55, 30)], fill="black", width=3)
    ink.line([(30, 5), (30, 55)], fill="black", width=3)
    if with_dot:
        ink.ellipse((25, 25, 35, 35), fill="black")
    image.save(tmp_path / "drawing.png")
    sheet = {
        "id": "raster",
        "file": "drawing.png",
        "port_tolerance": 2,
        "symbols": [
            symbol("a", "QF", {"out": (5, 31)}),
            symbol("b", "M", {"in": (55, 31)}),
            symbol("c", "QF", {"out": (30, 56)}),
            symbol("d", "M", {"in": (30, 6)}),
        ],
    }
    connections = endpoints(reconstruct({"sheets": [sheet]}, tmp_path))
    assert {pair("a", "b"), pair("c", "d")} <= connections
    assert len(connections) == (6 if with_dot else 2)


def test_bom_scope_anchors_conflicts_and_cli_exports(tmp_path):
    component = symbol(
        "QF1",
        "QF",
        {"out": (0, 0)},
        circuit="WL1",
        unit="台",
        specs={"model": "=custom", "spec": "3P", "In_A": 63},
        bbox=(0, 0, 2, 2),
    )
    changed = {**component, "specs": {**component["specs"], "In_A": 40}}
    contact = symbol("KM1", "KM_NO", {"left": (0, 0)})
    sheet = {
        "id": "one",
        "cabinet": "G01",
        "symbols": [component, contact],
        "wires": [],
    }
    project = {
        "sheets": [
            sheet,
            {**sheet, "id": "two", "symbols": [changed]},
            {**sheet, "id": "three", "cabinet": "G02"},
        ]
    }
    bom = build_bom(project)
    assert len(bom["items"]) == 2
    assert len(bom["items"][0]["anchors"]) == 2
    assert bom["warnings"][0]["field"] == "In_A"
    source = tmp_path / "project.json"
    target = tmp_path / "out"
    source.write_text(json.dumps(project), encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "netlist", str(source), "--out", str(target)], check=True
    )
    assert len(json.loads((target / "netlist.json").read_text())["nodes"]) == 5
    assert len(json.loads((target / "bom.erp.json").read_text())["items"]) == 2
    wb = load_workbook(target / "bom.xlsx")
    assert wb["明细"]["F2"].data_type == "s"
    with (target / "bom.csv").open(encoding="utf-8-sig") as csv_file:
        assert next(csv.DictReader(csv_file))["model"] == "'=custom"
