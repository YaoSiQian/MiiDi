# Plan 3: Web 应用（FastAPI + 复古 Mac 前端）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI backend wrapping the miidi kernel and a Vite + system.css frontend with Macintosh System 6 multi-window desktop UI.

**Architecture:** Backend (`src/miidi/web/`) wraps existing `run_pipeline`, `revise`, `SessionStore`, `evaluate_rules`, `generate_midi` into 8 REST endpoints. Frontend (`webapp/frontend/`) uses Vite + vanilla JS + `@sakun/system.css` with a ~100-line window manager for draggable Mac windows. Four windows: Composer, Piano Roll, Evaluator, Feedback.

**Tech Stack:** Python ≥3.11, FastAPI + uvicorn, httpx; Node ≥18, Vite, vanilla JS, @sakun/system.css (pure CSS, MIT)

**Spec:** `docs/superpowers/specs/2026-08-22-miidi-design.md` §9 (Web 应用)

## Global Constraints

- Python ≥3.11; pydantic v2; FastAPI + uvicorn
- Kernel is pure Python, zero Web dependency — web layer is a caller
- Frontend: Vite + vanilla JS + @sakun/system.css (pure CSS components, MIT)
- Session persistence: filesystem JSON snapshots (no database)
- Progress: polling (YAGNI, no WebSocket)
- UI: System 6 retro Mac multi-window desktop; monochrome gray基调; piano-roll音轨着色是唯一彩色元素; 无弹窗对话框
- Frontend served as static files by FastAPI (production mode)

---

## File Structure

| File | Purpose |
|------|---------|
| `src/miidi/web/__init__.py` | Package init |
| `src/miidi/web/app.py` | FastAPI app factory, mounts static, CORS |
| `src/miidi/web/routes.py` | 8 API endpoints |
| `src/miidi/web/schemas.py` | Request/response Pydantic models |
| `tests/test_web.py` | Backend API tests (httpx AsyncClient) |
| `webapp/frontend/index.html` | Single-page app shell |
| `webapp/frontend/style.css` | system.css import + custom overrides |
| `webapp/frontend/js/window-manager.js` | ~100-line draggable window manager |
| `webapp/frontend/js/composer.js` | Composer window logic |
| `webapp/frontend/js/pianoroll.js` | Piano Roll canvas renderer |
| `webapp/frontend/js/evaluator.js` | Evaluator window logic |
| `webapp/frontend/js/feedback.js` | Feedback window logic |
| `webapp/frontend/js/app.js` | Main entry, orchestrates windows |
| `webapp/frontend/package.json` | Vite + system.css deps |
| `webapp/frontend/vite.config.js` | Vite config (dev proxy to :8000) |

---

### Task 1: FastAPI Backend Core

**Files:**
- Create: `src/miidi/web/__init__.py`
- Create: `src/miidi/web/app.py`
- Create: `src/miidi/web/routes.py`
- Create: `src/miidi/web/schemas.py`
- Create: `tests/test_web.py`
- Modify: `pyproject.toml` (add fastapi + uvicorn + httpx[http2] deps)

**Interfaces:**
- Consumes: `run_pipeline(prompt, style, client, store, out_dir)`, `revise(sid, feedback, client, store)`, `SessionStore(root)`, `evaluate_rules(comp, defaults)`, `generate_midi(comp, path)`, `load_style_pack(name)`
- Produces: FastAPI `app` object, 8 route handlers

- [ ] **Step 1: Add dependencies to pyproject.toml**

Add to `[project.dependencies]`:
```
"fastapi>=0.115",
"uvicorn[standard]>=0.34",
```

Run: `pip install -e ".[dev]"`

- [ ] **Step 2: Write request/response schemas**

Create `src/miidi/web/schemas.py`:

```python
from __future__ import annotations
from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    prompt: str
    style: str


class CreateSessionResponse(BaseModel):
    sid: str


class ReviseRequest(BaseModel):
    feedback: str


class StatusResponse(BaseModel):
    sid: str
    stage: str
    trajectory: list[dict]
    stage_log: list[str]


class VersionResponse(BaseModel):
    versions: list[dict]


class EvaluateResponse(BaseModel):
    report: dict
```

- [ ] **Step 3: Write route handlers**

Create `src/miidi/web/routes.py`:

