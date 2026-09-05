# MiiDi 架构

MiiDi 是一个 LLM 驱动的符号音乐生成系统。用户输入自然语言描述，系统自动完成从音乐规划到 MIDI 输出的全流程。核心设计思路：用确定性规则做质量底线，用 LLM 做创意和美学判断，两条轨道互相校验。

---

## 模块全景

```
src/miidi/
├── schema/        # 数据模型、格式修复、硬约束校验
├── musicutil/     # 音程工具、音阶查询、GM 乐器映射
├── eval/          # 规则评估轴、反退化门、LLM Judge、合成评分
├── llm/           # LLM 客户端，双协议自动降级
├── skills/        # 曲风知识包加载器
├── pipeline/      # 五阶段流水线、编配协调、会话式修改
├── session/       # 版本管理、快照持久化
├── render/        # MIDI 文件渲染
├── web/           # FastAPI 应用、RESTful API
└── cli.py         # 命令行入口
```

依赖方向单一，从上往下流。`schema` 不依赖任何业务模块，`pipeline` 依赖其余所有，`web` 只接 `pipeline` 和 `session`。

---

## schema：数据的契约层

`schema/model.py` 定义了整个系统共用的数据模型，全部基于 pydantic v2 `BaseModel`。

**核心模型：**

| 模型 | 作用 |
|------|------|
| `Composition` | 顶层容器，包含 `Meta`、`structure`（段落）、`harmony`（和弦时间线）、`tracks`（轨道列表） |
| `Track` | 单轨：name、program（GM 编号）、role（melody/bass/harmony/counter/color/drums）、notes 列表 |
| `Meta` | 元数据：标题、BPM、拍号、调性、曲风 |
| `Section` | 段落定义：名称、起始小节、持续小节数 |
| `ChordSpan` | 和弦事件：起始小节、持续小节数、和弦符号 |

音符格式是四元组 `[onset_tick, duration_tick, midi_pitch, velocity]`，PPQ=480。选择元组而非字典，是因为音符在系统中被频繁遍历和计算，元组的内存开销和访问速度都更优。

`Composition` 提供了 `bar_ticks`（每小节 tick 数）、`piece_end_tick`（曲目结束位置）、`clamp_to_boundary`（截断越界音符）等计算方法。这些方法被 eval 和 pipeline 广泛调用。

**normalize.py** 负责把 LLM 输出的混乱 JSON 修复成合法的 `Composition`。LLM 经常丢掉 onset、用字符串表示音高（如 "C4"）、混用时值记号（"4" 代表四分音符）。`normalize_raw` 逐个音符做类型强转和缺失值填充，返回 `NormalizeResult`（包含修复记录和错误列表）。pipeline 的每个阶段在 LLM 调用后都会走一遍 normalize。

**validate.py** 做硬约束检查：音高越界、velocity 范围、音符重叠、时长越界。返回 `Violation` 列表。这些约束是铁律——任何一条违反就意味着 MIDI 文件不可用。

**chords.py** 解析和弦符号（如 "Fmaj7"、"Bm7b5"）成 `ChordInfo`（根音、音级集合、品质）。支持 16 种常见和弦类型。eval 的和声轴用它来判断音符是否落在和弦内。

---

## musicutil：音乐理论工具

三个小模块，提供 eval 和 pipeline 需要的音乐理论计算：

- **scales.py** — 根据调性返回音阶音级集合。大调音阶、小调变体（和声小调、旋律小调的超集）
- **band.py** — `band()` 函数：把一个数值映射到 [0, 1] 区间，支持渐变段和硬边界。eval 的所有轴评分都依赖它
- **gm.py** — GM MIDI 乐器的演奏音域和舒适音域查询，以及多轨 MIDI channel 分配

---

## eval：双轨评测引擎

评测分两条轨，各自独立运行，最后加权合成。

### 规则轨

`eval/score.py` 是入口。先过格式校验（`axis_format`），不合法直接返回 0 分。通过后计算五个加权轴 + 四个乘法门。

| 轴 | 权重 | 检测什么 |
|----|------|----------|
| harmony | 0.30 | 音阶符合度、和弦支撑度、和弦声明匹配、音簇率、终止式 |
| voice | 0.20 | 演奏音域适配、平行五八度、跳进率、旋律-低音间距 |
| rhythm | 0.20 | 网格吸附率、密度适配、鼓 pattern 匹配、swing 一致性 |
| structure | 0.20 | 段落覆盖、同族相似度、异族对比度、密度形态、动机再现 |
| dynamics | 0.10 | velocity 分布、方向性、副歌-主歌梯度 |

每个轴返回 `AxisResult`（score + details 字典），细节可追溯到具体指标。

**反退化门**是乘法因子，取值 [0, 1]，全部相乘后乘以加权分。设计目的是封死特定作弊模式：

| 门 | 防御什么 |
|----|----------|
| repetition | 4-gram 重复率过高 → 复读凑篇幅 |
| density | 全局音符密度过高 → 十六分音符轰炸 |
| balance | 某轨时长占比过低 → 凑轨数 |
| spread | 音高分布过于集中 → 表面丰富实际单调 |

