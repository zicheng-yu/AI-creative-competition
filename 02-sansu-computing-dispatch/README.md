# JS-ComputeSim-313

江苏「1+13」与长三角异构算网的小时级仿真基准，对应赛题 `AI-JIANGSU-Q36` / Linear `YOU-268`。Gymnasium 环境，确定性种子，参数在 `configs/`。

数据里哪些是公告原文、哪些是假设，写在 [docs/DATA_CONSTRUCTION.md](docs/DATA_CONSTRUCTION.md)。本目录不包含 Alibaba / Helios / Philly 原始 Trace。

## 运行

```bash
cd 02-sansu-computing-dispatch
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/run_baselines.py --seed 313
python scripts/download_traces.py          # 只打印公开仓库地址
python scripts/sample_traces.py            # 没有下载到 CSV 时直接退出
```

## 环境

```python
from js_computesim import JSComputeSimEnv, run_episode

env = JSComputeSimEnv("weekday")  # green_surplus | peak_conservation | node_failure
obs, info = env.reset(seed=313)
snap = env.planning_snapshot()    # MILP 读这一份
obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
```

- 一步 = 1 小时，一局 = 168 步（7 天）。第 1 天是 hours 0–23，第 4 天是 hours 72–95。
- `terminated` 恒为 `False`。168 步结束时 `truncated=True`。
- `info["cost"]` 是本小时错过截止期的参考 EFlops（最后一步含未完成积压），给 Safe-RL 做拉格朗日代价。电费和碳排在 `info["metrics"]`。
- `info["metrics"]` 是本小时原始量：`served_eflops`、`arrived_eflops`、`violated_eflops`、`energy_kwh`、`carbon_kg`、`cost_cny`、`green_kwh`、`cross_domain_eflops` 等。

### 动作

默认动作空间是 `Box(0, 1)`，形状 `(5 tasks, 16 nodes, 6 pools)`。`step` 把任意非负张量当权重（脚本策略可以不先归一化）。大于 1 的分量在环境里按比例使用，不视为非法。

环境对每个来源城市单独套时延 SLA：推理默认 5 ms，只能留在江苏城市节点；预训练 / 微调 / 超算默认 10 ms，可以进沪、浙、芜湖。不可行目的地的权重被丢掉，**不会**自动改派到别的节点。显式 MILP 方案可以用形状 `(task, origin, dest, pool)` 的数组调用 `step`，每个来源保留自己的权重。

任务顺序：`pretrain, finetune, inference, hpc, general`。  
节点顺序见 `env.node_ids`（统计局表顺序的 13 市，然后上海、浙江、芜湖）。  
芯片池：`cpu, ascend, cambricon, hygon, nvidia, hpc`。

有效吞吐：`参考 EFlops ≤ 占用的铭牌 EFlops × η[k,m] × operator_gain[k,m]`。

### 观测

`obs` 是裁剪到 `[0, 5]` 的 `float32` 向量，给策略网络用。队列、未来到达、电价、绿电、健康度和系数的未裁剪值在属性和 `planning_snapshot()` 里。`env.observation_layout["slices"]` 给出各段下标。

### MILP 快照

`planning_snapshot()` 在 `reset` 之后可调用，包含当前队列、剩余时域的到达预测（本基准里预测等于生成器真值）、`nameplate_eflops`、`eta`、`operator_gain`、`latency_ms`、`health`、`price_cny_per_kwh`、`green_available_mw`、`carbon_kg_per_kwh`、`pue_base`。`arrivals_eflops` 不含已经放进队列的当前小时；当前小时在 `queue_eflops`。

碳排因子默认用同一份 2022 年公告里的省级因子（`carbon_factor_mode="provincial"`）。`carbon_factor_mode="east_china"` 时所有节点都用华东 0.5617 kgCO₂/kWh。

## 四个场景

| id | 标签 | 与常规工作日的差别 |
| --- | --- | --- |
| `weekday` | 常规工作日 | 夏季电价，基准绿电签约，无故障，周六日略降负载 |
| `green_surplus` | 绿电大发日 | 风光容量因子 ×1.6、签约比例 ×1.5（均为假设旋钮） |
| `peak_conservation` | 尖峰保电日 | 推理负载加重，高峰/尖峰时段江苏城市铭牌 ×0.8，电价仍是 2025 年 8 月公告价 |
| `node_failure` | 节点故障压测 | 第 4 天南京下线，苏州 PUE ×1.35 |

## 基线

`run_episode(scenario, policy, seed)`，`policy` 为 `random` 或 `greedy`。贪心按「有效吞吐 / 上一小时池利用率」铺开，不看电价。种子同时决定到达序列和随机策略的动作。

结果表见 `results/baseline_seed313.md`。
