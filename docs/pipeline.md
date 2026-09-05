# MiiDi 生成管线

MiiDi 把用户的一句话描述拆成五个阶段，逐步把抽象意图变成可播放的 MIDI 文件。整个过程不是一次性跑完——每个阶段结束后都会把中间结果写进会话存储，遇到中断可以接着来。

## 阶段总览

```
Plan → Core → Arrange → Coordinate → Review → MIDI
```

五个阶段的职责：

| 阶段 | 做什么 | 输出 |
|------|--------|------|
| Plan | 理解用户意图，生成音乐蓝图 | MusicBrief（速度、调性、结构、和声、乐器配置） |
| Core | 生成骨架声部 | melody / bass / drums 三条 Track |
| Arrange | 填充织体 | harmony / counter / color 三条 Track |
| Coordinate | 审视整体平衡 | 调整命令列表（静音、八度、密度） |
| Review | 规则打分 + LLM 自我修补 | 最终 Composition |

## 各阶段详解

### Plan — 音乐蓝图

用户输入一句自然语言（比如"写一段 120bpm 的 jazz loop"），LLM 会生成一个 JSON 格式的 `MusicBrief`，包含：

- **meta**：标题、BPM（受风格包范围约束，比如 60–180）、拍号、调号（tonic + mode）
- **structure**：段落列表，每段有 `start_bar` 和 `bars`
- **harmony**：和弦进行，每个 `ChordSpan` 包含 bar、dur_bars、symbol
- **instruments**：乐器配置，每件乐器有 name、program（0–127）、role（melody/bass/harmony/counter/color/drums）

`MusicBrief` 会自动校验和弦符号是否合法。如果 LLM 返回的结构里 `start_bar` 不连续，系统会自动修复并记录修正日志。

**配置参数**：
- `style`：风格包名，决定 BPM 范围、密度参考值、鼓组 pattern 等默认参数
- `stages=["plan"]`：只跑这一步就停

**输出**：`MusicBrief` 对象 + 空骨架 `Composition`（有 meta、structure、harmony，但 tracks 里只有占位）

### Core — 骨架声部

三条核心轨道按固定顺序生成：melody → bass → drums。

每条轨道的生成流程：
1. 从 `MusicBrief` 取出对应的 `InstrumentSpec`
2. 如果之前有已生成的轨道，把它们作为上下文传给 LLM（bass 和 harmony 会拿到完整的 melody 音符；counter 和 color 只拿到每小节的 pitch class 摘要）
3. LLM 返回原始 JSON，经过 `normalize_raw` 规范化
4. 对规范化后的结果做 `validate_composition` 校验
5. 校验不通过就带反馈重试，最多 3 次

**配置参数**：
- `stages=["plan", "core"]`：只跑 Plan + Core

**输出**：三条有实际音符的 Track，分别替换骨架中的占位

### Arrange — 织体填充

和 Core 阶段类似的流程，生成 harmony、counter、color 三条轨道。

区别在于上下文：这三条轨道在生成时能看到 Core 阶段已经写好的旋律、贝斯和鼓，所以和声声部可以围绕旋律展开，副旋律可以避开主旋律的音区。

**输出**：六条轨道全部就位，`Composition` 初步成型

### Coordinate — 编配协调

LLM 拿到完整的六轨编配后，分析整体平衡，输出调整命令。支持三种操作：

| 命令 | 作用 | 参数 |
|------|------|------|
| `section_mute` | 静音某段落 | track, start_bar, end_bar |
| `octave_shift` | 八度移位 | track, direction (up/down) |
| `density_reduce` | 稀疏化 | track, factor, start_bar, end_bar |

如果 LLM 没给出有效调整，这一步直接跳过。

### Review — 规则评审 + 自我修补

分两部分：

**规则评分**：用 `evaluate_rules` 对 Composition 做多维度打分（R_rule，0–100），包含五个轴：

- harmony（权重 0.30）：和声与和弦进行的匹配度
- voice（权重 0.20）：声部合理性
- rhythm（权重 0.20）：节奏多样性
- structure（权重 0.20）：段落结构
- dynamics（权重 0.10）：动态范围

还有四个门控因子：repetition、density、balance、spread，任一门控为 0 都会让总分归零。

