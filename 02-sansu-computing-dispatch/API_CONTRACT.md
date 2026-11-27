# SuCompute 前端数据与可选接口

## 直接部署静态沙盘

把 `frontend_demo_data/` 随前端静态资源一起发布。所有数据采用 UTF-8 JSON。先加载拓扑、评测摘要，选择场景时加载回放，打开审计抽屉时再加载凭证。地图节点 ID 按拓扑数组顺序编号 0–15。浙江枢纽定位杭州，安徽枢纽定位芜湖。省级调度核心为逻辑控制器。回放中第 0 小时是周一 00:00，横轴使用仿真时间。

| 文件 | 顶层结构 | 沙盘用法 |
| --- | --- | --- |
| `topology.json` | `{version, simulator, core, slot_minutes, nodes[16], pools[6], task_classes[5], affinity[5][6], latency_ms[16][16], wan_gb_per_slot}` | 节点字段为 `id, city, lon, lat, external, centres, peak_eflops, pools_eflops[6], base_pue`。经纬度为十进制度 |
| `scenarios_4x4.json` | `{version,seed,scenarios:{[scenario]:{[strategy]:Replay}}}` | 所选场景与策略的 168 小时和 7 天趋势、逐城市时序状态、调度飞线、可查凭证 ID |
| `benchmarks_summary.json` | `{version,seed,hours,scenarios,strategies,aggregation,mean,runs[24],detail_sha256,runtime}` | `mean[strategy]` 为四场景等权均值。每行 `runs` 含场景、策略、周指标、实测规划次数、最长规划与故障耗时。无事件的耗时为 null |
| `fault_failover_trace.json` | `{version,seed,events:[{scenario,strategy,slot,city,kind,severity,duration_slots,elapsed_s,trajectories}]}` | 故障回放。`trajectories[]` 含 `task_id,source,target,checkpoint_slots,remaining_slots,operation,sla_met`。空目标表示迁移无可行目的地 |
| `ledger_sample.json` | `{version,receipts:[Receipt]}` | 以 `(scenario,strategy,seed,task_id)` 定位任务，展示首次决策候选、执行分段、碳足迹及凭证 |

四种 `scenario` 值为 `normal_weekday, high_renewable, peak_shaving, fault_stress`。四种回放策略为 `RR-Local, Least-Loaded, Cost-First, SuCompute`。摘要另含 `MILP-only, Safe-RL-only`。读取示例：

```js
const read = name => fetch("./frontend_demo_data/" + name).then(r => r.json());
const { scenarios } = await read("scenarios_4x4.json");
const week = scenarios.fault_stress.SuCompute;
const city = week.nodes.utilization[72][0];
const firstDay = week.hourly.slice(0, 24);
const { receipts } = await read("ledger_sample.json");
const audit = receipts.find(r => r.scenario === "fault_stress" &&
  r.strategy === "SuCompute" && r.task_id === week.sample_task_ids[0]);
```

### Replay 与指标

`kpis` 是整段累计量计算出的 KPI，`hourly[hour]` 与 `daily[day]` 使用同一 Schema。`nodes` 的每个字段均为 `[hour][node_id]` 矩阵，包含装机利用率 `utilization`、加权 `pue`、实际消纳 `green_share`、可用绿电功率 `renewable_kw`、可用容量比例 `health`。节点下电且零用能时，PUE/消纳的 0 表示无当期分母。`flights[]` 每项为 `[hour,src_id,dst_id,count,example_task_id]`，汇总该小时同向异地调度段。通过拓扑的 external 和城市判断跨省链路。采样审计 ID 在 `sample_task_ids` 中，离线引擎可以查询任意任务。

| KPI | 单位与分母 |
| --- | --- |
| `utilization` | 已驻留物理算力时 / 已启用服务器组容量时，0–1 |
| `sla` | 同时满足时延和截止期、完整交付的任务数 / 到达任务数，拒单计违约 |
| `kwh_per_efh` | 含待机的全部机房 kWh / 已执行有效 EF·h |
| `pue` | 全部设施 kWh / IT kWh |
| `green_share` | 实际就地消纳绿电 kWh / 设施 kWh |
| `kgco2_per_efh` | 电网用电碳排 kgCO₂ / 有效 EF·h |

辅助字段有 `installed_utilization`（忙物理容量 / 全装机）、`effective_installed_utilization`（有效工作量 / 全装机容量时）、`effective_efh, energy_kwh, tasks`。全网装机包括额外的 3 个枢纽。百分比指标在前端乘 100。相对增长应计算 `(新/基线 - 1) × 100%`。SLA 差值与相对增长可以用不同单位显示。

### 审计与计量

