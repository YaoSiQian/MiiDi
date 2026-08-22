# MiiDi 设计文档：基于 LLM 的符号音乐生成与评估系统

日期：2026-08-22
状态：待审阅

---

## 0. 背景与场景定义

### 0.1 赛题映射

本任务属于赛题方向「复合型产物评估」（由多步流程产出内容的质量评估），具体场景为**符号音乐生成（MIDI）**：输出不存在唯一标准答案，评判标准需自行设计并通过实验验证有效性。

### 0.2 目标用户与待解决问题

- **目标用户**：无编曲软件使用经验、但有音乐表达需求的爱好者（想给歌词配 demo、给短视频配乐、把脑内旋律变成可播放文件的人）；以及需要快速试听不同风格编曲方案的音乐学习者。
- **待解决问题**：传统 DAW 学习成本高；现有文本生成音频模型（Suno 等）不可编辑、不可检视内部结构。符号音乐（MIDI）是**可检查、可修改、可解释**的中间产物——用户能看到每个音符并逐轨修改。
- **LLM 必要性**：用户以自然语言描述风格与意图，映射到调性/和声进行/结构/配器的组合空间是指数级的且高度依赖乐理知识；该映射无法用规则穷举，正是 LLM 世界知识的用武之地。

### 0.3 需求决策记录（澄清结论）

| 决策点 | 结论 |
|--------|------|
| 应用形态 | Web 应用为主；评测保留纯脚本入口 |
| LLM 接入 | 单一第三方模型，OpenAI Responses 协议；`env.example` 预留 base_url / api_key / model |
| 曲风范围 | 流行、古典、爵士、Lo-Fi、东方 Project（五曲风 skill） |
| 多轮深度 | 内部多阶段流水线 + 会话式自然语言修改；评测只针对最终产物 |
| 人工标注资源 | 仅本人 → 一致性验证以多次评估波动为主，单人标注作参考 |
| 评测规模 | 小规模：约 36 prompt × 1 份生成；判别力用程序化降级构造 |
| 前端风格 | system.css（System 6 复古 Mac）多窗口桌面，极简 |

---

## 1. 参考项目分析结论

### 1.1 tubone24/midi-agent-skill（生成侧）

三层架构：SKILL.md 工作流指令 → resources 乐理文档渐进披露 → Python 渲染脚本。
**借鉴**：LLM 输出与渲染层分离、normalize 校验层、理论资源按需加载。
**缺陷与本项目的改进**：

| 缺陷 | 改进 |
|------|------|
| 音符顺序累加 `time += duration`，无休止符、无绝对时值 | 绝对 tick 网格 `[onset, dur, pitch, velocity]` |
| velocity 固定 100 | 显式 velocity 维度 |
| 轨道内无和弦 | 同 onset 多 pitch 支持 |
| `parse_duration` 非法值静默回退 | normalize/validate 分离，错误显式暴露 |
| 无拍号/小节概念、鼓轨被跳过不用 | 拍号声明 + GM ch10 打击乐映射表 |
| >9 轨 channel 碰撞 | renderer 自动分配并单测覆盖 |

### 1.2 Tencent-Hunyuan Hyra music（评估侧）

约 3000 行确定性评分器：硬约束门（ValueError 绝不静默）→ 加权轴 → 反退化乘法门。
**借鉴**：「轴加权 × 门乘法」聚合结构；梯形带原语 `_band()`（"越多越好"量两头都罚）；PC-set 和弦分类器；sustain-aware 纵向切片；128 GM program 音域双带（PLAY/COMF）；归一化熵。
**差异**：HYRA 是固定旋律的编曲优化（scorer 兼作搜索目标函数）；本项目是开放 prompt 的创作生成，评估器用于质量度量与应用内自评环，不做退火搜索。

---

## 2. 方案选型记录

三案对比后选定**方案三：分层流水线，evaluator 内嵌自评环**。

```
用户prompt + 曲风skill包
  ↓ ① Plan 规划        LLM 产出音乐简报（meta+structure+harmony+配器表）
  ↓ ② Compose 分轨创作  每轨独立调用 LLM 写音符（绝对tick网格），依赖顺序串行
  ↓ ③ Self-review      规则评估器打分→违规清单回喂 LLM 定点patch单轨（≤2轮）
  ↓ ④ Render           validate通过 → MIDI → WAV(可选)
会话式修改 = 带原产物与反馈重跑对应阶段函数
```

