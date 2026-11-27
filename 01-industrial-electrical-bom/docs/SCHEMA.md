# ElectroBench-JS 标注规范 v1.0.0

> 作品「图枢电析」· 赛题 `AI-MFG-Q21` · 本文件可直接摘进佐证材料 PDF。  
> 机器可读字段以 `schema/electrobench.schema.json` 与 `electrobench/catalog.py` 为准。  
> 冻结样例的计数见生成后的 `samples/STATS.md`。

## 1. 数据集是什么

ElectroBench-JS 是一套**可复现的成套电气图纸评测集**。每张图同时给出：

- 矢量 `drawing.dxf` 与矢量 `drawing.pdf`
- 光栅 `drawing.png`（图幅 420 mm × 297 mm，4 px/mm，1680 × 1188）
- 实例级真值 `annotations.json`（类别、规格、端口、毫米框与像素框）
- COCO `coco.json` 与 YOLO `labels.txt`
- 明细 `bom.csv` 与汇总 `bom_summary.csv`
- 拓扑 `netlist`（写在 `annotations.json` 内）
- 二次回路的逻辑真值表，以及 4 类国标合规缺陷的规则真值

图形是按 GB/T 4728 / IEC 60617 的常见简图形态用 `ezdxf` **程序化近似**画出来的，供检测与拓扑评测使用，不是标准图版的官方复制件。

图面上的文字代号（`QF`、`QS`、`KM`、`FR`、`FU`、`TA`、`TV` 等）是成套开关柜图纸仍在使用的行业习惯写法。`iec81346` 字段另给 IEC 81346-2:2019 表 1 的类字母。GB/T 5094 采用的是与 IEC 81346 对应的结构原则与参照代号，不把 `QF` 这种双字母规定为类字母。二者在本数据集里同时保留，评测以 `class_code` 为准。

IEC 81346-2:2019 表 1 中，字母 D、J、L、V、Y、Z 为预留，A、I、O 不得用作类字母。因此电抗器的行业代号 `L` 不填写 `iec81346`；合闸/分闸线圈的行业代号 `YC`/`YO` 在 `iec81346` 中记为开关电器的类字母 `Q`。接触器在 2019 版中属于控制能量流通的 `Q`，图面仍印 `KM`。

## 2. 四层划分

| 层 | 目录 | 内容 |
| :--- | :--- | :--- |
| 公开基础层 | `public/`、`docs/PUBLIC_DATASETS.md` | 可核验的外部数据集条目、许可证与落地页。不提交大文件。外部类别要映射到下表的 `class_code`，映射不到就保持未映射。 |
| 一次系统图 | `samples/primary/` | GGD、MNS、GCS、KYN28 各 1 张。含母线、进出线、测量、电缆回路。 |
| 二次原理图 | `samples/secondary/` | 电机启停自锁、正反转互锁、双电源切换。含线圈、触点、端子、线号与逻辑真值。 |
| 缺陷与退化 | `samples/defect/`、`samples/degraded/` | 4 类合规缺陷各 1 张；另有模糊、倾斜、非标简写各 1 张。 |

发布卷的生成命令（种子 262 只写入元数据；`sample` 预设的几何是冻结的）：

```bash
python -m electrobench generate --preset sample --seed 262 --out samples
python -m electrobench validate samples
```

`random` 预设会用种子改变馈线数量与额定电流，并且仍然满足合规规则。它不进入冻结卷。

## 3. 单图目录

```
samples/<subset>/<drawing-id>/
  drawing.dxf
  drawing.pdf          # 模糊/倾斜件没有矢量复本
  drawing.png
  annotations.json
  bom.csv
  bom_summary.csv
  coco.json
  labels.txt           # YOLO，一行一个实例
```

全卷还有 `samples/manifest.json`、`samples/electrobench_coco.json`、`samples/classes.txt`、`samples/STATS.md`。

图纸编号：