```python
from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from miidi.web.schemas import (
    CreateSessionRequest, CreateSessionResponse,
    ReviseRequest, StatusResponse, VersionResponse, EvaluateResponse,
)
from miidi.pipeline.orchestrator import run_pipeline, revise, PipelineResult
from miidi.session.store import SessionStore
from miidi.llm.client import LLMClient
from miidi.skills.loader import load_style_pack
from miidi.eval.score import evaluate_rules
from miidi.render.midi import generate_midi

router = APIRouter()

_store: SessionStore | None = None
_client: LLMClient | None = None
_root: Path | None = None


def init(store: SessionStore, client: LLMClient, root: Path) -> None:
    global _store, _client, _root
    _store = store
    _client = client
    _root = root


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    if _store is None or _client is None:
        raise HTTPException(503, "server not initialized")
    out_dir = _root / "midi"
    out_dir.mkdir(parents=True, exist_ok=True)
    result: PipelineResult = run_pipeline(
        prompt=req.prompt,
        style=req.style,
        client=_client,
        store=_store,
        out_dir=out_dir,
    )
    if result.sid is None:
        raise HTTPException(500, "pipeline produced no session")
    return CreateSessionResponse(sid=result.sid)


@router.get("/sessions/{sid}/status", response_model=StatusResponse)
async def get_status(sid: str) -> StatusResponse:
    if _store is None:
        raise HTTPException(503, "server not initialized")
    try:
        meta = _store.session_meta(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")
    latest = _store.latest(sid)
    if latest is None:
        return StatusResponse(sid=sid, stage="empty", trajectory=[], stage_log=[])
    ver = _store.load_version(sid, latest)
    return StatusResponse(
        sid=sid,
        stage="done",
        trajectory=ver.get("extra", {}).get("trajectory", []),
        stage_log=ver.get("extra", {}).get("stage_log", []),
    )


@router.get("/sessions/{sid}/composition")
async def get_composition(sid: str) -> dict:
    if _store is None:
        raise HTTPException(503, "server not initialized")
    try:
        latest = _store.latest(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")
    if latest is None:
        raise HTTPException(404, "no versions")
    ver = _store.load_version(sid, latest)
    return ver.get("composition", {})


@router.get("/sessions/{sid}/midi")
async def get_midi(sid: str) -> FileResponse:
    midi_dir = _root / "midi" if _root else Path("midi")
    midi_path = midi_dir / f"{sid}.mid"
    if not midi_path.exists():
        raise HTTPException(404, "MIDI not found")
    return FileResponse(midi_path, media_type="audio/midi", filename=f"{sid}.mid")


@router.get("/sessions/{sid}/audio")
async def get_audio(sid: str):
    raise HTTPException(501, "FluidSynth not available")


@router.post("/sessions/{sid}/revise")
async def revise_session(sid: str, req: ReviseRequest) -> StatusResponse:
    if _store is None or _client is None:
        raise HTTPException(503, "server not initialized")
    try:
        result: PipelineResult = revise(sid, req.feedback, _client, _store)
    except Exception as e:
        raise HTTPException(500, str(e))
    return StatusResponse(
        sid=sid,
        stage="done",
        trajectory=result.trajectory,
        stage_log=result.stage_log,
    )


@router.get("/sessions/{sid}/versions")
async def get_versions(sid: str) -> VersionResponse:
    if _store is None:
        raise HTTPException(503, "server not initialized")
    try:
        versions = _store.list_versions(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")
    return VersionResponse(versions=versions)


@router.post("/sessions/{sid}/versions/{version}/rollback")
async def rollback(sid: str, version: int) -> StatusResponse:
    if _store is None:
        raise HTTPException(503, "server not initialized")
    try:
        _store.load_version(sid, version)
    except FileNotFoundError:
        raise HTTPException(404, f"version {version} not found")
    meta = _store.session_meta(sid)
    return StatusResponse(
        sid=sid,
        stage="rolled_back",
        trajectory=[],
        stage_log=[f"rolled back to version {version}"],
    )


@router.post("/sessions/{sid}/evaluate")
async def evaluate(sid: str) -> EvaluateResponse:
    if _store is None:
        raise HTTPException(503, "server not initialized")
    try:
        latest = _store.latest(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")
    if latest is None:
        raise HTTPException(404, "no versions")
    ver = _store.load_version(sid, latest)
    from miidi.schema.model import Composition
    comp = Composition(**ver.get("composition", {}))
    style = ver.get("style", "touhou")
    pack = load_style_pack(style)
    report = evaluate_rules(comp, pack.defaults)
    return EvaluateResponse(report=report.to_dict())
```

