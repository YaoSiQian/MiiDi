# MiiDi API 文档

MiiDi 的后端基于 FastAPI，所有接口统一挂在 `/api` 前缀下。

## 会话生命周期

1. **创建会话**（`POST /api/sessions`）——提交 prompt 和风格，服务器立即返回 session id，默认只跑 plan 阶段。
2. **生成指定阶段**（`POST /api/sessions/{sid}/generate`）——可以触发 core / arrange，分步控制生成流程。
3. **查状态**（`GET /api/sessions/{sid}/status`）——后台生成还没跑完时返回 `generating`，跑完返回 `done`。
4. **拿谱子**（`GET /api/sessions/{sid}/composition`）——拿到最新版本的 JSON 结构。
5. **修订**（`POST /api/sessions/{sid}/revise`）——传文字反馈，自动判断修单轨还是整体重来。
6. **评估**（`POST /api/sessions/{sid}/evaluate`）——规则校验 + 评分。
7. **下载 MIDI**（`GET /api/sessions/{sid}/midi`）——拿到 `.mid` 文件。

---

## 接口详情

### POST /api/sessions

创建新会话，同时执行 plan 阶段（生成曲目骨架、结构、和声框架），如果 stages 包含 core/arrange 会在后台继续跑。

**请求体**

```json
{
  "prompt": "写一首关于大海的轻快钢琴曲",
  "style": "pop",
  "stages": ["plan"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| prompt | string | 是 | 用户描述 |
| style | string | 是 | 风格包名称，如 `pop`、`touhou` |
| stages | string[] | 否 | 要跑的阶段，可选 `plan`、`core`、`arrange`，默认只跑 `plan` |

**响应**

```json
{
  "sid": "abc123"
}
```

返回的 `sid` 用来后续所有接口调用。如果 stages 里带了 `core` 或 `arrange`，后台会接着跑，通过 status 接口轮询进度。

**错误**

| 状态码 | 场景 |
|--------|------|
| 503 | 服务器未初始化 |
| 500 | pipeline 内部错误 |

---

### POST /api/sessions/{sid}/generate

对已存在的会话执行指定阶段。适合分步控制生成流程——比如先跑 plan，看看骨架再决定要不要继续。

**请求体**

```json
{
  "stages": ["core", "arrange"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stages | string[] | 是 | 要跑的阶段，可选 `plan`、`core`、`arrange` |

**响应**

```json
{
  "sid": "abc123",
  "stage_log": ["composed melody", "composed bass", "composed drums", "core: done"],
  "comp": {
    "meta": { "title": "...", "bpm": 120 },
    "structure": [],
    "harmony": [],
    "tracks": []
  }
}
```

| 字段 | 说明 |
|------|------|
| stage_log | 各阶段执行日志 |
| comp | 生成完毕的 Composition 结构，失败时可能为 null |

**错误**

| 状态码 | 场景 |
|--------|------|
| 404 | session 不存在 |
| 503 | 服务器未初始化 |

---

### GET /api/sessions/{sid}/status

查看会话当前状态。

**响应**

```json
{
  "sid": "abc123",
  "stage": "done",
  "trajectory": [],
  "stage_log": ["plan: brief ok", "core: done", "arrange: done"]
}
```

| 字段 | 说明 |
|------|------|
| stage | 当前状态：`planned`（只有骨架）、`generating`（后台跑着）、`done`（跑完）、`rolled_back`（回滚后） |
| trajectory | self-review 的轨迹数据，没跑到 arrange 阶段就为空 |
| stage_log | 各阶段执行记录 |

**错误**

| 状态码 | 场景 |
|--------|------|
| 404 | session 不存在 |
| 503 | 服务器未初始化 |

---

### GET /api/sessions/{sid}/composition

获取最新版本的谱面 JSON。

**响应**

```json
{
  "meta": {
    "title": "untitled",
    "bpm": 120,
    "time_signature": [4, 4],
    "key": { "tonic_pc": 0, "mode": "major" },
    "style": "pop"
  },
  "structure": [
    { "name": "intro", "start_bar": 0, "bars": 4 }
  ],
  "harmony": [
    { "bar": 0, "dur_bars": 4, "symbol": "C" }
  ],
  "tracks": [
    {
      "name": "piano",
      "program": 0,
      "role": "melody",
      "is_drum": false,
      "notes": [[0, 480, 60, 80]]
    }
  ]
}
```

**错误**

| 状态码 | 场景 |
|--------|------|
| 404 | session 不存在，或还没有版本 |

---

### GET /api/sessions/{sid}/versions

列出该会话所有版本的历史。

**响应**

```json
{
  "versions": [
    { "version": 1, "label": "planned", "created": "2026-09-05T10:00:00" },
    { "version": 2, "label": "core", "created": "2026-09-05T10:00:15" }
  ]
}
```

**错误**

| 状态码 | 场景 |
|--------|------|
| 404 | session 不存在 |

---

### POST /api/sessions/{sid}/revise

提交文字反馈来修订作品。服务器会先用 LLM 判断反馈指向的是哪个音轨——如果是单轨问题就只修那一轨，如果是整体问题就重跑 pipeline。

**请求体**

```json
{
  "feedback": "bass 声部太吵了，轻一点"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| feedback | string | 是 | 修订意见 |

**响应**

```json
{
  "sid": "abc123",
  "stage": "done",
  "trajectory": [],
  "stage_log": ["revised track bass as v3"]
}
```

**错误**

| 状态码 | 场景 |
|--------|------|
| 500 | 修订过程出错 |

---

### POST /api/sessions/{sid}/versions/{version}/rollback

回滚到指定版本，会生成一个新版本（内容是目标版本的拷贝）。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| version | int | 目标版本号 |

**响应**

```json
{
  "sid": "abc123",
  "stage": "rolled_back",
  "trajectory": [],
  "stage_log": ["rolled back to version 2 as v4"]
}
```

**错误**

| 状态码 | 场景 |
|--------|------|
| 404 | 指定版本不存在 |

---

### POST /api/sessions/{sid}/evaluate

对最新版本做规则评估。先跑规则校验（音域、节奏密度等），如果规则通过了还会跑 LLM 评分。

**响应**

```json
{
  "report": {
    "invalid": false,
    "gates": [],
    "per_track": {}
  },
  "composite": {
    "overall": 7.5,
    "axes": {}
  }
}
```

| 字段 | 说明 |
|------|------|
| report | 规则评估报告，`invalid` 为 true 表示有硬性违规 |
| composite | 综合评分，如果规则校验不通过则为 null |

**错误**

| 状态码 | 场景 |
|--------|------|
| 404 | session 不存在，或没有版本 |

---

### GET /api/sessions/{sid}/midi

下载当前最新版本对应的 MIDI 文件。如果还没有生成过 midi，会当场渲染。

**响应**

直接返回文件，Content-Type 为 `audio/midi`。

**错误**

| 状态码 | 场景 |
|--------|------|
| 404 | session 不存在，或没有版本 |

---

## 错误格式

所有接口出错时返回标准 HTTP 状态码 + JSON：

```json
{
  "detail": "session abc123 not found"
}
```

503 表示服务端还没初始化好（store 或 client 为 None），正常情况下不会出现。500 是 pipeline 内部异常。404 是最常见的——要么 session id 写错了，要么还没跑到对应阶段就来取数据。