`EvaluationContext`（`eval/context.py`）预计算了段落边界、和弦时间线、平铺音符列表等，避免各轴重复计算。

### Judge 轨

`eval/judge.py` 三次调用 LLM，分别评估风格符合度（J1）、提示遵循度（J2）、整体音乐性（J3）。

J1 从 `StylePack` 的 `SKILL.md` 和 `instruments.md` 提取特征清单，逐条做 yes/partial/no 判定。J2 用正则从用户 prompt 中提取显式约束（BPM、调性、时长、乐器），逐条比对。J3 给出 1-5 分的锚点评分。

每次 LLM 调用都要求输出结构化 JSON，带 per_item 逐条证据和 evidence 引用（track + bar 编号）。

### 合成

`eval/composite.py` 把两条轨的结果合并：

```
composite = 0.6 × R_rule + 0.4 × mean(J1, J2, J3)
```

规则轨权重更高，因为它是确定性的、可复现的。Judge 轨覆盖规则无法触及的美学维度。

---

## llm：LLM 客户端

`llm/client.py` 封装了 LLM 调用，核心是 `LLMClient` 类。

**双协议设计：** 系统支持两种 API 后端。配置了 `OPENAI_BASE_URL` 时走 OpenAI Responses API；未配置时自动降级到 OpenCode Zen（免费 Chat Completions API）。`LLMConfig.provider` 字段决定走哪条路径。这个设计让项目零配置即可运行，同时保留对接商业模型的能力。

**重试机制：** 遇到 429（限流）或 5xx 错误时指数退避重试，最多 `max_retries` 次。4xx 非限流错误直接抛出。

**JSON 提取：** `extract_json` 从 LLM 回复中提取第一个完整 JSON 对象。LLM 经常在 JSON 外面包 markdown 代码块或额外文本，这个函数用括号匹配做提取，比正则可靠。

所有 pipeline 阶段的 LLM 调用都通过 `client.respond_json(system, user)` 完成，返回已解析的字典。

---

## skills：曲风知识包

`skills/` 目录下每个子目录是一个曲风包（目前有 pop、classical、jazz、lofi、touhou）。

每个包包含五个文件：

| 文件 | 内容 |
|------|------|
| `SKILL.md` | 曲风身份描述、风格特征清单 |
| `instruments.md` | 该曲风的标准配器、各乐器角色 |
| `harmony.md` | 和声语汇：可用和弦符号、进行模式 |
| `rhythm.md` | 节奏特征：鼓 pattern、swing 感觉 |
| `defaults.json` | 评估参数：BPM 范围、密度参考值、swing 偏移、鼓 pattern 残差 |

`skills/loader.py` 的 `load_style_pack` 加载并解析这五个文件，返回 `StylePack` 数据类。pipeline 用它构造 prompt，eval 用它的 `defaults` 做评估参数校准。

这个设计把曲风知识从代码中剥离出来。添加新曲风只需新建目录和文件，不改任何 Python 代码。

---

## pipeline：五阶段流水线

`pipeline/orchestrator.py` 的 `run_pipeline` 是主入口。

### 阶段流程

```
用户 prompt + 曲风
       │
       ▼
  ① Plan ──── LLM 生成音乐简报（MusicBrief）
       │       调性、节拍、段落结构、和弦时间线、配器表
       │       含一次重试：和弦符号校验失败自动修正
       ▼
  ② Core ──── 逐轨调用 LLM，生成核心轨
       │       melody → bass → drums（顺序执行，后续轨能读到前面轨的上下文）
       ▼
  ③ Arrange ── 逐轨调用 LLM，生成编配轨
       │       harmony → counter → color
       ▼
  ④ Coordinate  LLM 分析整体编配，输出结构调整命令
       │       section_mute / octave_shift / density_reduce
       ▼
  ⑤ Review ──── 规则评估 → LLM 定点 patch → 循环（最多 2 轮）
       │       每轮评估 R_rule，分数提升不足 1.0 则停止
       ▼
    validate ── 全曲硬约束校验
       │
       ▼
    render ──── 生成 MIDI 文件
```

### 关键设计决策

**逐轨串行生成。** 每个轨道生成时，能看到前面已生成轨道的上下文（音高类摘要或完整音符）。这是刻意的选择——并行生成虽然快，但轨道之间会互相冲突。串行牺牲了速度换来了声部间的协调性。

**编配协调独立于创作。** 第④阶段不做音符级修改，只输出结构级调整命令。这些命令由 `apply_adjustments` 执行：静音某个段落的某轨、整体移调八度、降低密度。这种分离让编配逻辑可测试、可回滚。

**自评循环有退出条件。** R_rule 提升不到 1.0 分就停。继续 patch 大概率是过拟合——在规则允许的范围内反复微调，实际音乐质量没有提升。

### MusicBrief

`pipeline/brief.py` 定义了 `MusicBrief`，它是 Plan 阶段的输出产物。包含 title、bpm、time_signature、tonic_pc、mode、structure、harmony、instruments。`to_skeleton()` 方法把它转成空音符的 `Composition`，供后续阶段填充。

`validate_symbols` 在 Plan 阶段就检查和弦符号合法性，不合法的简报会被拒绝并重试。

