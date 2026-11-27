# 流盾智研离线检索及轻量文本模型

AI-HEALTH-Q40 流感病毒免疫原辅助设计智能体研发和应用是官方赛题。本分支按照新版 YOU-275、YOU-276 交付科研方法学资料管理、文本检索、引文忠实度审计和专家复核。资料治理评分只反映输入档案的完备情况。

## 检索和审计

三条召回路分别为 BM25、384 维本地稠密向量余弦、NetworkX 1–3 跳图谱召回。向量使用词项归一、有限通用同义词映射和经过符号哈希的词／字符三元组。图谱使用 Document、Topic、Evidence、Snapshot 四类节点。检索将三路名次通过 RRF 融合，再用训练后的文本相关性概率参与重排。精确引用 ID 匹配优先。报告保留召回路名次、图跳数及文本匹配概率。

两个分类器共享 12 项可核查特征，包含词覆盖/重叠、局部稠密余弦、字符三元组、长度、整句匹配、否定、数字和词序。单隐层 24 单元，`reranker` 有 362 个参数，`nli_auditor` 有 387 个，输出 ENTAIL、CONTRADICT、UNSUPPORTED 的概率。 `weights/manifest.json` 记录类别、特征、数据指纹、参数、验证集选定轮次、分项指标、权重字节数和 SHA256。

`UncertaintyAuditAgent` 执行引用元组和整段原文的硬核验，并用 NLI 提供附加文本忠实度信号。只有当前批准快照内的原样引文可以作为发布事实。NLI 预测无法替代快照和原文核验。 `method_differences` 展示同主题文献对及专家待复核信号，来源对照仍需人工判断。 `engine/llm_adapter.py` 保留 `TODO(zicheng): plug in LLM provider`。当前 `OfflineClient` 原样组装引文，所有输出均过相同的硬核验。后续所有者可通过 `create_app(snapshot, client=provider)` 注入本地适配器。

## 数据拆分和复现

训练、验证、测试用明确标注的合成通用文本；领域词表与句式模板按 split 隔离，脚本检查不同 split 的完整文本对无交集。验证集决定训练停止点和排序器诊断二分类阈值。五条 PubMed 方法学标题和一条显式合成资料用于独立软件评测，模型训练不读取公开方法学快照。来源核验及内容性质见 [发行锁](tests/fixtures/release.lock.json)。

实测环境为 Windows、Python 3.13，核心依赖为 `torch 2.7.0+cpu`、`numpy 2.2.4`、`onnx 1.18.0`、`onnxruntime 1.21.1`、`networkx 3.4.2`、`pydantic 2.13.4`、`pyarrow 24.0.0`、`fastapi 0.115.12`、`httpx 0.28.1`、`pytest 9.0.3`。使用已安装依赖的环境，或从本地 wheel 目录离线安装。可选 HTTP 服务另需 uvicorn。

```bash
python -m benchmarks.train_weights
python weights/verify_weights.py --report weights/verification.json
python -m benchmarks.export_demo
python -m benchmarks.evaluate_tasks --report benchmarks/software_evaluation.json
python -m pytest -q
```

验证器对四个权重文件逐项核对哈希和大小，检查 ONNX 结构，并在同一批合成留出样本上对照 PyTorch／ONNX 的 logits 与分类结果。CPU 耗时为模型单样本的热运行中位数；软件评测单独统计本地 TestClient 延迟。评测和测试会阻断外部连接与 DNS，允许 Windows asyncio 本地回环。

[合成模型测试指标](weights/manifest.json) 中重排器的 NDCG@3 为约 0.969，同时二分类诊断漏掉了全部留出正类，故使用排序概率，不使用二分类阈值做准入。NLI 三类的合成样本宏平均 F1 为 1.000，样例规则简单，不能据此推定真实自由文本泛化。 [端到端软件指标](benchmarks/software_evaluation.json) 和 [数值一致性报告](weights/verification.json) 分开记录。人工 SOP 基线未测，软件指标用于核验资料审阅流程。