否决理由摘要：全曲直出（方案一）长 JSON 出错率高、跨轨对齐靠心算、评估与应用脱节；计划+规则展开（方案二）创造性上限=规则库上限，偏离 LLM 应用考察点。方案三每调用只处理一条轨（上下文短、错误率低）、评估内核在应用内有真实消费者、分阶段产物天然支持归因分析。

---

## 3. 总体架构

核心原则：**kernel 是纯 Python 包，零 Web 依赖**；Web 后端与评测脚本都是 kernel 的调用方——评测评的就是应用真正运行的逻辑。

```
MiiDi/
├── src/miidi/
│   ├── schema/          # model.py(pydantic) normalize.py(宽容修复) validate.py(硬约束)
│   ├── render/          # midi.py(midiutil) audio.py(FluidSynth,可选)
│   ├── eval/            # 规则轴实现 axes/ gates.py score.py
│   ├── llm/client.py    # OpenAI Responses 协议客户端
│   ├── skills/loader.py # 曲风知识包加载器
│   ├── pipeline/        # plan.py compose.py revise.py orchestrator.py
│   └── web/             # FastAPI 应用
├── webapp/frontend/     # Vite + vanilla JS + system.css
├── skills/{pop,classical,jazz,lofi,touhou}/   # 曲风知识包
├── evals/
│   ├── samples/         # 样本 YAML
│   ├── runners/         # run_eval.py 等
│   ├── experiments/     # E1判别力/E2一致性/E3对抗性
│   └── results/         # 表格与报告产物
├── docs/                # 分析报告、评估方法说明
├── env.example          # OPENAI_BASE_URL / OPENAI_API_KEY / MODEL_NAME
└── tests/
```

---

## 4. 数据模型：Composition Schema

```jsonc
{
  "meta": { "title": "...", "bpm": 120, "time_signature": [4,4],
            "key": {"tonic_pc": 0, "mode": "major"}, "style": "pop" },
  "structure": [
    {"name": "intro", "start_bar": 0, "bars": 4},
    {"name": "verse", "start_bar": 4, "bars": 8}
  ],
  "harmony": [                                   // 规划阶段声明的和弦时间线
    {"bar": 0, "dur_bars": 1.0, "symbol": "C"},
    {"bar": 1, "dur_bars": 1.0, "symbol": "Am7"}
  ],
  "tracks": [{
    "name": "Lead", "program": 73, "role": "melody",
    "notes": [[onset_tick, dur_tick, pitch, velocity], ...]
  },
  { "name": "Drums", "is_drum": true, "role": "drums",
    "notes": [[0, 120, 36, 100], ...] }          // GM 打击乐映射，ch10
  ]
}
```

关键决策：

1. **绝对整数 tick 网格，ppq=480**：16 分音符=120、三连音八分=160、32 分=60 全为整数，无浮点漂移；休止符=音符间的空隙；跨轨对齐零心算。爵士摇摆用显式 tick 偏移表达（如 200/160 拆分八分音符）。备选 ppq=96 或固定 16 分网格因无法无损表达三连音被否决。
2. **四元组紧凑数组**而非对象：长曲单轨数百音符省约一半 token；normalize 层同时接受 `{pitch,duration}` 对象写法。
3. **显式 harmony 层**：使「音符是否支撑声明的和弦」可机检——证据可追溯性的直接落点，也是对抗「术语堆砌」作弊的检测面。
4. **显式 structure 层**：段落边界成为发展性度量的坐标系。
5. **pitch 用 MIDI 整数**：消除 "F#5" 字符串解析歧义；normalize 兼容科学音名输入。
6. **normalize 与 validate 职责分离**：normalize 尽力修复格式瑕疵（字符串转 int、对象转数组、缺省 velocity 补 96）；validate 只查硬约束且失败必报定位明确的错误（轨名/小节/音符索引），绝不静默降级。

---

## 5. 生成流水线与曲风 Skills

### 5.1 四阶段

**① Plan**：输入用户 prompt + 曲风 skill 包。输出音乐简报：meta（调性/BPM/拍号）+ structure（段落表）+ harmony（和弦时间线）+ 配器表（每轨 role/name/program/职责描述/依赖顺序）。校验：schema + 音乐性快检（和弦符号可解析、段落连续无缝隙无重叠、BPM 在风格参考区间内）。矛盾请求（如 300BPM 摇篮曲）在此阶段返回解释性拒绝或降级建议。

