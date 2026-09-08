## 目标

把 Web 端从"一次性生成"改为**分阶段流水线**：plan → core → arrange 每个阶段完成后停下，用户可预览、继续（Continue）、或提意见（可选 feedback 后重做当前阶段）；同时修复 stages 判断 bug、revise 中间版本污染，并落地会话恢复（hash + 会话列表窗口）。UI 保持英文，不做 favicon。

## 一、后端（src/miidi/）

### 1. `pipeline/orchestrator.py` — run_pipeline 支持续跑（核心改动）
- **resume 语义**：`sid` + `store` 存在时，加载最新版本作为起点；若该版本的 `extra.brief` 存在则用 `MusicBrief.model_validate` 恢复完整 brief（planned 版本保存时已带 `extra={"brief": ...}`，orchestrator.py:124），否则回退 `_brief_from_comp`。**有 prior 就跳过 make_brief**（省一次 LLM 调用，且避免重规划出不同 brief）。
- **阶段出条件改成员判断**（修复现 bug）：`stages == ["plan"]` → `"core" not in stages` 早退；`stages == ["plan","core"]` → `"arrange" not in stages` 早退。使 `["core"]`、`["plan","core"]`、全量三种都语义正确。
- **按轨道跳过已完成段**：core 段只合成 core 角色中**没有音符**的轨道；arrange 段同理；段内无可做轨道则静默跳过（不重复存版本）。arrange+review 段只在实际合成后执行。
- 保存 label 不变：planned / core / assembled / reviewed。更新 docstring。

### 2. `pipeline/orchestrator.py` — revise() 修复
- regenerate 路径给 `run_pipeline` 传 `store=None`（消除沿途 "core"/"assembled" 中间版本污染），最终结果由 revise 自己保存（现有 256-263 行逻辑保留）。
- 按会话当前状态选择重生成范围：最新版无音符 → `stages=["plan"]` 且保存 label `"planned"`（供阶段门反馈用）；其余保持全量重生成 + `"revised-regenerated"`。

### 3. `web/routes.py` + `web/schemas.py`
- 新增 `GET /api/sessions`：用现成的 `store.list_sessions()` + `session_meta()`，返回 `[{sid, prompt, style, created, versions}]`（无分页，规模小）。
- `POST /sessions/{sid}/generate` 改为**后台线程模式**（与 create_session 相同：置 `_bg_tasks[sid]="running"`，daemon thread 跑，status 端点复用），返回 `{sid, accepted: true}`；删除 287-291 行无用的 vestigial 读取。前端轮询现有 status 即可。

### 4. 阶段门反馈链路
- 前端在各阶段门提交 feedback 走现有 `POST /revise`；plan 阶段（无音符）由上面 2 的分支落到"仅重规划"。

## 二、前端（web/）

### 1. 阶段门流程（app.js + index.html）
- Generate 只跑 `stages:["plan"]`，完成后自动进 Preview。
- Preview 窗口新增：**Plan 摘要块**（title/BPM/key/structure 各段/instrument 清单，无音符时显示，有音符时隐藏）+ **Continue 按钮**（下一段：plan→core→arrange）+ **可选反馈输入框 + Apply feedback 按钮**（POST /revise，成功后刷新当前阶段预览）。
- 状态文案按段更新（"generating core tracks..." → "arranging harmony & color..." 等）。
- arrange 段完成后维持现有链路：自动 loadEval → Evaluate 步骤。
- 全程用现有 pollUntilReady 轮询（含已修复的 error 处理）。

### 2. 会话恢复
- `#session=<sid>` hash：generate 成功 / 打开会话时写入；New Session 清除；页面加载时解析并自动恢复。
- Session 菜单新增 **Open Session…**（index.html 加 `<a href="#open">`）；新增静态 **Sessions 窗口**（System 6 风格）列出会话（sid、prompt 截断、style、版本数），点击行打开：置 currentSid、loadComposition + loadVersions + trajectory、写 hash、进 Preview。
- Evaluator 窗口加一个小 **Evaluate** 按钮（调现有 loadEval），供恢复的会话按需评估。

## 三、测试（tests/，全部 mock LLM）

- orchestrator：`stages=["core"]` + planned sid → 不调用 make_brief、只存 "core"；core 完成后 `stages=["arrange"]` → 只补 arrange 角色并存 assembled+reviewed；已完成段重复请求 → 不产生新版本。
- revise：regenerate 路径不再产生中间 "core" 版本；plan 阶段 feedback → 只重规划、label "planned"。
- web：`GET /api/sessions` 列表；`POST /sessions/{sid}/generate` 后台化（立即返回 + status 变 done）。
- 更新受 stages 语义变化影响的既有测试。

## 四、文档（中文）

- `docs/api.md`：新增 GET /api/sessions、generate 端点行为、hash 恢复说明。
- `docs/pipeline.md`：补分阶段/续跑语义。

## 不做

- UI 中文化（英文是既定方向）、favicon、会话分页、plan 段的结构编辑器（反馈走文本）。
- 不改 CLI 行为（CLI 默认全流程不变）。

## 涉及文件

`src/miidi/pipeline/orchestrator.py`、`src/miidi/web/routes.py`、`src/miidi/web/schemas.py`、`web/index.html`、`web/js/app.js`、`tests/*`（新增 2 个测试文件或扩展现有）、`docs/api.md`、`docs/pipeline.md`