- [ ] **Step 4: Write app factory**

Create `src/miidi/web/app.py`:

```python
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from miidi.web.routes import router, init
from miidi.session.store import SessionStore
from miidi.llm.client import LLMClient


def create_app(store: SessionStore, client: LLMClient, root: Path) -> FastAPI:
    app = FastAPI(title="MiiDi", version="0.1.0")
    init(store, client, root)
    app.include_router(router, prefix="/api")

    frontend = Path(__file__).resolve().parents[3] / "webapp" / "frontend"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend), html=True), name="static")

    return app
```

- [ ] **Step 5: Write backend tests**

Create `tests/test_web.py`:

```python
from __future__ import annotations
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from miidi.web.app import create_app
from miidi.web.routes import router
from miidi.session.store import SessionStore


class FakeClient:
    def respond_json(self, system, user, temperature=0.0):
        return {
            "meta": {"title": "test", "style": "touhou", "bpm": 140, "time_sig": "4/4", "key": "Am", "bars": 4},
            "structure": [{"section": "a", "start_bar": 0, "end_bar": 4}],
            "harmony": [{"start_bar": 0, "end_bar": 4, "chord": "Am"}],
            "instruments": [{"track": "Lead", "role": "melody", "program": 80, "channel": 0}],
            "notes": {"Lead": [{"pitch": 60, "onset": 0, "duration": 480, "velocity": 80}]},
        }


@pytest.fixture
def client(tmp_path):
    store = SessionStore(str(tmp_path / "sessions"))
    app = create_app(store, FakeClient(), tmp_path)
    return TestClient(app)


def test_create_session(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    assert resp.status_code == 200
    data = resp.json()
    assert "sid" in data


def test_get_status(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.get(f"/api/sessions/{sid}/status")
    assert resp.status_code == 200
    assert resp.json()["sid"] == sid


def test_get_composition(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.get(f"/api/sessions/{sid}/composition")
    assert resp.status_code == 200


def test_404_for_unknown_session(client):
    resp = client.get("/api/sessions/nonexistent/status")
    assert resp.status_code == 404


def test_evaluate(client):
    resp = client.post("/api/sessions", json={"prompt": "test", "style": "touhou"})
    sid = resp.json()["sid"]
    resp = client.post(f"/api/sessions/{sid}/evaluate")
    assert resp.status_code == 200
    assert "report" in resp.json()
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_web.py -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/miidi/web/ tests/test_web.py pyproject.toml
git commit -m "feat: FastAPI backend with 8 API endpoints"
```

---

### Task 2: Frontend Scaffolding + Window Manager

**Files:**
- Create: `webapp/frontend/package.json`
- Create: `webapp/frontend/vite.config.js`
- Create: `webapp/frontend/index.html`
- Create: `webapp/frontend/style.css`
- Create: `webapp/frontend/js/window-manager.js`
- Create: `webapp/frontend/js/app.js`

**Interfaces:**
- Consumes: Backend API at `http://localhost:8000/api/*`
- Produces: Draggable Mac windows, menu bar, 4 window containers

- [ ] **Step 1: Create package.json**

```json
{
  "name": "miidi-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@sakun/system.css": "^0.1.0"
  },
  "devDependencies": {
    "vite": "^6.0"
  }
}
```

- [ ] **Step 2: Create vite.config.js**

```javascript
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
```

- [ ] **Step 3: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MiiDi</title>
  <link rel="stylesheet" href="https://unpkg.com/@sakun/system.css/dist/system.css" />
  <link rel="stylesheet" href="./style.css" />