**② Compose**：按配器表的依赖顺序（典型：melody → bass → chords → drums → color）逐轨调用 LLM。注入上下文 = 简报 + 该轨职责说明 + skill 相关理论片段 + 已完成轨必要信息（chords/bass 轨拿到 melody 完整音符作支撑依据；color 轨只拿逐小节 pitch-class 摘要控制 token）。每轨输出即 normalize+validate，失败带报错重试 ≤2 次。

**③ Self-review**：`miidi.eval` 对整曲打分 → 结构化违规清单回喂 LLM 定点 patch 单轨（不重写全曲）。默认 ≤2 轮，每轮分数轨迹入档。

**④ Render**：validate 通过 → MIDI 文件 → WAV（FluidSynth 可选）。

**关键约束**：③ 使用的评估内核与评测脚本为同一份代码（`miidi.eval`）——应用内自评环是评估方法的真实消费者。

### 5.2 会话式修改

用户反馈（"贝斯太闷""副歌换进行"）→ 分类定位目标层（meta/structure/harmony/某轨）→ **带原产物+反馈重跑对应阶段函数**。修改不另写逻辑，即流水线阶段的带参重入。每次改动存版本快照（JSON 文件），支持回滚。

### 5.3 曲风 Skill 包

```
skills/<style>/
├── SKILL.md          # 风格定义 + 各阶段应读取哪个文件的指引
├── instruments.md    # 配器惯例、GM program 推荐、音域注意
├── harmony.md        # 和弦语汇、特征进行、终止式
├── rhythm.md         # 节奏特征、鼓 pattern 库（tick网格模板）
└── defaults.json     # BPM 区间、结构模板、密度参考带
```

五曲风定位：流行（基准，四大件/I-V-vi-IV 语汇）、古典（功能和声严格/终止式/无鼓）、爵士（ii-V-I/七九和弦/walking bass/swing tick 偏移——难例来源）、Lo-Fi（maj7/min9/70-90BPM/慵懒 swing 鼓组——鼓轨+动态评估场景）、东方 Project（150-190BPM/小号主旋律/快速钢琴琶音/副歌高密度——高速高密度正确性挑战）。

### 5.4 LLM 客户端

OpenAI Responses 协议（`{base_url}/responses`）。优先 json_schema 受限输出；不支持则自由文本 + normalize 修复。指数退避重试、超时、JSON 提取统一封装于 client，流水线代码不感知。配置仅来自环境变量（env.example：`OPENAI_BASE_URL` / `OPENAI_API_KEY` / `MODEL_NAME`）。

---

## 6. 评估体系

### 6.1 双轨架构与设计依据

```
Composition JSON ──┬─ 规则轨：六个确定性轴 → 加权和 → 反退化门乘法 → R_rule ∈ [0,100]
                   │    （可复现、零 API 成本、无法靠话术骗分）
                   └─ Judge轨：LLM-as-judge ×3 维，rubric 锚点化 + 证据引用
                        （覆盖规则无法触及的风格与美学维度）
```

两轨互不重叠计分：judge 不复判规则可判事项，规则不越界评主观维度。规则指标作为客观证据注入 judge prompt（降低幻觉），但 judge 分数独立报告。

### 6.2 规则轨六轴（可操作判定标准）

**A1 格式规范性**：validate() 通过与否 + 违规计数（音符越界曲长、轨内重叠、pitch∉[0,127]、velocity∉[1,127]、非整数 tick、program∉[0,127]、鼓轨未走打击乐映射）。完全不可解析 → INVALID 标记，R_rule=0。

**A2 和声正确性**：(a) 音阶符合度——非调外 PC 占比（弱拍经过音豁免清单）；(b) 和弦支撑度——逐小节 sounding PC 集合 vs harmony 层声明：bass/chords 轨和弦音占比 ≥80% 为满分带、旋律轨容忍色彩音；(c) 小二度簇纵向占比 <5%；(d) 终止式存在性（段落尾 V→I 或变格进行检出）。同时承担**专业术语正确性**：和弦符号必须可解析且与实际音高集一致——「声明-实际背离」直接扣分。