| 编号 | 子集 | 内容 |
| :--- | :--- | :--- |
| `EBJS-P-GGD-001` | primary | GGD，进线隔离开关 + 断路器，含电动机、计量、熔断器馈线 |
| `EBJS-P-MNS-002` | primary | MNS，三路电动机（断路器 + 接触器 + 热继电器） |
| `EBJS-P-GCS-003` | primary | GCS，电动机 + 串联电抗器的电容器回路 |
| `EBJS-P-KYN-004` | primary | KYN28 10 kV，隔离、接地、真空断路器、互感器、电抗器、变压器 |
| `EBJS-S-DOL-001` | secondary | 启停自锁 |
| `EBJS-S-FREV-002` | secondary | 正反转，含行程开关与电气互锁 |
| `EBJS-S-ATS-003` | secondary | 双电源切换，含选择开关、时间继电器、合分闸线圈 |
| `EBJS-D-SEL-001` | defect | 上下级断路器额定电流倒挂 |
| `EBJS-D-AMP-002` | defect | 电缆载流量低于保护电器 In |
| `EBJS-D-MOT-003` | defect | 电动机回路缺少热继电器 |
| `EBJS-D-ILK-004` | defect | 正反转两侧都没有对方的常闭互锁 |
| `EBJS-G-BLUR-001` | degraded | 由 GGD 光栅做高斯模糊，框不移动 |
| `EBJS-G-SKEW-002` | degraded | 由启停图逆时针转 3.5°，框随像素更新 |
| `EBJS-G-ALIAS-003` | degraded | 与 GGD 同拓扑，图面改为非标简写 |

## 4. 符号目录

`class_id` 是 COCO / YOLO 的类别号，冻结后不改。`BOM 锚点=否` 的图形属于已有器件（触点、线号、接地符号），不另计数量。

| id | class_code | 名称 | 行业代号 | IEC 81346-2:2019 | 单位 | BOM 锚点 | 层 |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | `QF` | 断路器 | QF | Q | 台 | 是 | primary |
| 1 | `QS` | 隔离开关 | QS | Q | 台 | 是 | primary |
| 2 | `QE` | 接地开关 | QE | Q | 台 | 是 | primary |
| 3 | `KM_MAIN` | 接触器主触头 | KM | Q | 台 | 是 | primary |
| 4 | `KM_COIL` | 接触器线圈 | KM | Q | 台 | 否 | secondary |
| 5 | `KM_NO` | 接触器常开触点 | KM | Q | 台 | 否 | secondary |
| 6 | `KM_NC` | 接触器常闭触点 | KM | Q | 台 | 否 | secondary |
| 7 | `KA_COIL` | 中间继电器线圈 | KA | K | 只 | 是 | secondary |
| 8 | `KA_NO` | 中间继电器常开触点 | KA | K | 只 | 否 | secondary |
| 9 | `KA_NC` | 中间继电器常闭触点 | KA | K | 只 | 否 | secondary |
| 10 | `KT_COIL` | 时间继电器线圈 | KT | K | 只 | 是 | secondary |
| 11 | `KT_NO` | 时间继电器延时常开触点 | KT | K | 只 | 否 | secondary |
| 12 | `FR` | 热继电器 | FR | F | 只 | 是 | primary |
| 13 | `FR_NC` | 热继电器常闭触点 | FR | F | 只 | 否 | secondary |
| 14 | `FU` | 熔断器 | FU | F | 只 | 是 | both |
| 15 | `TA` | 电流互感器 | TA | B | 只 | 是 | primary |
| 16 | `TV` | 电压互感器 | TV | B | 只 | 是 | primary |
| 17 | `SPD` | 电涌保护器 | SPD | F | 只 | 是 | primary |
| 18 | `T` | 电力变压器 | T | T | 台 | 是 | primary |
| 19 | `TC` | 控制变压器 | TC | T | 台 | 是 | secondary |
| 20 | `M` | 电动机 | M | M | 台 | 是 | primary |
| 21 | `PA` | 电流表 | PA | P | 只 | 是 | primary |
| 22 | `PV` | 电压表 | PV | P | 只 | 是 | primary |
| 23 | `PJ` | 电能表 | PJ | P | 只 | 是 | primary |
| 24 | `C` | 电容器 | C | C | 只 | 是 | primary |
| 25 | `L` | 电抗器 | L | — | 只 | 是 | primary |
| 26 | `HL` | 指示灯 | HL | P | 只 | 是 | secondary |
| 27 | `HA` | 电铃 | HA | P | 只 | 是 | secondary |
| 28 | `SB_NO` | 常开按钮 | SB | S | 只 | 是 | secondary |
| 29 | `SB_NC` | 常闭按钮 | SB | S | 只 | 是 | secondary |
| 30 | `SA` | 选择开关 | SA | S | 只 | 是 | secondary |
| 31 | `SQ` | 行程开关 | SQ | B | 只 | 是 | secondary |
| 32 | `XT` | 端子 | XT | X | 只 | 是 | secondary |
| 33 | `WB` | 母线 | WB | W | 套 | 是 | primary |
| 34 | `YC` | 合闸线圈 | YC | Q | 只 | 是 | secondary |
| 35 | `YO` | 分闸线圈 | YO | Q | 只 | 是 | secondary |
| 36 | `ATS` | 双电源转换开关 | ATS | Q | 台 | 是 | primary |
| 37 | `PE` | 保护接地 | — | — | — | 否 | annotation |
| 38 | `WL` | 导线回路 | WL | W | 回路 | 是 | primary |
| 39 | `WIRE_NO` | 线号 | — | — | — | 否 | annotation |

