# 离线证据审阅实现

## 检索与审计

`EvidenceIndex` 以来源原始引用、检索摘要和原文片段为索引字段，用 BM25 选择证据，并生成证据、来源和版本之间的 NetworkX 溯源子图。展示层使用原样引文和分级。排序分仅决定检索顺序。

`BaseLLMClient.assemble(query, records)` 是可替换接口。默认 `OfflineClient` 返回已选原文引文。`engine/llm_adapter.py` 预留 `TODO(zicheng): plug in LLM provider`。仓库所有者可通过 `create_app(snapshot, client=provider)` 或 `EvidenceService(snapshot, client=provider)` 注入实现。适配器提交 `Citation(evidence_id, dataset_version, text)`，所有输出均经过独立审计。运行时执行当前检索集合成员检查、整段原文一致性核验及有限的疗效承诺措辞过滤。缺乏通过核验的证据、版本不匹配或生成了改写文本的场景会显示待验证提示。固定措辞过滤仅覆盖列出的规则，专家继续审查原文的语境、相关性和科学适用性。

`T4_COMPUTATIONAL` 记录保持辅助证据分级。记录来自可信 release，审计只展示 release 中已经标注的等级。引用的形式完整性和数据发布者对来源的核验是两个环节。

## 演示与评测范围

`python -m benchmarks.export_demo` 通过本地 TestClient 执行研究方法问答、两组引文清点、专家处置与签批。命令报告指定引文 Top-1、通过检查的引用组数、签批导出结果及本次本地运行耗时。自动测试禁止外部 socket 连接与 DNS 查询。样例的 PubMed 来源为 [FAIR 指南（26978244）](https://pubmed.ncbi.nlm.nih.gov/26978244/) 和 [PRISMA 2020 声明（33782057）](https://pubmed.ncbi.nlm.nih.gov/33782057/)。

本分支的指标覆盖软件行为和两个方法学样例。赛题生物分析指标、人工 SOP 提效指标、重排/NLI 的训练与权重包均不在本次部分交付范围。