**自我修补**：LLM 看到评分报告后，选择一条轨道重写。重写结果必须通过 `validate_composition` 校验才能被接受。最多跑 `max_review_rounds` 轮（默认 2），如果两轮之间 R_rule 提升不到 1.0 分就提前停。

## 会话管理

`SessionStore` 把每次生成的所有版本持久化到磁盘。

### 目录结构

```
sessions/
  20260905-143022-a1b2/
    meta.json          # 会话元数据（prompt, style, versions 列表）
    v1.json            # planned 版本
    v2.json            # core 版本
    v3.json            # assembled 版本
    v4.json            # reviewed 版本
```

### 版本标签

每个阶段结束都会保存一个版本，标签对应阶段名：

- `planned` — Plan 完成
- `core` — Core 完成
- `assembled` — Arrange 完成
- `reviewed` — Review 完成
- `revised` — 用户反馈修改（单轨重写）
- `revised-regenerated` — 用户反馈修改（整体重生成）

### 查看历史

```python
from miidi.session.store import SessionStore

store = SessionStore(Path("sessions"))

# 列出所有会话
store.list_sessions()  # ["20260905-143022-a1b2", ...]

# 查看某个会话的所有版本
store.list_versions("20260905-143022-a1b2")
# [{"version": 1, "label": "planned"}, {"version": 2, "label": "core"}, ...]

# 加载某个版本的 Composition
comp = store.load_composition("20260905-143022-a1b2", 4)
```

## 断点恢复

管线支持从任意阶段的中间结果恢复，只需要传入 `sid` 参数：

```python
# 第一次跑了 Plan + Core，中断了
result = run_pipeline("jazz loop", "jazz", client, stages=["plan", "core"], store=store)
sid = result.sid  # 记下会话 ID

# 之后从 core 版本继续跑 Arrange
result = run_pipeline("jazz loop", "jazz", client, stages=["plan", "core", "arrange"],
                      store=store, sid=sid)
```

会话 ID 格式是 `YYYYMMDD-HHMMSS-xxxx`，最后四位是随机 hex，确保唯一。

## 断点续跑的注意事项

1. **必须传 `sid`**：不传的话会创建新会话
2. **`stages` 可以缩减**：如果只传 `["plan"]`，就只跑 Plan；传 `["plan", "core"]` 跑到 Core 停
3. **已生成的 Track 不会重复生成**：`stages` 参数控制的是哪些阶段执行，但每个阶段内部的 Track 生成是完整执行的
4. **版本不覆盖**：每次 `save_version` 都创建新文件，不会覆盖之前的版本

## 修订流程

生成完成后，用户可以给出反馈，系统会智能决定怎么改：

```python
result = revise(store, client, sid, "把鼓换成 swing 风格")
```

修订有两种路径：

1. **单轨重写**：如果反馈明确指向某条轨道（"鼓太密了"、"副旋律太抢"），LLM 会分类出目标轨，只重新生成那一轨
2. **整体重生成**：如果反馈比较模糊（"听起来不像 jazz"），会把反馈追加到原始 prompt，重新跑一遍完整管线

重生成会经过整曲校验（`validate_composition`），不通过就丢弃，不覆盖之前的版本。

## 时间预期

一次完整生成（Plan → Review）的耗时取决于 LLM 调用次数：

| 阶段 | LLM 调用次数 | 大致耗时 |
|------|-------------|---------|
| Plan | 1–2 次 | 5–15 秒 |
| Core | 3–9 次（3 轨 × 最多 3 次重试） | 15–45 秒 |
| Arrange | 3–9 次 | 15–45 秒 |
| Coordinate | 1 次 | 3–8 秒 |
| Review | 2–6 次（2 轨 × 最多 3 次重试） | 10–30 秒 |

整体来看，一次完整生成大约需要 1–2 分钟。如果中途需要重试（比如和弦符号不合法），Plan 阶段会多花一倍时间。

## 错误处理

每个阶段都有异常捕获。如果某个阶段失败：

- 该阶段之前的中间结果不会丢失（已经保存到会话了）
- 返回的 `PipelineResult.comp` 为 `None`
- 错误信息写入 `stage_log`

可以基于上一个成功版本的 `sid` 重新跑失败的阶段。