**A3 声部写作质量**：(a) 音域适配——每轨落在该 program PLAY 带 ≥95%、COMF 带 ≥70%（内置全部 128 GM program 双带表）；(b) 平行五八度检出计数 =0 为满分带；(c) 同轨相邻跳进 >P8 占比 <10%；(d) bass-melody 注册分离度带。

**A4 节奏律动**：(a) 网格吸附率——onset 满足「存在 k∈{1,2,3,4,6,8,12} 使 onset×k ≡ 0 (mod 480)」的比例（即从全音符到三十二分音符及三连音细分的并集；离格白名单：爵士 swing 偏移模板，如八分拆分为 200+280）；(b) 每轨密度梯形带（对照 skill defaults.json 的风格参考带）；(c) 鼓 pattern 匹配——kick/snare/hat 相对拍位与 skill 模板库的容差匹配率；(d) swing 一致性——同段落内偏移量方差有界（随机偏移 ≠ 律动）。

**A5 结构与发展性**：(a) structure 层无缝隙无重叠覆盖实际音符范围；(b) 段落间相似度矩阵落带——重复段相似度 >0.7 且对比段 <0.9（梯形带，两头罚：全同=复读，全异=散架）；(c) 密度轮廓有形状（逐段 note/bar 方差在带内）；(d) 动机再现可检出（首段旋律轮廓序列在后续段落匹配）。

**A6 动态表现力**：(a) 全曲 velocity 分布带——恒定值（σ≈0）罚，随机抖动同样罚（方向性检查：相邻小节 velocity 序列的自相关）；(b) 段落梯度——副歌均值 ≥ 主歌（与 structure 对照）。

聚合：`R_rule = 100 × Σ(wᵢ·Aᵢ) × ΠGⱼ`，权重固定公开（A2:0.30, A3:0.20, A4:0.20, A5:0.20, A6:0.10；A1 为资格门不计权）。

### 6.3 反退化门（乘法，防刷分脊柱）

每个"越多越好"量均为梯形带处理，退化策略压到地板分而非线性扣分：

- **G_repetition**：单轨 n-gram 自复制率过高压分（反「复读凑篇幅」）
- **G_density**：轨密度梯形带的极端端惩罚（反「十六分轰炸刷复杂度」与空洞敷衍）
- **G_balance**：轨间内容失衡——某轨仅几拍糊弄（反「凑轨数」）
- **G_spread**：假宽注册检测——孤立高音撑 spread（反「表面丰富」）

门的触发明细随结果输出，供对抗性实验直接引用。

### 6.4 Judge 轨三维（LLM-as-judge）

- **J1 风格符合度**：对照曲风 skill 显式列出的 6-8 条风格特征清单逐条 yes/partial/no + 引用轨名与小节证据；BPM 区间、配器家族等规则特征作为证据注入但不由 judge 重算。
- **J2 提示遵循度**：显式要求（BPM 数值/指定乐器/时长/调性）由规则精确核对该部分；意象类要求由 judge 三值判定（satisfied/violated/unaddressed）+ 证据引用。
- **J3 整体音乐性**：锚点 rubric 1-5 分——1=无法成曲；2=能播放但错误密集；3=成立但平淡或局部硬伤；4=连贯有起伏；5=结构清晰且有记忆点。每档附具体可查特征描述。

Judge 分数量纲统一（供 §6.5 合成）：J1 逐条 yes=100/partial=50/no=0 取均值；J2 satisfied=100/unaddressed=50/violated=0 取均值；J3 = (原始分−1)/4×100。报告同时呈现原始判定与归一化值。

Judge 约束：温度 0；结构化 JSON 输出 `{score, per_item, evidence[]}`；evidence 必须引用轨名+小节号（人工可抽查）；多样本评测时随机呈现顺序防位置偏差。已知局限如实写入报告：生成与评判同模型存在自偏好风险，缓解手段 = judge 只管主观维度 + rubric 锚点客观化 + 规则轨承担全部客观判定。

### 6.5 合成分与安全合规说明

排序用 composite = `0.6·R_rule + 0.4·mean(J1,J2,J3)`（权重公开固定）；所有实验同时报告逐维分数，不掩盖维度间分歧。

