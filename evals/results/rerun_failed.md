# 首轮失败样本重测

首轮（主结果表）保持原样计入；本表用于失败归因：`recovered` = 瞬时故障，`failed again / invalid` = 持续失败模式（detail 为阶段日志/违规摘要）。

| 样本 | 风格 | 重测结果 | R_rule | J 均值 | composite | 音符数 | detail |
|------|------|----------|--------|--------|-----------|--------|--------|
| constraint_04 | lofi | recovered | 16.7 | 65.3 | 36.1 | 294 |  |
| hard_03 | pop | failed again | 0.0 | 0.0 | 0.0 | 0 | composed Lead | composed Bass | core failed: LLM call failed after retries: no c |
| jazz_basic_01 | jazz | recovered | 52.6 | 46.3 | 50.1 | 486 |  |
| jazz_basic_02 | jazz | recovered | 71.4 | 47.7 | 61.9 | 565 |  |
| jazz_basic_04 | jazz | failed again | 0.0 | 0.0 | 0.0 | 0 | plan: brief ok | core failed: LLM call failed after retries: no content in messa |
| pop_basic_01 | pop | failed again | 0.0 | 0.0 | 0.0 | 0 | plan: brief ok | core failed: LLM call failed after retries: invalid JSON in rep |
| pop_basic_02 | pop | recovered | 0.0 | 75.0 | 30.0 | 1697 |  |
| pop_basic_03 | pop | recovered | 11.1 | 81.0 | 39.1 | 1073 |  |

**重测结论**：5/8 重测成功（瞬时故障率 3/8 为持续失败）。