冻结样例 14 张图把上表 40 个类别各至少出现一次。

器件型号字符串（`EB-MCCB-250/160` 这类）是本评测集的合成目录号，不是某个厂家的产品型号。电缆型号采用 `YJV-4x截面+1xPE` 这种类型写法。

## 5. annotations.json

顶层字段：

| 字段 | 含义 |
| :--- | :--- |
| `schema_version` | 固定 `1.0.0` |
| `id` / `subset` / `title` / `seed` | 图纸身份。`subset` 为 `primary`、`secondary`、`defect`、`degraded` |
| `cabinet` | `GGD` / `MNS` / `GCS` / `KYN28`，二次图为空 |
| `circuit_kind` | `dol_self_hold`、`reversing`、`ats` 或空 |
| `alias` | 图面是否使用非标简写 |
| `interlock` | 正反转图是否画了电气互锁 |
| `degradation` | 空，或 `{type, ...}`，`type` 为 `blur` / `skew` / `alias` |
| `sheet` | 毫米图幅、`px_per_mm=4`、像素宽高 |
| `instances` | 全部符号与线号 |
| `netlist` | `nodes`、`edges`、`children`、`roots` |
| `control_branches` | 二次线圈支路的串联实例 id |
| `logic` | 真值表。一次图为空 |
| `bom` / `bom_summary` | 与两份 CSV 一致 |
| `defects` | 规则重算结果。干净图为空数组 |

实例字段：`id`、`tag`、`class_id`、`class_code`、`bom_letter`、`iec81346`、`bom_anchor`、`in_netlist`、`bbox_mm`（左下角 x,y,w,h，y 向上）、`bbox_px`（左上角 x,y,w,h，y 向下）、`ports`、`specs`、`label_tag`、`label_spec`、`circuit`、`extra`。

`specs` 是规范真值。非标简写只出现在 `label_tag` / `label_spec` 和图面墨线里，不改 `specs`、不改 `class_code`。

像素框由毫米框按整张图的线性比例换算，y 轴翻转。倾斜件额外保存 `bbox_px_source`，`bbox_px` 是按 Pillow `rotate(expand=True)` 的几何把源框四角旋到新图后的外接矩形。

## 6. COCO 与 YOLO

