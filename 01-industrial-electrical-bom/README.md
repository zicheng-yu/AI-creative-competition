# ElectroBench-JS：成套电气图纸评测集

赛题 `AI-MFG-Q21`（电气图纸智能解析与 BOM 自动生成）的标准化数据集。标注规范见 [docs/SCHEMA.md](docs/SCHEMA.md)，公开数据与许可证见 [docs/PUBLIC_DATASETS.md](docs/PUBLIC_DATASETS.md)。

合成样例（`samples/`）和规范文本以 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 发布。外部数据集保持各自许可证，不进本仓库。

## 环境

```bash
pip install -r requirements.txt
```

需要系统里能找到 `wqy-microhei.ttc`（Debian/Ubuntu：`fonts-wqy-microhei`）。没有这套字体时生成程序会退出，避免中文变成方框还继续写标注。

## 生成

在本目录执行。`--out` 会先清空目标目录。

```bash
python -m electrobench generate --preset sample --seed 262 --out samples
python -m electrobench generate --preset random --seed 262 --count 4 --out /tmp/ebjs-random
```

`sample` 是冻结评测卷：4 张一次图（GGD / MNS / GCS / KYN28）、3 张二次图（启停自锁、正反转互锁、双电源切换）、4 张缺陷图、3 张退化图（模糊、倾斜、非标简写）。几何不随种子变化，种子写入元数据。`random` 的馈线额定值由种子决定，并且仍然满足合规规则。

每张矢量图包含 `drawing.dxf`、`drawing.pdf`、`drawing.png`、`annotations.json`、`bom.csv`、`bom_summary.csv`、`coco.json`、`labels.txt`。模糊和倾斜只有光栅和标注。

## 校验

```bash
python -m electrobench validate samples
```

脚本确认：

- 类别号都在 40 类目录内，冻结卷覆盖全部类别
- 像素框与毫米框（倾斜件则与旋转公式）一致，且落在图像内
- Netlist 节点等于 `in_netlist` 实例，边的端点落在端口上
- BOM 明细、汇总和两份 CSV 与锚点实例一致
- 四类缺陷与 `electrobench/rules.py` 的重算结果一致；一次图、二次图和退化图没有缺陷
- 二次逻辑真值表与方程重算一致

退出码 0 为通过。

## 公开数据

```bash
python scripts/download_public.py
python scripts/download_public.py --targets
```

目录只记录核过的落地页和许可证。没有直接文件地址的条目不会被下载。

## 冻结卷规模

由 `python -m electrobench generate --preset sample --seed 262` 生成，校验输出：

- 图纸 14 张（一次 4、二次 3、缺陷 4、退化 3）
- 符号实例 345
- 类别 40 / 40
- 缺陷条数：级差倒挂 1、载流量不足 1、电机保护缺配 1、二次互锁缺失 2（正反转两侧各 1 条）

明细以 `samples/STATS.md` 为准。
