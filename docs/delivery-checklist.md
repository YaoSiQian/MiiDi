# 交付清单

任务书交付项 → 对应文件的一页式索引，评审可按表直接定位材料。复现路径：`pip install -e ".[dev]"` → 配置 LLM（见 [README 快速开始](../README.md#2-配置-llm)）→ [README「运行评测」](../README.md#运行评测)三条命令。

## ① 应用侧（用户 / 问题 / LLM 必要性）

| 交付项 | 文件 |
|--------|------|
| 场景选择与 LLM 必要性论证 | [docs/report.md §1](report.md) |
| Web 应用（生成 / 评估 / 修订全流程） | `src/miidi/web/`（FastAPI 后端）、`web/`（Vite 前端） |
| CLI | `src/miidi/cli.py`（`python -m miidi ...`） |
| Docker 部署 | `Dockerfile`、`docker-compose.yml` |
| 架构与设计取舍 | [docs/architecture.md](architecture.md)、[docs/pipeline.md](pipeline.md) |

## ② 评估方法设计

| 交付项 | 文件 |
|--------|------|
| 评估方法总述（六轴 / 四道门 / 三维 Judge / 合成分） | [docs/evaluation.md](evaluation.md) |
| 维度设计依据与权重 | [docs/report.md §3](report.md) |
| 规则轴实现 | `src/miidi/eval/axes.py` |
| 反退化门实现 | `src/miidi/eval/gates.py` |
| Judge 轨实现（锚点 / 清单 / 证据要求） | `src/miidi/eval/judge.py` |
| 合成分实现 | `src/miidi/eval/composite.py` |

## ③ 评测样本

| 交付项 | 文件 |
|--------|------|
| 46 个样本（basic ×20 / constraint ×8 / hard ×6 / adversarial ×12，覆盖 5 曲风） | `evals/samples/*.yaml` |
| 样本集设计说明 | [docs/report.md §4.1](report.md) |
| 样本 schema 与类别划分 | `evals/schema.py` |

## ④ 有效性验证

| 交付项 | 文件 |
|--------|------|
| E1 区分度（四种规则轨退化） | `evals/experiments/e1_discrimination.py` |
| E1b 三档生成样本判别力（原始/轻度/重度） | `evals/experiments/e1b_tiers.py` |
| E2 确定性 | `evals/experiments/e2_consistency.py` |
| E2-Judge 评委轨重复一致性 | `evals/experiments/e2_judge_consistency.py` |
| E3 对抗性 | `evals/experiments/e3_adversarial.py` |
| E4 异构 Judge | `evals/experiments/e4_hetero_judge.py` |
| E5 无害变形不变性（IVR） | `evals/experiments/e5_invariance.py` |
| 人工听感对照（单标注者初步） | `evals/runners/human_correlation.py` + `human_ratings.jsonl` |
| 实验结果 | [evals/results/experiments.md](../evals/results/experiments.md)、[docs/report.md §5](report.md) |
| 失败样本重测归因 | [evals/results/rerun_failed.md](../evals/results/rerun_failed.md) |

## ⑤ 评测执行与交付物

| 交付项 | 文件 |
|--------|------|
| 全量评测结果表（46 样本，含拦截层标签列） | [evals/results/results.csv](../evals/results/results.csv) |
| 可读版结果与汇总 | [evals/results/results.md](../evals/results/results.md)、[evals/results/summary.md](../evals/results/summary.md) |
| 逐样本原始产物（composition / rule_report / judge_report / MIDI） | `evals/results/<sample_id>/` |
| 分析报告（结果 / 结论 / 失败模式 / 典型模式 / 局限） | [docs/report.md §6–§10](report.md) |
| Demo 录屏 + 成品音频 | [README「Demo」区块](../README.md#demo)、`docs/img/web-demo.avif`、`docs/img/web-demo.mp3` |
| 测试套件（LLM 全 mock，无需 API key） | `tests/` |