- COCO `bbox` 与 `bbox_px` 相同，`category_id` 等于 `class_id`。
- YOLO 一行：`class_id cx cy w h`，相对图像宽高归一化。
- `classes.txt` 的行序就是 `class_id`。
- 全卷 `electrobench_coco.json` 把 14 张图收成一个 COCO 文件，`file_name` 相对 `samples/`。

## 7. Netlist 口径

- 节点集合 = `in_netlist=true` 的实例。只有线号为 `false`。
- `power` 边从上游指向下游。级差、载流量、电机保护都只沿 `power` 回溯。
- `branch` 是测量分支（电流表、电压表），不参与上述三条规则。
- `pe` 是接地支路。
- `control` 是二次连线。互锁规则读的是 `control_branches.series_ids`，不是把控制线再走一遍几何。
- 边的点列首尾必须落在对应端口坐标上（容差 0.05 mm）。电缆标注与保护电器之间可以只有逻辑边、不另画一根跨越图面的线，点列仍然对准端口。
- `roots` 是没有 `power` 父节点的节点。`children` 只索引 `power` 边。

## 8. BOM 口径

1. 每个 `bom_anchor=true` 的实例对应明细一行，`qty=1`。
2. 明细的 `model`、`spec` 等于该实例 `specs` 里的同名字段。
3. 接触器：有主触头时只把 `KM_MAIN` 计入 BOM，线圈和辅助触点共用位号、不另计。正反转因此是两台接触器（`KMF`、`KMR`）。
4. 热继电器只计 `FR` 本体。中间继电器、时间继电器计线圈，不计触点。
5. 合闸线圈 `YC`、分闸线圈 `YO` 按独立二次元件各计一只，不并进断路器行。这是评测口径，方便和二次图上的线圈框对齐。
6. 电缆按回路计，单位「回路」，不按米。
7. 母线按「套」。保护接地符号和线号不进 BOM。
8. 汇总键是 `(bom_letter, name_zh, model, spec, unit)`，数量等于明细行之和。`bom_summary.csv` 的 `tags` 列为空格分隔的位号。

校验脚本重算上述关系。明细、汇总、CSV、实例锚点四者不一致即失败。

## 9. 四类缺陷的判定式

规则实现在 `electrobench/rules.py`。生成器和校验器调用同一函数，因此标注里的 `defects` 必须与重算结果逐字相同。

这些判定是 **ElectroBench 评测操作化**。它们引用真实条款作为依据，但不代替整定曲线、厂家配合表或载流量标准表的工程设计。

### 9.1 上下级断路器级差倒挂 `selectivity_inversion`

- 依据：GB 50054-2011 第 6.1.2 条（上下级保护电器的动作特性应能协调配合）。选择性的定义见 GB/T 14048.2。
- 操作化：沿 `power` 边找到下级断路器最近的上级断路器。若 `In_下级 > In_上级`，记一条缺陷。相等不算倒挂。熔断器不参与这条比较。
- 完整的选择性还要核对时间-电流特性。本评测只把「额定电流倒挂」当作必失败的筛查，不把某个固定倍数（例如 1.6）写成断路器的强制条款。1.6 这个比例出现在 GB 50054-2011 第 6.1.2 条的条文说明里，说的是熔断器熔体，不是断路器。

### 9.2 导线载流量不足 `ampacity_insufficient`

- 依据：GB 50054-2011 第 6.3.3 条，`Ib ≤ In ≤ Iz`。导体载流量的标准出处是该规范指向的 GB/T 16895.15；铠装电缆另见 GB 50217。
- 操作化：电缆实例带 `Ib_A`、`Iz_A`、`section_mm2`。保护电器是上游最近的断路器或熔断器。`In > Iz` 或 `Ib > Iz` 记缺陷。
- `Iz` 用下表，而不是标准表格的逐字转录。表内数值只服务本评测的可复现判定。

| 截面 mm² | 2 | 4 | 6 | 10 | 16 | 25 | 35 | 50 | 70 | 95 | 120 | 150 | 185 | 240 | 300 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Iz / A | 16 | 28 | 36 | 50 | 66 | 87 | 110 | 134 | 171 | 207 | 239 | 271 | 310 | 367 | 430 |

