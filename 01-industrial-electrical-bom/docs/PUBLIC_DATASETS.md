# 公开基础层：可核验的外部数据集

检索日期：2026-11-27。本页只写当时打得开、并且能看到名称或许可证陈述的资料。摘录不是法律意见。大文件不进 git。

命令：

```bash
python scripts/download_public.py
python scripts/download_public.py --targets
python scripts/download_public.py --fetch cghd
```

`--fetch` 只在 `public/catalog.json` 写了 `direct_url` 时才下载。下面这些条目都是落地页，脚本会打印链接后退出，避免一次拉下数 GB。

## 纳入目录的资料

| id | 资料 | 落地页 | 许可证（检索当日） | 和本赛题的关系 |
| :--- | :--- | :--- | :--- | :--- |
| `cghd` | CGHD，手绘电路图 | https://doi.org/10.5281/zenodo.17469897 | Zenodo v16 为 CC-BY-4.0。GitHub `DFKI/cghd` 仓库标记为 CC0-1.0，那是仓库许可，不能代替数据包许可 | 光栅到网表的公开基准。手绘电子电路，不是国标开关柜 |
| `open-schematics` | Hugging Face `bshada/open-schematics` | https://huggingface.co/datasets/bshada/open-schematics | 数据集卡声明 CC-BY-4.0，并要求同时遵守原始硬件项目的许可证 | 原理图源文件和渲染图配对，不是一次系统图 |
| `floorplancad` | FloorPlanCAD | https://floorplancad.github.io/ | 项目站：标注与网站 CC BY-NC 4.0，且作者声明不拥有图纸版权。Hugging Face `Voxel51/FloorPlanCAD` 的卡头标签写着 cc-by-sa-4.0，正文又写 CC BY-NC 4.0 | 只作矢量符号检测的方法参考，本身不是电气图 |
| `pid-symbol-detection` | P&ID 符号检测 | https://doi.org/10.5281/zenodo.8028570 ；代码 https://github.com/mgupta70/PID_Symbol_Detection | 代码仓库 MIT。Zenodo 数据包页面当日没有许可证字段 | 大图滑窗检测的代码参考。未把 P&ID 类名映射成国标代号 |
| `roboflow-leepharma-sld1` | LEEPHARMA_SLD1，315 张 | https://universe.roboflow.com/02main-single-line-diagram-sheet13-05102018-1/leepharma_sld1 | 页面未声明许可证 | 单线图检测候选集。类名以该数据集自己的字符串为准 |
| `roboflow-e08-schematic` | E08_Schematic Diagrams_REV5，120 张 | https://universe.roboflow.com/02main-single-line-diagram-sheet13-05102018-1/e08_schematic-diagrams_rev5 | 页面未声明许可证 | 同上 |

CGHD v16 的 Zenodo 说明列出约 3269 张已标注图像、59 个对象类。引用：Thoma, Bayer, Li, Dengel, ICDAR 2021；数据包 doi:10.5281/zenodo.17469897。

P&ID 论文：Gupta, Wei, Czerniawski, *Automation in Construction* 159 (2024) 105260。

FloorPlanCAD 论文：Fan 等, ICCV 2021。项目站在 2023-01-19 的通知里写明项目已于 2022 年初停止。

## 查过但没有接入下载器的名称

- **EplanSymbols**：2026-11-27 在 Roboflow Universe 检索时，没有核到这个数据集名称，因此不写入目录。
- **Kaggle `christiandmoira/electrical-symbols-dataset`** 以及 Hugging Face 镜像 `MustangAkin/electrical-symbols-dataset`：页面把内容描述成 EPLAN 符号图。Kaggle 页面的 License 栏在检索当日是空的，所以不下载、不镜像。

## 映射规则

外部标签不要自动改写成国标代号。`--targets` 打印本数据集的 40 个 `class_code`。只有外部类名和这里的定义在语义上对得上时才写入映射；对不上就留空。合成卷的真值不依赖这些外部图像。