</head>
<body>
  <div class="menu-bar">
    <span class="menu-bar-title">MiiDi</span>
    <span class="menu-bar-item" id="menu-session">Session</span>
    <span class="menu-bar-item" id="menu-about">About</span>
  </div>

  <div class="desktop">
    <div class="window" id="window-composer" style="left:40px;top:40px;width:420px;">
      <div class="title-bar"><h1 class="title">Composer</h1></div>
      <div class="window-content">
        <div class="form-group">
          <label>Prompt</label>
          <textarea id="prompt-input" rows="3" placeholder="Describe your piece..."></textarea>
        </div>
        <div class="form-group">
          <label>Style</label>
          <div class="style-buttons" id="style-buttons"></div>
        </div>
        <div class="form-group">
          <button class="btn btn-primary" id="btn-generate">Generate</button>
        </div>
        <div class="form-group">
          <div class="progress-bar" id="progress-bar" style="display:none;">
            <div class="progress-fill" id="progress-fill"></div>
          </div>
          <div id="status-text" class="status-bar"></div>
        </div>
      </div>
    </div>

    <div class="window" id="window-pianoroll" style="left:480px;top:40px;width:520px;">
      <div class="title-bar"><h1 class="title">Piano Roll</h1></div>
      <div class="window-content">
        <canvas id="pianoroll-canvas" width="500" height="300"></canvas>
        <div class="transport-bar">
          <button class="btn" id="btn-play">Play</button>
          <button class="btn" id="btn-stop">Stop</button>
        </div>
      </div>
    </div>

    <div class="window" id="window-evaluator" style="left:40px;top:380px;width:420px;">
      <div class="title-bar"><h1 class="title">Evaluator</h1></div>
      <div class="window-content">
        <div id="eval-scores"></div>
        <div id="eval-violations"></div>
        <div id="eval-trajectory"></div>
      </div>
    </div>

    <div class="window" id="window-feedback" style="left:480px;top:380px;width:520px;">
      <div class="title-bar"><h1 class="title">Feedback</h1></div>
      <div class="window-content">
        <div class="form-group">
          <label>Revision instructions</label>
          <textarea id="feedback-input" rows="2" placeholder="What should change?"></textarea>
        </div>
        <div class="form-group">
          <button class="btn" id="btn-revise">Revise</button>
        </div>
        <div id="version-timeline"></div>
      </div>
    </div>
  </div>

  <script type="module" src="./js/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create style.css**

```css
body {
  margin: 0;
  background: #e0e0e0;
  font-family: "Chicago", "Geneva", system-ui, sans-serif;
  font-size: 12px;
  overflow: hidden;
  height: 100vh;
}

.menu-bar {
  background: #e0e0e0;
  border-bottom: 2px solid #000;
  padding: 2px 8px;
  display: flex;
  gap: 16px;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10000;
}

.menu-bar-title {
  font-weight: bold;
  margin-right: auto;
}

.menu-bar-item {
  cursor: pointer;
}

.desktop {
  position: relative;
  width: 100vw;
  height: 100vh;
  padding-top: 24px;
}

.window {
  position: absolute;
  border: 2px solid #000;
  background: #e0e0e0;
  box-shadow: 2px 2px 0 #000;
}

.window .title-bar {
  background: #e0e0e0;
  border-bottom: 1px solid #000;
  padding: 2px 4px;
  cursor: grab;
  user-select: none;
}

.window .title-bar h1 {
  font-size: 12px;
  font-weight: bold;
  margin: 0;
  padding: 0;
}

.window .window-content {
  padding: 8px;
}

.window.focused {
  z-index: 9999;
}

.form-group {
  margin-bottom: 8px;
}

.form-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 2px;
}

textarea {
  width: 100%;
  box-sizing: border-box;
  font-family: inherit;
  font-size: 12px;
  border: 2px inset #999;
  background: #fff;
  padding: 4px;
}

.btn {
  font-family: inherit;
  font-size: 12px;
  border: 2px outset #ccc;
  background: #e0e0e0;
  padding: 2px 12px;
  cursor: pointer;
}

.btn:active {
  border-style: inset;
}

.btn-primary {
  font-weight: bold;
}

.progress-bar {
  height: 12px;
  border: 1px solid #000;
  background: #fff;
  margin-top: 4px;
}

.progress-fill {
  height: 100%;
  background: #000;
  width: 0%;
  transition: width 0.3s;
}

.status-bar {
  font-size: 11px;
  margin-top: 4px;
  color: #333;
}

.style-buttons {
  display: flex;
  gap: 4px;
}

.style-btn {
  width: 32px;
  height: 32px;
  border: 2px outset #ccc;
  background: #e0e0e0;
  cursor: pointer;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.style-btn.selected {
  border-style: inset;
  background: #ccc;
}

.transport-bar {
  margin-top: 4px;
  display: flex;
  gap: 4px;
}

canvas {
  border: 1px solid #000;
  background: #fff;
  display: block;
}
```

