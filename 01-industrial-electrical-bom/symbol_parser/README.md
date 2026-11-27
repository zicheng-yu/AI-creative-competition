# YOU-263 · 电气图纸符号与规格识别

解析 DXF、矢量 PDF、扫描 PDF、PNG、JPEG、TIFF 等图纸，输出统一的器件类别、原图定位、端口、位号、规格、额定参数和置信度。可从 Python 调用 `symbol_parser.engine.parse_drawing`，也可使用命令行。

## 运行

在 `01-industrial-electrical-bom/` 内执行。

```bash
python -m pip install -r symbol-parser-ocr-requirements.txt
python -m symbol_parser drawing.dxf --out output/dxf.json
python -m symbol_parser drawing.pdf --out output/pdf.json
python -m symbol_parser drawing.png --out output/png.json
```

只做 DXF 原生图元识别或无 OCR 的光栅几何匹配时，可安装 `symbol-parser-requirements.txt` 并传入 `--no-ocr`。页面 OCR 由 RapidOCR 执行 PaddleOCR ONNX 模型，输出原文与位置。局部重读只在编号已定位但额定参数缺漏时尝试。扫描图可用 `--pixels-per-mm` 指定分析图的比例以覆盖默认估计。

### 识别通道

- DXF 用 ezdxf 读取图层、块和坐标。已知块使用原始插入变换和目录端口，LINE、POLYLINE、ARC、CIRCLE 等保留离散路径。未出现可映射块时，可根据可见几何与位号用模板匹配散线图元。
- PDF 用 PyMuPDF 读取路径和可提取的文本。几何模板从页面渲染图匹配符号；文字转换成曲线的 PDF 和纯扫描 PDF 使用光栅文字识别。
- 光栅默认使用可复现的模板匹配结合 OCR。模板来自 [ElectroBench-JS](https://github.com/zicheng-yu/AI-creative-competition/pull/4) 的程序化符号目录，兼顾连线重叠、规范位号与常见别名。
- 位号和规格各做一次一对一的最小成本空间分配。匹配先受类别前缀约束，再参考图纸位置、标注对齐和置信度。规格缺失时保留空值并标记待复核。

### 可选 SAHI / YOLO 与 VLM

```bash
python -m pip install -r symbol-parser-yolo-requirements.txt
python -m symbol_parser drawing.png --yolo-weights ./best.pt --out output/yolo.json
python -m symbol_parser drawing.pdf --out output/refined.json \
  --vlm-url http://127.0.0.1:8000/v1/chat/completions --vlm-model local-vision
```

`--yolo-weights` 指向本地电气符号检测模型，模型的类别名应与目录中的 `class_code` 一致。SAHI 使用 640 像素重叠切片和按类 NMS；可用 `--yolo-confidence` 调节阈值。默认模板和 YOLO 是两种可独立测量的检测方式。

配置 VLM 后，程序将低置信度器件附近的 512×512 裁片发给指定服务。令牌从 `SYMBOL_PARSER_VLM_TOKEN` 读取。候选位号必须符合当前类别，返回值不得改动类别或几何，修订项保留待复核标记。没有配置服务时，解析在本机执行。

## 输出与下游接入

`sheets[]` 包含 `channel`、坐标系、`symbols`、原始图元、文本和诊断。器件 `bbox` 采用 `[x, y, width, height]`，x 向右、y 向上，与 YOU-264 的端口坐标约定一致。`bbox_top_left` 用于前端叠加显示，PDF 和扫描图使用分析图的像素坐标。`coordinate_space` 提供分析尺寸以及 PDF 点或原图像素到分析图的换算信息。DXF 保留原生绘图单位和坐标。

已验证使用 YOU-264 的 Python 接口直接联调一张 DXF。调用 `reconstruct` 前将该图的本地路径填入识别页的 `file`。回路语义、采购型号等只在图面有相应信息时由后续规则或人工确认。

```python
from pathlib import Path
from netlist import reconstruct
from symbol_parser.engine import parse_drawing

drawing = Path("drawing.dxf").resolve()
payload = parse_drawing(drawing)
payload["sheets"][0]["file"] = str(drawing)
graph = reconstruct(payload)
```

## 复现验证

```bash
python -m pytest -q tests/test_symbol_parser.py
python -m symbol_parser.benchmark /path/to/ElectroBench-JS/samples --format dxf
python -m symbol_parser.benchmark /path/to/ElectroBench-JS/samples --format pdf
python -m symbol_parser.benchmark /path/to/ElectroBench-JS/samples --format png
```

默认评测纳入一次、二次及缺陷三类冻结样图各 4、3、4 张。只把图纸交给解析器，标注用于评分。符号 F1 按类别正确且框 IoU≥0.5 匹配后微平均；规格准确率以所有带规格真值的器件为分母，器件漏检计为规格错误。耗时按每张图的本机解析记录。模板与冻结样图共享符号设计，另需用独立工程图验证泛化。

使用数据集 PR #4 的 `a5e0e28` 冻结图纸测得以下结果。三种格式分别处理同一批 11 个样本，未调用 VLM。

| 输入 | 符号 F1 | 规格精确匹配 | 平均耗时 |
| --- | ---: | ---: | ---: |
| DXF | 100.00% | 95.15%（216/227） | 0.08 秒 |
| PDF | 86.25% | 69.60%（158/227） | 6.97 秒 |
| PNG | 89.05% | 72.69%（165/227） | 6.17 秒 |

小字、重叠走线及 PDF 曲线字形会影响光栅分支的规格识别。上表是本模块指标，组合解析准确率和 BOM 完整率由 YOU-267 按端到端流程验证。倾斜和模糊子集需在后续验收单列。

可选 SAHI 推理也在同批 11 张 PNG 上验证。由程序化符号布局训练的实验权重得到符号 F1 60.32%，默认继续使用模板与 OCR。VLM 已通过模拟端点测试。

模板目录如需更新，可运行：

```bash
python -m symbol_parser.export_catalog /path/to/01-industrial-electrical-bom symbol_parser/electrobench-catalog.json
```

底层接口见 [PyMuPDF 图形提取](https://pymupdf.readthedocs.io/en/latest/recipes-drawing-and-graphics.html) 和 [SAHI 切片推理](https://docs.ultralytics.com/guides/sahi-tiled-inference/)。