### 会话式修改

`pipeline/orchestrator.py` 的 `revise` 函数处理用户的修改请求。先用 LLM 判断修改属于哪个层次（单轨 / 和声 / 结构 / 整体重生），再路由到对应处理路径。单轨修改只重新生成目标轨道，保留其余轨道不变。

---

## session：版本管理

`session/store.py` 用文件系统做持久化。

```
sessions/
└── 20250101-120000-abcd/
    ├── meta.json          # 会话元数据（prompt、style、版本列表）
    ├── v1.json            # Plan 阶段快照
    ├── v2.json            # Core 阶段快照
    └── v3.json            # Review 后快照
```

每个版本快照包含完整的 `Composition` JSON 和额外信息（如自评轨迹）。`SessionStore` 提供 `create`、`save_version`、`load_version`、`latest`、`rollback` 等操作。

选择文件系统而非数据库，是因为这个系统的数据量小（单首曲子几 KB）、并发低（主要是单用户场景）、调试需要直接查看 JSON。文件系统还天然支持版本回滚——复制一份就行。

---

## render：MIDI 渲染

`render/midi.py` 把 `Composition` 转成标准 MIDI 文件。用 `midiutil` 库，逐轨写入音符、设置 GM program、写入 tempo 和拍号标记。

MIDI 文件是系统的最终输出产物，可以在任何 DAW 中打开和编辑。

---

## web：HTTP API 层

`web/app.py` 创建 FastAPI 应用，挂载 `/api` 路由和前端静态文件。

**核心端点：**

| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/api/sessions` | 创建会话，执行 Plan 阶段，返回 sid |
| POST | `/api/sessions/{sid}/generate` | 执行指定阶段 |
| GET | `/api/sessions/{sid}/status` | 查看生成状态 |
| GET | `/api/sessions/{sid}/composition` | 获取当前版本曲谱 |
| POST | `/api/sessions/{sid}/revise` | 提交修改请求 |
| POST | `/api/sessions/{sid}/versions/{v}/rollback` | 回滚到指定版本 |
| POST | `/api/sessions/{sid}/evaluate` | 规则 + Judge 双轨评估 |
| GET | `/api/sessions/{sid}/midi` | 下载 MIDI 文件 |

生成是异步的——`/api/sessions` 先同步跑 Plan（~10s），然后在后台线程跑 Core 和 Arrange。前端通过轮询 `/api/sessions/{sid}/status` 获取进度。

`web/routes.py` 维护一个全局的 `_bg_tasks` 字典跟踪后台任务状态。`web/schemas.py` 定义请求/响应的 pydantic 模型。

---

## 数据流：从 prompt 到 MIDI

完整路径：

1. 用户提交 `{"prompt": "雨夜的咖啡馆", "style": "lofi"}`
2. `load_style_pack("lofi")` 加载曲风知识包
3. Plan 阶段：`make_brief` 调用 LLM → 返回 `MusicBrief` → 转成骨架 `Composition`
4. Core 阶段：按 melody → bass → drums 顺序，每轨调用 LLM，传入已生成轨道的上下文
5. Arrange 阶段：按 harmony → counter → color 顺序，同样逐轨生成
6. Coordinate 阶段：LLM 分析全曲平衡，输出调整命令 → `apply_adjustments` 执行
7. Review 阶段：`evaluate_rules` 打分 → LLM 看报告决定改哪轨 → 替换音符 → 重评 → 循环
8. `validate_composition` 最终校验
9. `generate_midi` 渲染成 .mid 文件
10. `SessionStore.save_version` 保存快照

每一步的中间产物都持久化到 `sessions/` 目录，支持断点续跑和版本回滚。

---

## 为什么是这样

**pydantic 而非 dataclass 做核心模型。** `Composition` 需要从 LLM 输出的不规范 JSON 构建，pydantic 的 `model_validate` 自带类型校验、默认值填充、嵌套模型解析。dataclass 做不到这些。eval 层的 `EvaluationContext`、`AxisResult` 用 dataclass，因为它们是纯计算中间产物，不需要序列化校验。

**LLM 回调走双协议。** OpenCode Zen 是免费的 Chat Completions API，降低了试用门槛。OpenAI Responses API 是更现代的格式。`LLMClient` 通过 `provider` 字段自动选择路径，对 pipeline 透明。

**session 用文件系统。** 单用户场景，数据量小，需要人工调试。文件系统比数据库简单，JSON 文件直接可读，版本管理用文件复制即可。

**逐轨串行而非并行生成。** 轨道之间有声部依赖——旋律影响和声选择，和声影响低音走向。串行生成让后续轨能参考前面的轨，减少冲突。代价是速度慢，但对生成质量的影响是正面的。

**规则轨权重高于 Judge 轨。** 规则是确定性的、零 API 成本、可复现。LLM 评判有随机性且成本高。6:4 的比例让规则轨兜底，Judge 轨补充美学判断。

**反退化门用乘法而非减法。** 乘法让每个门都成为必要条件——任何一个门触发都直接拉低总分。减法可能被其他轴的高分补偿，失去防御效果。