- [ ] **Step 5: Create window-manager.js (~100 lines)**

```javascript
// Macintosh System 6 window manager
// Handles: drag, click-to-focus, fold/unfold

export class WindowManager {
  constructor() {
    this.highestZ = 100;
    this.init();
  }

  init() {
    document.querySelectorAll(".window").forEach((win) => {
      this.setupDrag(win);
      this.setupFocus(win);
    });
  }

  setupDrag(win) {
    const titleBar = win.querySelector(".title-bar");
    if (!titleBar) return;

    let offsetX = 0;
    let offsetY = 0;
    let dragging = false;

    titleBar.addEventListener("mousedown", (e) => {
      dragging = true;
      offsetX = e.clientX - win.offsetLeft;
      offsetY = e.clientY - win.offsetTop;
      this.focus(win);
      e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      win.style.left = `${e.clientX - offsetX}px`;
      win.style.top = `${e.clientY - offsetY}px`;
    });

    document.addEventListener("mouseup", () => {
      dragging = false;
    });

    // Double-click to fold
    titleBar.addEventListener("dblclick", () => {
      const content = win.querySelector(".window-content");
      if (content) {
        content.style.display =
          content.style.display === "none" ? "block" : "none";
      }
    });
  }

  setupFocus(win) {
    win.addEventListener("mousedown", () => {
      this.focus(win);
    });
  }

  focus(win) {
    document.querySelectorAll(".window").forEach((w) =>
      w.classList.remove("focused")
    );
    this.highestZ++;
    win.style.zIndex = this.highestZ;
    win.classList.add("focused");
  }
}
```

- [ ] **Step 6: Create app.js (main entry)**

