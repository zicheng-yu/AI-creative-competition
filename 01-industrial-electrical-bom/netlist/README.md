# 图枢电析拓扑与 BOM 模块

本模块接收上游已识别的器件、端口、位号与规格，从图纸导线重建拓扑，并生成采购清单。图纸坐标全程使用 **x 向右、y 向上** 的同一坐标系。DXF 通常用毫米。光栅坐标满足 `(x, y) = (列 / 比例, (图像高度 - 行) / 比例)`。

## 运行

在 `01-industrial-electrical-bom/` 目录运行。

```bash
python -m pip install -r netlist-requirements.txt
python -m netlist parsed-sheet.json --out ./netlist-output
```

最小输入 `parsed-sheet.json` 示例。此处直接提供矢量线段，替换 `wires` 为 `"file": "drawing.dxf"` 可读取分层 DXF。

```json
{
  "sheets": [{
    "id": "sheet-1",
    "cabinet": "G01",
    "symbols": [
      {"id": "i1", "tag": "QF1", "class_code": "QF", "circuit": "WL1",
       "ports": {"out": [10, 20]}, "specs": {"model": "MCCB", "spec": "3P 63A", "In_A": 63}, "unit": "台"},
      {"id": "i2", "tag": "M1", "class_code": "M", "circuit": "WL1",
       "ports": {"in": [10, 4]}, "unit": "台"}
    ],
    "wires": [[[10, 20], [10, 4]]]
  }]
}
```

| 输入 | 字段 |
| --- | --- |
| 图页 | `id`、`symbols` 与 `wires` 或 `file`。文件路径相对输入 JSON，也接受绝对路径。可选 `cabinet`、`tolerance`（线段对齐容差，默认 0.15）、`port_tolerance` |
| DXF | 默认只读取 `WIRE` 层的 LINE、LWPOLYLINE、POLYLINE、ARC。可用 `wire_layers` 指定导线层，`junction_layers` 指定带 CIRCLE 或 POINT 的接点层（默认 `JUNCTION`）。默认端口只挂接到图元端点或显式接点，以降低穿过器件的线误挂，可用 `ports_on_stroke_ends: false` 接受线段内部接入 |
| 光栅 | PNG、JPEG、TIFF 或 BMP。用 `pixels_per_unit` 指定比例，用 `text_boxes` 提供文字框，器件的 `bbox` 同时用于去除符号内部像素。`ink_threshold` 默认为 155。方向接近正交的图纸可直接运行，倾斜件应先做配准 |
| 器件 | `id`、`class_code`、`tag`、`ports`。可选 `bbox: [x,y,w,h]`、`specs`、`unit`、`name_zh`、`circuit`、`circuit_kind`、`bom_anchor`、`in_netlist` |
| 消歧 | `junctions: [[x,y],...]` 添加显式接点。`bridges` 可指定一条只在两端电气接入的曲线点列。器件可用 `port_axes` 在交叉点选 `h/v`、用 `port_roles` 将端口标为 `in/out`、用 `primary_port` 处理重合端口 |
| 跨页线号 | `wire_labels: [{"number":"12","point":[x,y]}]`。同柜号内匹配不同图页上编号相同且唯一的导线锚点。可用 `scope` 显式约定跨页范围。若锚点落在无点交叉处，可用 `axis` 选连接方向 |

## 输出

- `netlist.json` 提供 `schema_version`、`nodes`、`edges` 和 `circuits`。一次电路可用 `roots` 和 `children` 浏览进线、母线和馈线。二次回路保留 `control` 边及分支、汇合节点。设备边表示端口之间的导线连接，设备自身在某个触点状态下的导通由下游规则判定。
- 单页边含 `points`，多页边用 `route` 分页保存坐标。边类型为 `power`、`control`、`branch` 或 `pe`。同回路唯一保护器件和无几何连接的同名电缆标注会生成 `origin: "circuit_label"` 的逻辑边，坐标路径为空。该来源字段可以供前端区分显示。
- `bom.csv`、`bom_summary.csv`、`bom.xlsx` 与 `bom.erp.json` 保留柜号、回路、位号、型号、规格、额定参数和坐标锚点。同柜同回路的同类同位号重复出现时归为一个器件，保留所有锚点。缺少柜号或位号时保留分图页明细。规格冲突写入 ERP JSON 的 `warnings`。
- Python 入口为 `netlist.reconstruct(project, base)`、`netlist.build_bom(project)` 与 `netlist.export_bom(bom, target)`。PDF 矢量抽取器可将导线折线拆段后通过 `wires` 对接。

## 可复现评测

```bash
python -m pytest -q tests/test_netlist.py
python -m netlist.benchmark /path/to/ElectroBench-JS/samples --channel dxf
python -m netlist.benchmark /path/to/ElectroBench-JS/samples --channel raster
```

样本来自 [YOU-262 的数据集 PR](https://github.com/zicheng-yu/AI-creative-competition/pull/4) 的 `a5e0e28`，包括一次图 4 张、二次图 3 张、缺陷图 4 张。输入采用标注中的正确器件、端口和规格；导线从图纸提取，真值边和 BOM 仅用于计分。F1 为无向器件端口对的微平均，含图纸中由回路标签表达的逻辑边。BOM 按器件类别、位号、型号、规格和数量匹配。光栅端口允许 4 像素的挂接误差以容纳骨架化和去框后的端点偏移。

| 输入 | 拓扑 F1 | BOM 完整率 |
| --- | ---: | ---: |
| 分层 DXF | 90.91%（230 TP、26 FP、20 FN） | 100%（227/227） |
| 光栅 PNG | 86.30%（211 TP、28 FP、39 FN） | 100%（227/227） |

BOM 数字反映给定正确器件、端口和规格时的汇总结果。真实识别误差与整套系统是否达标由 YOU-263 接入后，在 YOU-267 中评测。当前未纳入倾斜和模糊子集的验收，光栅漏连及二次图重叠线段的多余边需在联调中继续核对。
