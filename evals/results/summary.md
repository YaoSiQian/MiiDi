# 评测结果汇总

- 样本总数：46（有效 34，生成/评分失败 12）
- composite 总均值：42.6（R_rule 28.3，Judge 均值 64.1）

## Composite 分段分布

| 分段 | 样本数 |
|------|--------|
| 80–100 优秀 | 0 |
| 60–79 合格 | 6 |
| 40–59 勉强 | 10 |
| 20–39 较差 | 18 |
| 0–19 不可用 | 0 |

## 主客观相关性

- Pearson r(R_rule, J_mean) = **0.032**（n=34）

| 0–19 不可用 | 0 |

## 规则轴均值（0–100）

| 轴 | 均值 |
|----|------|
| harmony | 84.3 |
| voice | 69.6 |
| rhythm | 88.6 |
| structure | 71.2 |
| dynamics | 90.6 |

## 反退化门均值（乘数 0–1）

| 门 | 均值 | 最小值 |
|----|------|--------|
| repetition | 0.533 | 0.000 |
| density | 0.896 | 0.500 |
| balance | 0.738 | 0.400 |
| spread | 0.988 | 0.600 |
## 按风格分组

| 分组 | 样本数 | 生成失败率 | composite 均值* | R_rule 均值* | J 均值* | 门击穿** |
|------|--------|------------|-----------------|--------------|---------|----------|
| classical | 9 | 2 | 54.2 | 45.8 | 66.6 | 0 |
| jazz | 9 | 3 | 42.4 | 32.3 | 57.6 | 0 |
| lofi | 10 | 3 | 37.0 | 25.0 | 55.1 | 0 |
| pop | 11 | 4 | 47.9 | 32.8 | 70.6 | 0 |
| touhou | 7 | 0 | 31.4 | 6.0 | 69.5 | 2 |

\* 均值仅计入完成样本（生成失败样本的 0 分不摊入均值，失败单列）。
\* 门击穿：任一反退化门乘数 ≤ 0.05 的样本数（R_rule 被乘法门大幅压制）。

## 按样本类别分组

| 分组 | 样本数 | 生成失败率 | composite 均值* | R_rule 均值* | J 均值* | 门击穿** |
|------|--------|------------|-----------------|--------------|---------|----------|
| adversarial | 12 | 3 | 42.0 | 31.5 | 57.6 | 1 |
| basic | 20 | 6 | 42.7 | 25.2 | 69.1 | 0 |
| constraint | 8 | 1 | 43.0 | 28.3 | 65.2 | 0 |
| hard | 6 | 2 | 42.7 | 31.9 | 58.8 | 1 |

\* 均值仅计入完成样本（生成失败样本的 0 分不摊入均值，失败单列）。
\* 门击穿：任一反退化门乘数 ≤ 0.05 的样本数（R_rule 被乘法门大幅压制）。

## 失败样本

| 样本 | 错误 |
|------|------|
| constraint_04 | generation failed |
| hard_03 | generation failed |
| hard_04 | invalid composition |
| jazz_basic_01 | generation failed |
| jazz_basic_02 | generation failed |
| jazz_basic_04 | generation failed |
| pop_basic_01 | generation failed |
| pop_basic_02 | generation failed |
| pop_basic_03 | generation failed |
| adversarial_09 | invalid composition |
| adversarial_10 | generation failed |
| adversarial_12 | generation failed |