安全合规维度在本场景的映射：不设独立评分轴；以 (a) prompt 层版权提示（不模仿在世作曲家具体作品旋律）、(b) 报告中讨论符号生成的版权边界、(c) 反例请求的优雅拒绝来覆盖，并在报告中说明此取舍理由。

---

## 7. 评测样本集（约 36 prompt）

| 类型 | 数量 | 构造方式 | 作用 |
|------|------|---------|------|
| 基础题 | 20（每曲风4） | 手写种子 prompt（情绪/场景描述，少显式约束）+ 2 题改编真实歌曲风格描述（只借描述不借旋律） | 常规覆盖 |
| 显式约束题 | 8 | 指定 BPM/乐器/调性/时长的组合 | J2 规则核对精确靶子 |
| 难例 | 6 | 爵士全曲 ii-V-I、东方高 BPM 副歌、多约束叠加（转调+指定结构+时长）、边界值（4 小节/单轨极简） | 能力边界探测 |
| 反例 | 2-4 | 矛盾/不可行请求："300BPM 的舒缓摇篮曲"、"3/4 与 4/4 同时" | 优雅降级检验 + 评估器不被表面完成欺骗 |

样本文件统一 YAML schema（id/style/prompt/constraints/expectations）。构造流程：手写种子 → LLM 辅助扩充措辞变体 → 人工终审入库；来源与方式写入报告。**含难例与反例，不只保留易得分子集。**

---

## 8. 有效性验证实验

### E1 判别力验证（好/中/差三档）

- 好档 = 含自评环最终输出；中档 = 跳过阶段③的直接产物（修订前版本，零额外成本）；差档 = 程序化降级算子：(a) 旋律调内随机重排 (b) 删 bass 或鼓轨 (c) onset 随机扰动破坏网格 (d) 首小节复读填满。
- 判定：composite 三档严格单调（好>中>差）；**归因校验**——每个降级算子应精确打击对应轴（删 bass 主打 A2/A3 而非 A5），归因错位即暴露评估器缺陷。报告 Spearman/Kendall 排序系数。

### E2 一致性验证

- 评估稳定性：同一输出重复评估 k=3 → 逐维极差与标准差；规则轨确定性复跑零方差作对照基线。
- 人机一致性：抽 ~12 输出，本人按同一 rubric 盲评（隐藏机器分）→ Spearman 相关 + 逐维偏差分析。单人标注统计局限如实声明，效力由 E1 补足。

### E3 对抗性验证（赛题加分项）

| 作弊策略 | 对应人类刷分行为 | 应被拦截于 |
|----------|----------------|-----------|
| 好曲复读×2 扩篇幅 | 堆篇幅 | G_repetition + A5 |
| 十六分音符填满一切 | 假装复杂 | G_density + A4 |
| harmony 层写高级和弦但音符不支持 | 术语堆砌/伪造引用 | A2 声明-实际背离 |
| velocity 恒定 127 | 表面力度 | A6 分布带 |

预期：所有对抗变体得分 ≤ 原版。任何失效 = 发现评估漏洞，修补并记录迭代过程（本身即报告素材）。E3 固化为常驻回归测试。

### 评测执行产出

36 样本全量跑一次 → 总表（样本 × 九维 + R_rule + composite）CSV+Markdown → 典型 case 归因 3-4 个（高分拆解、一个真实失败模式、一个反例优雅降级、一个对抗攻防）。全程 `python -m evals.runners.run_eval --samples ... --out ...` 单命令可复现。

---

## 9. Web 应用

### 9.1 后端 API（FastAPI）

```
POST /sessions                    {prompt, style} → 创建创作会话
GET  /sessions/{id}/status        各阶段进度 + 自评环分数轨迹
GET  /sessions/{id}/composition   当前版本 JSON
GET  /sessions/{id}/audio         WAV（FluidSynth 服务端渲染；缺失返回501）
GET  /sessions/{id}/midi          MIDI 下载
POST /sessions/{id}/revise        {feedback} → 定位层重生成
GET  /sessions/{id}/versions      版本历史；POST /sessions/{id}/versions/{v}/rollback 回滚
POST /sessions/{id}/evaluate      当前版本即时评估报告
```

进度推送用轮询（YAGNI，不上 WebSocket）。会话状态持久化为文件系统 JSON 快照（版本历史即快照序列，单机应用不引入数据库）。

