"""Apply preview patches to a copied annotation, then rebuild dependent metadata."""

from collections import defaultdict
from copy import deepcopy

from electrobench.catalog import BY_CODE
from .topology import Drawing

BOM_KEY = ("bom_letter", "name_zh", "model", "spec", "unit")


def anchor(item):
    symbol = BY_CODE.get(item["class_code"])
    return item.get("bom_anchor", symbol.default_bom_anchor if symbol else False)


def bom_rows(drawing):
    details = []
    groups = {}
    for item in drawing.items.values():
        symbol = BY_CODE.get(item["class_code"])
        if not symbol or not anchor(item):
            continue
        line = dict(line_no=len(details) + 1, instance_id=item["id"], tag=item["tag"],
                    class_code=symbol.code, bom_letter=symbol.bom_letter, name_zh=symbol.bom_name_zh,
                    model=item["specs"].get("model", ""), spec=item["specs"].get("spec", ""),
                    qty=1, unit=symbol.unit, circuit=item.get("circuit", ""))
        details.append(line)
        key = tuple(line[k] for k in BOM_KEY)
        group = groups.setdefault(key, {k: line[k] for k in BOM_KEY} |
                                  {"qty": 0, "tags": [], "line_no": len(groups) + 1})
        group["qty"] += 1
        group["tags"].append(line["tag"])
    return details, list(groups.values())


def update_specs(drawing, node, values):
    return {"op": "update_specs", "id": node, "values": values,
            "expected": {key: drawing.items[node]["specs"].get(key) for key in values}}


def insert_series(drawing, node, code, tag, kind, *, specs=None, extra=None):
    incoming = [e for e in drawing.edges
                if e["target"] == node and e.get("kind") == kind]
    ports = {e["target_port"] for e in incoming if e.get("target_port") is not None}
    if not incoming or len(ports) > 1:
        return None
    return {"op": "insert_series", "target": node, "kind": kind,
            "incoming": [{"id": e.get("id"), "source": e["source"], "target": e["target"],
                          "source_port": e.get("source_port"), "target_port": e.get("target_port")}
                         for e in incoming],
            "instance": {"class_code": code, "tag": tag, "specs": specs or {}, "extra": extra or {}}}


def _insert(data, operation):
    target = operation["target"]
    edges = data["netlist"]["edges"]
    expected = operation["incoming"]
    identity = ("id", "source", "target", "source_port", "target_port")
    def signature(edge):
        return tuple(edge.get(key) for key in identity)

    expected_signatures = {signature(row) for row in expected}
    selected = [e for e in edges if e["kind"] == operation["kind"]
                and signature(e) in expected_signatures]
    current = [e for e in edges if e["kind"] == operation["kind"] and e["target"] == target]
    if not selected or len(selected) != len(expected) or len(current) != len(selected):
        raise ValueError(f"series patch is stale or does not cover all incoming paths for {target}")
    destination = next(item for item in data["instances"] if item["id"] == target)
    identifier = f"repair-{operation['instance']['class_code']}-{target}"
    if any(item["id"] == identifier for item in data["instances"]):
        raise ValueError(f"instance already exists: {identifier}")
    part = deepcopy(operation["instance"])
    symbol = BY_CODE[part["class_code"]]
    data["instances"].append(part | {
        "id": identifier, "class_id": symbol.class_id, "bom_letter": symbol.bom_letter,
        "iec81346": symbol.iec81346, "bom_anchor": symbol.default_bom_anchor,
        "in_netlist": True, "circuit": destination.get("circuit", ""), "ports": {},
        "bbox_px": None, "bbox_mm": None, "label_tag": part["tag"],
        "label_spec": part["specs"].get("spec", ""), "layout_pending": True,
    })
    ports = {e["target_port"] for e in selected if e.get("target_port") is not None}
    if len(ports) > 1:
        raise ValueError("series insertion requires one common target port")
    port = next(iter(ports), None)
    for edge in selected:
        edge.update(target=identifier, target_port="in", points=[])
    edges.append(dict(id=identifier + "-out", source=identifier, target=target,
                      kind=operation["kind"], source_port="out", target_port=port, points=[]))
    if operation["kind"] == "control":
        for branch in data.get("control_branches") or []:
            series = branch["series_ids"]
            if target in series:
                series.insert(series.index(target), identifier)


def apply_fix(data, suggestion):
    """Apply a semantic preview. Insertions require placement in the CAD editor."""
    if not suggestion["operations"]:
        raise ValueError("this finding requires engineering review")
    result = deepcopy(data)
    for operation in suggestion["operations"]:
        op = operation["op"]
        if op == "update_specs":
            item = next(i for i in result["instances"] if i["id"] == operation["id"])
            normalized = Drawing(result).items[operation["id"]]["specs"]
            if any(normalized.get(key) != old for key, old in operation["expected"].items()):
                raise ValueError(f"specification patch is stale for {item['id']}")
            item.setdefault("specs", {}).update(operation["values"])
            if "spec" in operation["values"]:
                item["label_spec"] = operation["values"]["spec"]
        elif op == "insert_series":
            _insert(result, operation)
        elif op != "rebuild_bom":
            raise ValueError(f"unsupported patch operation: {op}")
    drawing = Drawing(result)
    netlist = result["netlist"]
    children = defaultdict(list)
    for src, target in drawing.power.edges:
        children[src].append(target)
    if "nodes" in netlist:
        nodes = netlist["nodes"]
        known = {n.get("id") if isinstance(n, dict) else n for n in nodes}
        for item in drawing.items.values():
            if item.get("layout_pending") and item["id"] not in known:
                nodes.append({"id": item["id"], "class_code": item["class_code"], "tag": item["tag"]}
                             if nodes and isinstance(nodes[0], dict) else item["id"])
    netlist["children"] = dict(children)
    netlist["roots"] = [node for node in drawing.power if not drawing.power.in_degree(node)
                        and drawing.items[node].get("in_netlist", True)]
    result["bom"], result["bom_summary"] = bom_rows(drawing)
    return result