`Receipt` 记录 `task_class,source,release_slot,deadline_slot,latency_limit_ms,required_efh`。每个 `candidate_affinity` 元素给出该节点 6 个芯片池的 `scores`（任务亲和度 η）、首次决策时的物理/配额可行掩码 `feasible`、网络时延和节点资源/碳预算的 LP 松弛影子价格。仅使用基线时节点对偶为 null。`segments[]` 含目标节点、芯片池、起止槽（左闭右开）、实际时延、加权 PUE 和绿电占比、两类影子价格及部署决策分布中所选动作的概率。策略部署采用最大分值动作，概率用于解释各候选的相对分值。

任务还含 `effective_efh, physical_efh, energy_kwh, electricity_cny, co2_kg, avoided_vs_grid_kg, sla_met, sha256`。节点同槽电耗按物理算力份额分摊。空节点待机电耗计入全网指标，单独作为设施开销。减碳参照为同一任务同等电量全部购自电网。哈希使用去除 sha256 字段后的 Python JSON，键排序、紧凑分隔符、UTF-8、保留原始浮点数。用 `backend.report.receipt_hash` 复核；JS 若重排数字格式，可能产生不同的字节序列。`Meter.audit(task_id)` 和 `Meter.export_csv(path)` 可生成完整凭证。

## 离线复现

在本赛道目录使用 Python 3.13（实测 CPU 版 PyTorch）。首次安装依赖需要本地 wheel 缓存或包源。安装完成后，训练、推理、回放、导出和测试均可断网执行。PowerShell 可使用 `.venv\Scripts\python.exe` 替代下列 python。

```sh
python -m venv .venv
# PowerShell: .\.venv\Scripts\Activate.ps1
# POSIX: source .venv/bin/activate
python -m pip install -r requirements.txt
python weights/verify_weights.py
python benchmarks/run_benchmark.py
python -m pytest -q
```

仅重新训练时，依次执行 `python benchmarks/train_forecast.py`、`python benchmarks/train_policy.py`、`python weights/verify_weights.py --release`，再跑评测。可用 `python benchmarks/run_benchmark.py --out <另一个目录>` 独立复验。对比 `detail_sha256`；CPU 实耗随主机与调度变化。`benchmarks/results_report.md`、两张 PNG、逐小时 CSV 与前端 JSON 均由同一入口生成。

## 可选的本地接口

```sh
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

`/docs` 提供 OpenAPI 交互。每次请求在独立内存日历上从指定 seed 开始。CORS 允许静态站调用。所有 POST 共用可选配置 `seed`（默认 313）、`scenario`、`strategy`、`hours`（1–168，默认 6）与 `weights`（cost、carbon、network、utilization、sla，每项 0–1）。错误输入返回 422。以下响应字段摘录用来标明类型；实际值由请求产生。

| 方法及路径 | 请求示例 | 响应 |
| --- | --- | --- |
| `GET /api/v1/health` | 无请求体 | `{"status":"ok","simulator":"JS-ComputeSim-313"}` |
| `POST /api/v1/simulate` | `{"seed":313,"hours":24,"scenario":"high_renewable","strategy":"SuCompute","weights":{"carbon":0.8}}` | Replay，含 `kpis,hourly,daily,nodes,flights`。静态包另附可查样例 ID |
| `POST /api/v1/fault/inject` | `{"hours":4,"slot":18,"fault":{"city":"南京","kind":"capacity","severity":0.3,"duration_slots":12}}` | `{"fault":{…},"kpis":{…}}`，fault 与静态事件字段相同，场景和策略由请求给出 |
| `POST /api/v1/copilot/command` | `{"hours":2,"text":"碳排权重调至0.6"}`，或 `{"text":"注入南京30%算力故障"}`，或 `{"text":"解释调度","task_id":0}` | `{"action":{"kind":"weights","weights":{"carbon":0.6},"fault":null},"result":{…}}`。调权返回重算 KPI，故障返回事件和 KPI，解释返回 summary 和 evidence |

故障类型 `outage` 表示全节点离线，`capacity` 的 severity 表示损失比例，`pue` 的 severity 表示 PUE 数值增量。slot 为故障开始的五分钟槽。实测秒数包含计划重算、剩余预留释放、重新选址与切流/Checkpoint 编排。轨迹描述内存仿真中的剩余服务量与已保存进度，生产链路的 checkpoint 字节复制未计入。

### zicheng 的 Copilot 接入点

`TODO(zicheng): plug in LLM provider`。实现 `backend/copilot.py` 中的 `BaseCopilotAdapter.parse_command(text) -> SchedulingControlAction` 与 `explain_decision(attribution_payload) -> ExplanationResult`。在应用装配处注入 `app.dependency_overrides[get_adapter] = lambda: MyAdapter()`。默认依赖是纯本地确定性 `RuleBasedCopilotStub`。结构化动作和审计凭证已覆盖两端边界。`weights` 重新经 Simulation 数据校验，故障经 Injection 校验。静态站可直接显示已导出的结构化归因。
