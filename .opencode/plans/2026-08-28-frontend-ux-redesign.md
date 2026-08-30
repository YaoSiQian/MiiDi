# Frontend UX Redesign: Flow-Guided Multi-Window Layout

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a flow indicator bar, introduction window, and window dimming to guide users through the Compose → Preview → Evaluate → Revise pipeline.

**Architecture:** Add a flow indicator bar below the menu bar showing 4 numbered steps. Add an introduction window that appears on first load. Implement window dimming (opacity transitions) based on the current step. Wire step transitions to Generate/Eval/Revise actions.

**Tech Stack:** Vanilla JS, Vite, `@sakun/system.css`

**Spec:** `docs/superpowers/specs/2026-08-28-frontend-ux-redesign.md`

## Global Constraints

- CSS must not override system.css element-level rules (textarea, input, button, canvas, h1, body)
- system.css loaded from CDN: `https://unpkg.com/@sakun/system.css/dist/system.css`
- No close/resize buttons on windows (already removed from JS, remove from HTML)
- Windows use `position: absolute` within `.desktop` container
- Build: `npm run build` in `webapp/frontend/`
- Tests: `python -m pytest tests/ -q` (200 tests, no Python changes)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `webapp/frontend/index.html` | Modify | Add flow bar + intro window, remove close/resize buttons |
| `webapp/frontend/style.css` | Modify | Add flow bar, hint, dimming, intro styles |
| `webapp/frontend/js/app.js` | Modify | Step state machine, transitions, hint updates |

---

### Task 1: Add Flow Indicator Bar HTML and CSS

**Files:**
- Modify: `webapp/frontend/index.html:27-28` (after menu bar, before desktop)
- Modify: `webapp/frontend/style.css` (append new styles)

**Interfaces:**
- Consumes: nothing
- Produces: `.flow-bar`, `.flow-step`, `.flow-connector`, `.flow-hint` DOM elements

- [ ] **Step 1: Add flow indicator bar HTML**

In `index.html`, insert after the closing `</ul>` (menu bar) and before `<div class="desktop">`:

```html
  <div class="flow-bar" id="flow-bar">
    <span class="flow-step active" data-step="1">1. Compose</span>
    <span class="flow-connector">→</span>
    <span class="flow-step future" data-step="2">2. Preview</span>
    <span class="flow-connector">→</span>
    <span class="flow-step future" data-step="3">3. Evaluate</span>
    <span class="flow-connector">→</span>
    <span class="flow-step future" data-step="4">4. Revise</span>
  </div>
  <div class="flow-hint" id="flow-hint">Write your prompt and choose a style</div>
```

- [ ] **Step 2: Add flow bar CSS**

Append to `style.css`:

```css
.flow-bar {
  background: #fff;
  border-bottom: 0.1rem solid #000;
  padding: 6px 16px;
  display: flex;
  align-items: center;
}
.flow-step {
  padding: 3px 10px;
  font-size: 13px;
  cursor: default;
  white-space: nowrap;
}
.flow-step.active {
  background: #000;
  color: #fff;
}
.flow-step.completed {
  cursor: pointer;
}
.flow-step.future {
  opacity: 0.5;
}
.flow-connector {
  width: 24px;
  text-align: center;
  color: #999;
  font-size: 12px;
}
.flow-hint {
  font-size: 12px;
  color: #666;
  padding: 2px 16px 4px;
  background: #fff;
  border-bottom: 0.1rem solid #000;
}
```

- [ ] **Step 3: Build and verify**

Run: `npm run build` in `webapp/frontend/`
Expected: build succeeds, flow bar visible below menu bar

---

### Task 2: Add Introduction Window

**Files:**
- Modify: `webapp/frontend/index.html:30-59` (inside `.desktop`, before Composer window)
- Modify: `webapp/frontend/style.css` (append intro styles)

