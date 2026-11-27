# 赛道演示工作台

`shared-workbench/` 提供规则与约束、来源追溯、离线评测和报告导出四个可复用组件。仓库内置图枢电析、苏算绿枢两个样例，用于联调界面与接口。样例数值只用于演示交互。

## 本地启动

后端在本目录启动，默认只监听本机。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8061
```

另开终端进入 `frontend/`，用 Node.js 22.12 或更高版本启动。

```bash
npm ci
npm run dev
```

浏览器访问终端显示的本地地址。Vite 将 `/api` 转发给 FastAPI。前端通过 `npm run build` 构建，也可使用 `npm run preview` 核验构建产物。

## 契约与数据源

工作区主契约为 [workspace.schema.json](workspace.schema.json)（JSON Schema 2020-12），实例字段可参考 [图枢电析样例](backend/fixtures/electrical.json)。接口说明在本地 FastAPI 的 `/docs`。

| 接口 | 用途 |
| --- | --- |
| `GET /api/v1/workspaces?mode=mock` | 列出指定模式下的工作区及显示名称 |
| `GET /api/v1/workspaces/{id}?mode=mock` | 读取指定工作区的版本、来源、规则与图表 |
| `POST /api/v1/reports/{fmt}` | 用请求体中当前展示的工作区生成报告，支持 `md`、`pdf`、`csv`、`xlsx` |

在启动后端前将 `WORKBENCH_REAL_DIR` 设为一个目录路径，便可在前端切换到「真实数据」。赛道适配层将运行结果转换为工作区契约并写入该目录，文件名与工作区编号一致，例如 `electrical.json`。前端切换真实模式时只读取该目录。目录缺失会显示可理解的错误，坏数据会被接口拒绝。各赛道可以保留原接口，通过离线脚本或现有后端的适配函数产生快照。

接口还校验几种需要跨字段比较的约束。来源片段必须出现在原文，校验记录引用的来源必须存在，编号与坐标标签不可重复，各系列长度必须与坐标数量一致，雷达图每个坐标要有上限。修改 `backend/contracts.py` 后重新生成 schema 并运行测试。

```bash
python -m backend.schema > workspace.schema.json
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
```

## 前端接入

- `frontend/src/components.js` 导出四个面板及来源详情。事件由宿主页面接管。规则项的 `source_id` 指向来源记录，详情抽屉支持高亮原文、键盘关闭和焦点恢复。
- `frontend/src/charts.js` 按契约渲染折线、雷达和柱状图，可在界面打开数值表。来源标记、规则等级和图表均随明暗主题调整。
- 「导入评测数据」接收 `Chart[]` 的 JSON 或带 `charts` 字段的 JSON，也接受下例 CSV。当前导入数据参与报告生成，切换工作区或点击「恢复工作区数据」即可回到工作区默认数据。

```csv
chart_id,kind,title,unit,category,series,value,maximum
load,line,利用率,%,08:00,约束调度,51,
load,line,利用率,%,09:00,约束调度,60,
load,line,利用率,%,08:00,先到先服务,43,
load,line,利用率,%,09:00,先到先服务,49,
```

CSV 一行一个数据点，要求同一图表中每个系列覆盖同一组坐标。雷达类需要 `maximum`，用来指定该坐标的上限。Markdown、PDF 含来源、校验和评测数值记录，Excel 把三类记录分到不同工作表，CSV 提供平铺的评测数据。