### 9.3 电机保护缺配 `motor_protection_missing`

- 依据：GB/T 5226.1-2019 第 7.2 条过电流保护、第 7.3 条电动机过热保护；GB 50054-2011 第 6.1.1 条要求配电线路装设短路保护和过负荷保护。
- 操作化：每台电动机的全部 `power` 祖先里，必须有热继电器 `FR`，并且有断路器 `QF` 或熔断器 `FU`。缺哪一类就写入 `evidence.missing`。注入样例只去掉热继电器，短路保护仍在。

### 9.4 二次互锁缺失 `interlock_missing`

- 依据：GB/T 5226.1-2019 第 9.3 条联锁保护。
- 操作化：`circuit_kind=reversing` 时，每个方向的线圈支路必须含一个 `KM_NC`，且 `extra.interlocks` 等于对侧接触器位号。正转支路要串 `KMR` 的常闭，反转支路要串 `KMF` 的常闭。缺一条支路记一条缺陷，因此缺陷卷这一项为 2 条。
- 逻辑真值在有互锁时禁止两侧同时吸合；去掉互锁后，方程允许两侧同时为 1。真值表由 `electrobench/logic.py` 枚举，校验时重算比对。

双电源图另有一条不记入上述四类的健全性检查：真值表中不允许两侧同时合闸。

### 9.5 三个二次方程

- 启停自锁：`KM' = (not STOP) and (not FR) and (START or KM)`。`STOP=1` 表示停止按钮按下（常闭打开），`FR=1` 表示热继电器动作。16 行。
- 正反转：在自锁式上再乘行程开关常闭，以及（有互锁时）对侧按钮和对侧接触器的否定。8 个布尔输入，256 行。
- 双电源：`SA=1` 只合 I 段，`SA=2` 只合 II 段，`SA=0` 为自动，有 I 段电压则合 I 段，否则在延时完成后合 II 段。24 行。

## 10. 退化

| 类型 | 参数 | 框怎么变 |
| :--- | :--- | :--- |
| `blur` | 高斯半径 1.8 px | 不移动。模拟扫描发虚。 |
| `skew` | 逆时针 3.5°，白底扩展画布 | 四角旋转后取外接矩形，与 Pillow 的展开旋转一致。 |
| `alias` | 位号前缀换成「空开 / 闸刀 / 热偶 / CT / PT / 马达」等，规格里的电流单位改成「安」 | 框仍按毫米图幅。`specs` 保持规范值。 |

非标简写的替换表在 `electrobench/catalog.py` 的 `ALIASES`。

## 11. 公开基础层

外部数据集的名称、落地页和许可证见 `docs/PUBLIC_DATASETS.md` 与 `public/catalog.json`。下载脚本默认只打印目录。没有 `direct_url` 的条目不会被静默下载。

本仓库**没有**把下列名称写成数据集：检索时未能核到名为 `EplanSymbols` 的 Roboflow 数据集。Kaggle 上的 `electrical-symbols-dataset` 页面在检索当日没有填写许可证，且素材被描述为 EPLAN 符号，因此不接入下载器。

## 12. 许可证与复现依赖

- `samples/` 下的合成图纸、标注、CSV 以及本规范文本，以 CC-BY-4.0 发布。
- 外部数据保持各自许可证，不因写入本目录而改变。
- 生成依赖 Python 3、`ezdxf`、`matplotlib`、`pillow`，以及字体文件 `wqy-microhei.ttc`（Debian/Ubuntu 包 `fonts-wqy-microhei`）。缺字体时程序直接退出，避免图面中文变成方框后仍写出“通过”的标注。
- DXF 文件头时间固定为 2026-11-27，避免仅因时钟变化改写文件。
- 评测对比应以 `annotations.json` 为准。PNG 是否字节级一致取决于 Matplotlib 版本，校验脚本核对的是尺寸、框和语义，不核对 PNG 字节。