**Interfaces:**
- Consumes: nothing
- Produces: `#window-intro` DOM element, `#btn-get-started` button

- [ ] **Step 1: Add intro window HTML**

In `index.html`, insert as the first child of `<div class="desktop">` (before `#window-composer`):

```html
    <div class="window" id="window-intro" style="left:40px;top:40px;width:420px;">
      <div class="title-bar">
        <h1 class="title">Welcome to MiiDi</h1>
      </div>
      <div class="separator"></div>
      <div class="window-pane">
        <p>AI-powered symbolic music generation with a custom dual-track evaluation system.</p>
        <h3>How it works</h3>
        <div class="flow-overview">
          <div class="flow-overview-step">1. Compose — Write a prompt and choose a style</div>
          <div class="flow-overview-step">2. Preview — See your composition as a piano roll</div>
          <div class="flow-overview-step">3. Evaluate — Review automatic quality scores</div>
          <div class="flow-overview-step">4. Revise — Give feedback and regenerate</div>
        </div>
        <button class="btn" id="btn-get-started">Get Started</button>
      </div>
    </div>
```

- [ ] **Step 2: Add intro CSS**

Append to `style.css`:

```css
.flow-overview {
  margin: 12px 0;
}
.flow-overview-step {
  padding: 4px 0;
  font-size: 14px;
}
```

- [ ] **Step 3: Build and verify**

Run: `npm run build` in `webapp/frontend/`
Expected: build succeeds, intro window visible in top-left of desktop

---

### Task 3: Remove Close/Resize Buttons from HTML

**Files:**
- Modify: `webapp/frontend/index.html` (all 4 window title bars)

**Interfaces:**
- Consumes: nothing
- Produces: cleaner HTML without non-functional buttons

- [ ] **Step 1: Remove close and resize buttons**

In `index.html`, remove all `<button aria-label="Close" class="close"></button>` and `<button aria-label="Resize" class="resize"></button>` elements from all 4 windows (Composer, Piano Roll, Evaluator, Feedback). Each title bar should only contain `<h1 class="title">`.

Before:
```html
      <div class="title-bar">
        <button aria-label="Close" class="close"></button>
        <h1 class="title">Composer</h1>
        <button aria-label="Resize" class="resize"></button>
      </div>
```

After:
```html
      <div class="title-bar">
        <h1 class="title">Composer</h1>
      </div>
```

- [ ] **Step 2: Build and verify**

Run: `npm run build` in `webapp/frontend/`
Expected: build succeeds, no close/resize buttons visible

---

### Task 4: Add Window Dimming CSS

**Files:**
- Modify: `webapp/frontend/style.css` (append dimming styles)

**Interfaces:**
- Consumes: nothing
- Produces: `.dimmed`, `.reference` CSS classes for `.window`

- [ ] **Step 1: Add dimming CSS**

Append to `style.css`:

```css
.desktop .window {
  transition: opacity 0.2s;
}
.desktop .window.dimmed {
  opacity: 0.3;
  pointer-events: none;
}
.desktop .window.reference {
  opacity: 0.6;
}
```

- [ ] **Step 2: Build and verify**

Run: `npm run build` in `webapp/frontend/`
Expected: build succeeds

---

### Task 5: Implement Step State Machine in app.js

**Files:**
- Modify: `webapp/frontend/js/app.js` (add step state, setStep function, wire transitions)

**Interfaces:**
- Consumes: `.flow-step[data-step]` elements, `#flow-hint`, `#window-intro`, `#btn-get-started`
- Produces: `setStep(n)` function, `STEP_HINTS` constant, step transition logic

- [ ] **Step 1: Add step constants and state**

At the top of `app.js` (after imports, before `const STYLES`), add:

```javascript
const STEPS = {
  INTRO: 0,
  COMPOSE: 1,
  PREVIEW: 2,
  EVALUATE: 3,
  REVISE: 4,
};

const STEP_HINTS = {
  [STEPS.INTRO]: "Welcome to MiiDi",
  [STEPS.COMPOSE]: "Write your prompt and choose a style",
  [STEPS.PREVIEW]: "Your composition is ready — preview it below",
  [STEPS.EVALUATE]: "Review evaluation scores and violations",
  [STEPS.REVISE]: "Describe what to change, then revise",
};

const STEP_WINDOWS = {
  [STEPS.INTRO]: { active: ["window-intro"], reference: [], dimmed: ["window-composer", "window-pianoroll", "window-evaluator", "window-feedback"] },
  [STEPS.COMPOSE]: { active: ["window-composer"], reference: [], dimmed: ["window-intro", "window-pianoroll", "window-evaluator", "window-feedback"] },
  [STEPS.PREVIEW]: { active: ["window-composer", "window-pianoroll"], reference: [], dimmed: ["window-intro", "window-evaluator", "window-feedback"] },
  [STEPS.EVALUATE]: { active: ["window-pianoroll", "window-evaluator"], reference: ["window-composer"], dimmed: ["window-intro", "window-feedback"] },
  [STEPS.REVISE]: { active: ["window-feedback", "window-composer"], reference: ["window-pianoroll"], dimmed: ["window-intro", "window-evaluator"] },
};

let currentStep = STEPS.INTRO;
let completedSteps = new Set();
```

- [ ] **Step 2: Add setStep function**

After the state variables, add:

```javascript
function setStep(step) {
  currentStep = step;
  completedSteps.add(step);

  // Update flow bar
  document.querySelectorAll(".flow-step").forEach((el) => {
    const s = parseInt(el.dataset.step, 10);
    el.classList.remove("active", "completed", "future");
    if (s === step) {
      el.classList.add("active");
    } else if (completedSteps.has(s)) {
      el.classList.add("completed");
    } else {
      el.classList.add("future");
    }
  });

  // Update hint
  const hintEl = document.getElementById("flow-hint");
  if (hintEl) hintEl.textContent = STEP_HINTS[step] || "";

  // Update window visibility
  const layout = STEP_WINDOWS[step];
  if (layout) {
    layout.active.forEach((id) => {
      const win = document.getElementById(id);
      if (win) { win.classList.remove("dimmed", "reference"); win.style.display = ""; }
    });
    layout.reference.forEach((id) => {
      const win = document.getElementById(id);
      if (win) { win.classList.remove("dimmed"); win.classList.add("reference"); win.style.display = ""; }
    });
    layout.dimmed.forEach((id) => {
      const win = document.getElementById(id);
      if (win) { win.classList.remove("reference"); win.classList.add("dimmed"); }
    });
  }
}
```

- [ ] **Step 3: Wire flow bar click navigation**

After `setStep` function, add:

```javascript
// Flow bar backward navigation
document.querySelectorAll(".flow-step").forEach((el) => {
  el.addEventListener("click", () => {
    const step = parseInt(el.dataset.step, 10);
    if (completedSteps.has(step) && step < currentStep) {
      setStep(step);
    }
  });
});
```

- [ ] **Step 4: Wire Get Started button**

After the flow bar navigation, add:

```javascript
// Intro → Step 1
document.getElementById("btn-get-started").addEventListener("click", () => {
  setStep(STEPS.COMPOSE);
});
```

- [ ] **Step 5: Build and verify**

Run: `npm run build` in `webapp/frontend/`
Expected: build succeeds

---

### Task 6: Wire Step Transitions to Pipeline Actions

**Files:**
- Modify: `webapp/frontend/js/app.js` (modify Generate, Eval, Revise handlers)

**Interfaces:**
- Consumes: `setStep()`, `STEPS` constants
- Produces: step transitions after Generate, Eval, Revise

- [ ] **Step 1: Update Generate handler to advance to Step 2**

In the existing `btn-generate` click handler, after `await loadVersions()`, add:

```javascript
    setStep(STEPS.PREVIEW);
```

The full handler becomes:
```javascript
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
      body: JSON.stringify({ prompt, style: getSelectedStyle() }),
    });
    const data = await resp.json();
    currentSid = data.sid;
    statusEl.textContent = `Session ${data.sid} created`;
    fillEl.style.width = "100%";

    await loadComposition();
    await loadEval();
    await loadVersions();
    setStep(STEPS.PREVIEW);
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
});
```

- [ ] **Step 2: Add eval auto-advance to Step 3**

In the existing `loadEval` function, after `renderEval(report)`, add:

```javascript
    if (currentStep === STEPS.PREVIEW) {
      setStep(STEPS.EVALUATE);
    }
```

The full function becomes:
```javascript
async function loadEval() {
  if (!currentSid) return;
  try {
    const resp = await fetch(`/api/sessions/${currentSid}/evaluate`, { method: "POST" });
    const { report } = await resp.json();
    renderEval(report);
    if (currentStep === STEPS.PREVIEW) {
      setStep(STEPS.EVALUATE);
    }
  } catch (e) {
    console.error("Failed to load eval:", e);
  }
}
```

- [ ] **Step 3: Update Revise handler to advance to Step 2**

In the existing `btn-revise` click handler, after `await loadVersions()`, add:

```javascript
    setStep(STEPS.PREVIEW);
```

The full handler becomes:
```javascript
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
    setStep(STEPS.PREVIEW);
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
});
```

- [ ] **Step 4: Add New Session menu handler**

At the end of `app.js`, add:

```javascript
// New Session — reset to Step 1
document.querySelector('a[href="#new"]').addEventListener("click", (e) => {
  e.preventDefault();
  currentSid = null;
  completedSteps.clear();
  document.getElementById("prompt-input").value = "";
  document.getElementById("feedback-input").value = "";
  document.getElementById("status-text").textContent = "";
  document.getElementById("progress-bar").style.display = "none";
  document.getElementById("eval-scores").innerHTML = "";
  document.getElementById("eval-violations").innerHTML = "";
  document.getElementById("eval-trajectory").innerHTML = "";
  document.getElementById("version-timeline").innerHTML = "";

  // Clear piano roll
  const canvas = document.getElementById("pianoroll-canvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  setStep(STEPS.COMPOSE);
});
```

- [ ] **Step 5: Initialize to Step 1 on load**

At the end of `app.js` (after all event listeners), add:

```javascript
// Start at Step 1 (after intro)
setStep(STEPS.INTRO);
```

- [ ] **Step 6: Build and verify**

Run: `npm run build` in `webapp/frontend/`
Expected: build succeeds

---

### Task 7: Final Build and Integration Test

**Files:**
- No file changes (verification only)

**Interfaces:**
- Consumes: all previous tasks
- Produces: verified build

- [ ] **Step 1: Run full build**

Run: `npm run build` in `webapp/frontend/`
Expected: build succeeds with no errors

- [ ] **Step 2: Run Python tests**

Run: `python -m pytest tests/ -q` in project root
Expected: 200 tests pass (no Python changes)

- [ ] **Step 3: Manual verification checklist**

Start the server (`python serve.py`) and verify in browser:
- [ ] Intro window visible on left, other windows dimmed
- [ ] Flow bar shows step 1 active, others dimmed
- [ ] "Get Started" transitions to Step 1 (Composer active, intro dimmed)
- [ ] Generate button advances to Step 2 (Composer + Piano Roll active)
- [ ] Eval auto-advances to Step 3 (Piano Roll + Evaluator active, Composer reference)
- [ ] Revise advances to Step 2 (Feedback + Composer active)
- [ ] Backward click on flow bar jumps to completed step
- [ ] New Session resets to Step 1
- [ ] No close/resize buttons on any window
- [ ] Windows are draggable via title bar
- [ ] Double-click title bar folds/unfolds window