### 9.2 前端：麦金塔复古多窗口桌面

技术栈：Vite + vanilla JS + `@sakun/system.css`（纯 CSS 组件库，MIT）+ 自写约百行窗口管理器（标题栏拖拽、点击置焦 z-index、折叠）。

菜单栏置顶（会话名 + File/Session 操作）。四个窗口：

| 窗口 | 内容 | 对应 API |
|------|------|---------|
| Composer | prompt 输入、五枚曲风图标按钮、Generate、四阶段进度条 | POST /sessions, GET status |
| Piano Roll | canvas 多轨音符网格渲染（按轨着色）、播放/停止传输条 | GET composition + audio |
| Evaluator | 各轴/Judge 分数条形图 + 违规明细列表（轨/小节定位）+ 自评环分数轨迹 | POST evaluate |
| Feedback | 自然语言反馈输入框 + 版本时间线（点击回滚） | POST revise, GET versions |

极简原则：四窗口固定初始位可拖动、不做 resize（System 6 本就不缩放）；单色灰阶基调，piano-roll 音轨着色为唯一彩色元素；无弹窗对话框，错误以窗口内 status bar 文本呈现。

---

## 10. 错误处理

| 故障 | 策略 |
|------|------|
| LLM 返回坏 JSON | normalize 修复 → 失败带报错重试 ≤2 → 仍失败该轨置空并显式警告（绝不静默） |
| validate 硬约束失败 | 结构化错误对象（轨/小节/音符定位）→ 作为自评环修订输入 |
| FluidSynth 未安装 | 音频端点 501，MIDI 不受影响（fail-soft） |
| LLM API 网络/超时 | 指数退避 ≤3 次，超限返回已完成的部分产物 |
| 矛盾/不可行 prompt | Plan 阶段校验拦截 → 解释性拒绝或降级建议（LLM 生成解释文案） |

---

## 11. 测试策略（pytest）

- **schema 层**：合法/非法输入矩阵（覆盖参考仓库全部踩坑模式：非法 duration、轨内重叠、越界 pitch、字符串混输）
- **评估器 golden tests**：手工小型 Composition 断言各轴精确分数；确定性断言（复跑 bit-exact——直接支撑赛题可复现要求）
- **渲染 round-trip**：mido 读回比对 MIDI 事件；channel 分配含 >9 轨边界
- **LLM client mock**：重试/退避/JSON 降级路径全覆盖，不发真实请求
- **流水线集成**：fake LLM stub 跑通四阶段与会话修改
- **评估器对抗回归**：E3 对抗样本固化为常驻测试——评估器任何改动必须保持压制作弊变体
- 真实 API 冒烟标记 `@llm` 手动触发；CI 只跑 mock 全套

---

## 12. 技术栈与依赖

Python ≥3.11；pydantic v2、midiutil、FastAPI + uvicorn、httpx、numpy/scipy/pandas（评测分析）、pytest。前端：Node ≥18、Vite、vanilla JS、@sakun/system.css。可选二进制：FluidSynth + SoundFont（WAV 渲染）。

## 13. 交付物映射（赛题要求 → 仓库位置）

| 赛项交付 | 位置 |
|----------|------|
| 开源仓库：源码/README/env.example/运行说明 | 仓库根 + README.md |
| 评测样本集 | evals/samples/*.yaml |
| 评估方法说明文档 | 本文档 §6 + docs/evaluation.md（面向评审者的独立版） |
| 评测脚本 | evals/runners/ |
| 完整结果表格 | evals/results/ |
| 有效性验证过程与数据 | evals/experiments/（E1/E2/E3 脚本+输出数据） |
| 分析报告（场景理由/方案/维度依据/结论/模型信息/失败模式/能力边界/典型模式） | docs/report.md |

## 14. 风险与已知局限

1. **同模型自偏好**：judge 与生成共用单一第三方模型；缓解见 §6.4，报告中作为局限讨论。
2. **单人标注统计效力弱**：一致性验证以稳定性为主、人机相关为辅（§8 E2）。
3. **听感与符号指标的鸿沟**：规则分高 ≠ 好听；J3 锚点 rubric 与 case 归因分析部分弥补，报告如实呈现分歧案例。
4. **第三方 API 不确定性**：Responses 协议的结构化输出支持程度未知；normalize 层与 mock 测试保证降级路径可用。