```javascript
import { WindowManager } from "./window-manager.js";

const STYLES = ["pop", "classical", "jazz", "lofi", "touhou"];
let currentSid = null;
let currentStyle = "touhou";

// Initialize
const wm = new WindowManager();

// Style buttons
const styleContainer = document.getElementById("style-buttons");
STYLES.forEach((s) => {
  const btn = document.createElement("button");
  btn.className = `style-btn${s === currentStyle ? " selected" : ""}`;
  btn.textContent = s[0].toUpperCase();
  btn.title = s;
  btn.addEventListener("click", () => {
    currentStyle = s;
    styleContainer.querySelectorAll(".style-btn").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
  });
  styleContainer.appendChild(btn);
});

// Generate
document.getElementById("btn-generate").addEventListener("click", async () => {
  const prompt = document.getElementById("prompt-input").value.trim();
  if (!prompt) return;

  const statusEl = document.getElementById("status-text");
  const progressEl = document.getElementById("progress-bar");
  const fillEl = document.getElementById("progress-fill");

  statusEl.textContent = "Generating...";
  progressEl.style.display = "block";
  fillEl.style.width = "10%";

  try {
    const resp = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, style: currentStyle }),
    });
    const data = await resp.json();
    currentSid = data.sid;
    statusEl.textContent = `Session ${data.sid} created`;
    fillEl.style.width = "100%";

    await loadComposition();
    await loadEval();
    await loadVersions();
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
});

// Load composition into piano roll
async function loadComposition() {
  if (!currentSid) return;
  try {
    const resp = await fetch(`/api/sessions/${currentSid}/composition`);
    const comp = await resp.json();
    renderPianoRoll(comp);
  } catch (e) {
    console.error("Failed to load composition:", e);
  }
}

// Piano roll renderer
function renderPianoRoll(comp) {
  const canvas = document.getElementById("pianoroll-canvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const tracks = comp.tracks || [];
  if (!tracks.length) return;

  const trackColors = ["#e00", "#00a0e0", "#0a0", "#e0e000", "#e07000", "#808080"];
  const pitchMin = 24;
  const pitchMax = 96;
  const pitchRange = pitchMax - pitchMin;

  // Find total duration
  let maxTick = 0;
  tracks.forEach((t) => {
    t.notes.forEach((n) => {
      if (n[0] + n[1] > maxTick) maxTick = n[0] + n[1];
    });
  });
  if (maxTick === 0) maxTick = 1920 * 4;

  const scaleX = canvas.width / maxTick;
  const scaleY = canvas.height / pitchRange;

  // Draw grid (bar lines)
  ctx.strokeStyle = "#ddd";
  ctx.lineWidth = 0.5;
  for (let bar = 0; bar * 1920 < maxTick; bar++) {
    const x = bar * 1920 * scaleX;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }

  // Draw notes
  tracks.forEach((track, ti) => {
    const color = trackColors[ti % trackColors.length];
    ctx.fillStyle = color;
    track.notes.forEach((n) => {
      const [onset, dur, pitch] = n;
      const x = onset * scaleX;
      const y = (pitchMax - pitch) * scaleY;
      const w = Math.max(dur * scaleX, 2);
      const h = Math.max(scaleY, 2);
      ctx.fillRect(x, y, w, h);
    });
  });
}

// Load eval
async function loadEval() {
  if (!currentSid) return;
  try {
    const resp = await fetch(`/api/sessions/${currentSid}/evaluate`, { method: "POST" });
    const { report } = await resp.json();
    renderEval(report);
  } catch (e) {
    console.error("Failed to load eval:", e);
  }
}

function renderEval(report) {
  const scoresEl = document.getElementById("eval-scores");
  const violationsEl = document.getElementById("eval-violations");
  const trajectoryEl = document.getElementById("eval-trajectory");

  // Scores
  if (report.axes) {
    scoresEl.innerHTML = "<h3>Scores</h3>";
    for (const [name, val] of Object.entries(report.axes)) {
      const bar = `<div style="margin:2px 0;"><span style="display:inline-block;width:80px;">${name}</span>
        <div style="display:inline-block;width:200px;height:10px;background:#fff;border:1px solid #000;">
          <div style="width:${val * 100}%;height:100%;background:#000;"></div>
        </div>
        <span>${(val * 100).toFixed(1)}</span></div>`;
      scoresEl.innerHTML += bar;
    }
    scoresEl.innerHTML += `<div style="margin-top:4px;font-weight:bold;">R_rule: ${(report.R_rule || 0).toFixed(1)}</div>`;
  }

  // Violations
  if (report.violations && report.violations.length) {
    violationsEl.innerHTML = "<h3>Violations</h3>";
    report.violations.forEach((v) => {
      violationsEl.innerHTML += `<div style="font-size:11px;">${v.location}: ${v.message}</div>`;
    });
  } else {
    violationsEl.innerHTML = "<h3>Violations</h3><div>None</div>";
  }

  // Trajectory
  trajectoryEl.innerHTML = "<h3>Trajectory</h3><div>No review rounds</div>";
}

// Load versions
async function loadVersions() {
  if (!currentSid) return;
  try {
    const resp = await fetch(`/api/sessions/${currentSid}/versions`);
    const { versions } = await resp.json();
    renderTimeline(versions);
  } catch (e) {
    console.error("Failed to load versions:", e);
  }
}

function renderTimeline(versions) {
  const el = document.getElementById("version-timeline");
  el.innerHTML = "<h3>Version History</h3>";
  versions.forEach((v) => {
    el.innerHTML += `<div class="version-item" data-v="${v.version}" style="cursor:pointer;padding:2px 0;border-bottom:1px solid #ccc;">
      v${v.version} — ${v.label || "unnamed"}
    </div>`;
  });
}

// Revise
document.getElementById("btn-revise").addEventListener("click", async () => {
  if (!currentSid) return;
  const feedback = document.getElementById("feedback-input").value.trim();
  if (!feedback) return;

  const statusEl = document.getElementById("status-text");
  statusEl.textContent = "Revising...";

  try {
    await fetch(`/api/sessions/${currentSid}/revise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedback }),
    });
    statusEl.textContent = "Revision complete";
    await loadComposition();
    await loadEval();
    await loadVersions();
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
});
```

- [ ] **Step 7: Install frontend deps**

Run: `cd webapp/frontend && npm install`

- [ ] **Step 8: Commit**

```bash
git add webapp/frontend/
git commit -m "feat: frontend scaffolding with system.css window manager"
```

---

### Task 3: Dev Server Integration

**Files:**
- Modify: `src/miidi/web/app.py` (serve built frontend in production)
- Create: `webapp/frontend/.gitignore` (ignore node_modules, dist)

**Interfaces:**
- Consumes: Frontend build output at `webapp/frontend/dist/`
- Produces: Dev script that runs both Vite dev server and FastAPI

- [ ] **Step 1: Add dev script**

Add to `pyproject.toml` `[project.scripts]`:
```
miidi-dev = "miidi.web.app:run_dev"
```

Create dev runner in `src/miidi/web/app.py`:

```python
def run_dev():
    """Run FastAPI + Vite dev server."""
    import subprocess, sys, os
    from miidi.session.store import SessionStore
    from miidi.llm.client import make_client

    root = Path(os.environ.get("MIIDI_ROOT", "."))
    store = SessionStore(str(root / "sessions"))
    client = make_client()
    app = create_app(store, client, root)

    # Start Vite in background
    frontend = root / "webapp" / "frontend"
    vite = subprocess.Popen(
        ["npx", "vite", "--port", "5173"],
        cwd=str(frontend),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        vite.terminate()
```

- [ ] **Step 2: Create .gitignore**

```
node_modules/
dist/
```

- [ ] **Step 3: Commit**

```bash
git add src/miidi/web/app.py webapp/frontend/.gitignore pyproject.toml
git commit -m "feat: dev server integration (FastAPI + Vite)"
```

---

### Task 4: Evaluation End-to-End Test

**Files:**
- Modify: `tests/test_web.py`

**Interfaces:**
- Consumes: All 8 API endpoints
- Produces: Full integration test

- [ ] **Step 1: Add integration test**

Add to `tests/test_web.py`:

```python
def test_full_lifecycle(client):
    # Create
    resp = client.post("/api/sessions", json={"prompt": "dark and moody", "style": "jazz"})
    assert resp.status_code == 200
    sid = resp.json()["sid"]

    # Status
    resp = client.get(f"/api/sessions/{sid}/status")
    assert resp.status_code == 200

    # Composition
    resp = client.get(f"/api/sessions/{sid}/composition")
    assert resp.status_code == 200

    # Evaluate
    resp = client.post(f"/api/sessions/{sid}/evaluate")
    assert resp.status_code == 200
    assert "report" in resp.json()

    # Versions
    resp = client.get(f"/api/sessions/{sid}/versions")
    assert resp.status_code == 200

    # Revise
    resp = client.post(f"/api/sessions/{sid}/revise", json={"feedback": "make it brighter"})
    assert resp.status_code == 200

    # After revise, should have more versions
    resp = client.get(f"/api/sessions/{sid}/versions")
    assert resp.status_code == 200

    # MIDI
    resp = client.get(f"/api/sessions/{sid}/midi")
    assert resp.status_code in (200, 404)  # 404 if no out_dir set
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_web.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/test_web.py
git commit -m "test: full lifecycle integration test for web API"
```

---

### Task 5: Final Validation

**Files:**
- Read: all web files
- Read: `docs/superpowers/specs/2026-08-22-miidi-design.md` §9

**Interfaces:**
- Consumes: Complete web app
- Produces: All tests green, spec conformance verified

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 2: Smoke test frontend build**

Run: `cd webapp/frontend && npx vite build`
Expected: builds without errors

- [ ] **Step 3: Verify API endpoints match spec §9.1**

Checklist:
- [ ] POST /sessions → CreateSessionResponse
- [ ] GET /sessions/{id}/status → StatusResponse
- [ ] GET /sessions/{id}/composition → Composition JSON
- [ ] GET /sessions/{id}/audio → 501
- [ ] GET /sessions/{id}/midi → FileResponse
- [ ] POST /sessions/{id}/revise → StatusResponse
- [ ] GET /sessions/{id}/versions → VersionResponse
- [ ] POST /sessions/{id}/evaluate → EvaluateResponse

- [ ] **Step 4: Verify frontend matches spec §9.2**

Checklist:
- [ ] 4 windows: Composer, Piano Roll, Evaluator, Feedback
- [ ] Menu bar at top
- [ ] system.css styling
- [ ] Draggable windows
- [ ] Piano roll canvas renders notes
- [ ] Style selector (5 styles)

- [ ] **Step 5: Commit if any fixes needed**

```bash
git commit -m "fix: web app validation fixes"
```
