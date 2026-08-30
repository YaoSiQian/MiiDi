import { WindowManager } from "./window-manager.js";

const STYLES = ["pop", "classical", "jazz", "lofi", "touhou"];

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
let currentSid = null;
let currentTracks = [];
let midiPlayer = null;

// Initialize
const wm = new WindowManager();

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

// Flow bar navigation — backward and forward to next step
document.querySelectorAll(".flow-step").forEach((el) => {
  el.addEventListener("click", () => {
    const step = parseInt(el.dataset.step, 10);
    if (step === currentStep) return;
    if (step < currentStep && completedSteps.has(step)) {
      setStep(step);
    } else if (step === currentStep + 1) {
      setStep(step);
    }
  });
});

// Intro → Step 1
document.getElementById("btn-get-started").addEventListener("click", () => {
  setStep(STEPS.COMPOSE);
});

function getSelectedStyle() {
  const checked = document.querySelector('input[name="style"]:checked');
  return checked ? checked.value : "touhou";
}

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
      body: JSON.stringify({ prompt, style: getSelectedStyle(), stages: ["plan", "core"] }),
    });
    const data = await resp.json();
    currentSid = data.sid;
    fillEl.style.width = "30%";
    statusEl.textContent = `Session ${currentSid} — generating core tracks...`;

    // Poll until generation is done
    await pollUntilReady(currentSid, statusEl, fillEl);

    setStep(STEPS.PREVIEW);
    await loadComposition();
    await loadEval();
    await loadVersions();
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
});

async function pollUntilReady(sid, statusEl, fillEl) {
  for (let i = 0; i < 300; i++) { // max ~50 min (10s interval)
    await new Promise((r) => setTimeout(r, 10000));
    try {
      const resp = await fetch(`/api/sessions/${sid}/status`);
      const data = await resp.json();
      if (data.stage === "done") {
        fillEl.style.width = "100%";
        statusEl.textContent = `Session ${sid} ready`;
        return;
      }
      fillEl.style.width = `${30 + Math.min(i * 2, 60)}%`;
      statusEl.textContent = `Session ${sid} — ${data.stage}...`;
    } catch (_) {
      // retry
    }
  }
  throw new Error("Generation timed out");
}

// Load composition into piano roll
async function loadComposition() {
  if (!currentSid) return;
  try {
    const resp = await fetch(`/api/sessions/${currentSid}/composition`);
    const comp = await resp.json();
    currentTracks = comp.tracks || [];
    renderPianoRoll(comp);
  } catch (e) {
    console.error("Failed to load composition:", e);
  }
}

// Piano roll renderer
function renderPianoRoll(comp) {
  const canvas = document.getElementById("pianoroll-canvas");
  const emptyEl = document.getElementById("pianoroll-empty");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const tracks = comp.tracks || [];
  const hasNotes = tracks.some((t) => t.notes && t.notes.length > 0);

  if (!hasNotes) {
    canvas.style.display = "none";
    if (emptyEl) emptyEl.style.display = "";
    return;
  }

  if (emptyEl) emptyEl.style.display = "none";
  canvas.style.display = "";

  const trackColors = ["#e00", "#00a0e0", "#0a0", "#e0e000", "#e07000", "#808080"];
  const pitchMin = 24;
  const pitchMax = 96;
  const pitchRange = pitchMax - pitchMin;

  let maxTick = 0;
  tracks.forEach((t) => {
    t.notes.forEach((n) => {
      if (n[0] + n[1] > maxTick) maxTick = n[0] + n[1];
    });
  });
  if (maxTick === 0) maxTick = 1920 * 4;

  const scaleX = canvas.width / maxTick;
  const scaleY = canvas.height / pitchRange;

  ctx.strokeStyle = "#ddd";
  ctx.lineWidth = 0.5;
  for (let bar = 0; bar * 1920 < maxTick; bar++) {
    const x = bar * 1920 * scaleX;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }

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
    const { report, composite } = await resp.json();
    renderEval(report, composite);
    loadTrajectory().catch(() => {}); // non-blocking
    if (currentStep === STEPS.PREVIEW) {
      setStep(STEPS.EVALUATE);
    }
  } catch (e) {
    console.error("Failed to load eval:", e);
  }
}

// Load trajectory from status endpoint
async function loadTrajectory() {
  if (!currentSid) return;
  try {
    const resp = await fetch(`/api/sessions/${currentSid}/status`);
    const data = await resp.json();
    renderTrajectory(data);
  } catch (e) {
    console.error("Failed to load trajectory:", e);
  }
}

function renderEval(report, composite) {
  const scoresEl = document.getElementById("eval-scores");
  const violationsEl = document.getElementById("eval-violations");
  const trajectoryEl = document.getElementById("eval-trajectory");

  if (report.axes) {
    scoresEl.innerHTML = "<h3>Scores</h3>";
    for (const [name, axis] of Object.entries(report.axes)) {
      const score = typeof axis === "object" && axis !== null ? axis.score : axis;
      const bar = `<div style="margin:2px 0;"><span style="display:inline-block;width:80px;">${name}</span>
        <div style="display:inline-block;width:200px;height:10px;background:#fff;border:1px solid #000;">
          <div style="width:${score * 100}%;height:100%;background:#000;"></div>
        </div>
        <span>${(score * 100).toFixed(1)}</span></div>`;
      scoresEl.innerHTML += bar;
    }
    scoresEl.innerHTML += `<div style="margin-top:4px;font-weight:bold;">R_rule: ${(report.R_rule || 0).toFixed(1)}</div>`;
  }

  if (composite) {
    const compDiv = document.createElement('div');
    compDiv.className = 'eval-composite';
    compDiv.innerHTML = `
      <h3>Composite Score</h3>
      <div class="composite-score">${composite.composite.toFixed(1)}</div>
      <div class="composite-breakdown">
        R_rule: ${composite.R_rule.toFixed(1)} (60%) |
        Judge: ${composite.Judge_mean.toFixed(1)} (40%)
      </div>
      <div class="judge-scores">
        J1 Style: ${composite.J1.toFixed(1)} |
        J2 Prompt: ${composite.J2.toFixed(1)} |
        J3 Musical: ${composite.J3.toFixed(1)}
      </div>
    `;
    scoresEl.appendChild(compDiv);
  }

  if (report.violations && report.violations.length) {
    violationsEl.innerHTML = "<h3>Violations</h3>";
    report.violations.forEach((v) => {
      violationsEl.innerHTML += `<div style="font-size:11px;">${v.location}: ${v.message}</div>`;
    });
  } else {
    violationsEl.innerHTML = "<h3>Violations</h3><div>None</div>";
  }

  trajectoryEl.innerHTML = "";
}

// Render trajectory from status endpoint (arrangement + review rounds)
function renderTrajectory(data) {
  const el = document.getElementById("eval-trajectory");
  if (!el) return;

  const stageLog = data.stage_log || [];
  const trajectory = data.trajectory || [];

  let html = "<h3>Pipeline</h3>";

  // Show arrangement adjustments from stage_log
  const arrangeEntry = stageLog.find((s) => s.startsWith("arrangement:"));
  if (arrangeEntry) {
    html += `<div style="font-size:11px;margin:2px 0;">${arrangeEntry}</div>`;
  }

  // Show review rounds
  if (trajectory.length) {
    trajectory.forEach((r) => {
      html += `<div style="font-size:11px;margin:2px 0;">Round ${r.round}: R_rule=${r.R_rule} — ${r.action}</div>`;
    });
  } else {
    html += `<div style="font-size:11px;color:#999;">No review rounds</div>`;
  }

  el.innerHTML = html;
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
    setStep(STEPS.PREVIEW);
    await loadComposition();
    await loadEval();
    await loadVersions();
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
});

// New Session — reset to Step 1
document.querySelector('a[href="#new"]').addEventListener("click", (e) => {
  e.preventDefault();
  if (midiPlayer) { midiPlayer.stop(); midiPlayer = null; }
  currentSid = null;
  currentTracks = [];
  completedSteps.clear();
  document.getElementById("prompt-input").value = "";
  document.getElementById("feedback-input").value = "";
  document.getElementById("status-text").textContent = "";
  document.getElementById("progress-bar").style.display = "none";
  document.getElementById("eval-scores").innerHTML = "";
  document.getElementById("eval-violations").innerHTML = "";
  document.getElementById("eval-trajectory").innerHTML = "";
  document.getElementById("version-timeline").innerHTML = "";

  const canvas = document.getElementById("pianoroll-canvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  canvas.style.display = "none";
  const emptyEl = document.getElementById("pianoroll-empty");
  if (emptyEl) emptyEl.style.display = "";

  setStep(STEPS.INTRO);
});

// MIDI Upload
document.getElementById("btn-upload-midi").addEventListener("click", () => {
  document.getElementById("midi-file-input").click();
});

document.getElementById("midi-file-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const buf = await file.arrayBuffer();
    const tracks = parseMidi(new Uint8Array(buf));
    currentTracks = tracks;
    renderPianoRoll({ tracks });
    document.getElementById("status-text").textContent = `Loaded: ${file.name}`;
    setStep(STEPS.PREVIEW);
  } catch (err) {
    document.getElementById("status-text").textContent = `MIDI parse error: ${err.message}`;
  }
});

// ─── MIDI Player (Web Audio API) ───────────────────────────────
class MidiPlayer {
  constructor(tracks) {
    this.ctx = null;
    this.playing = false;
    this.pauseTime = 0;
    this.startOffset = 0;
    this.scheduled = [];
    this.tickTimer = null;

    // Flatten all notes into events: {onset (seconds), dur (seconds), pitch, vel, trackIdx}
    this.events = [];
    tracks.forEach((t, ti) => {
      (t.notes || []).forEach((n) => {
        this.events.push({ onset: n[0], dur: n[1], pitch: n[2], vel: n[3] || 100, trackIdx: ti });
      });
    });
    this.events.sort((a, b) => a.onset - b.onset);
    this.duration = this.events.length ? Math.max(...this.events.map(e => e.onset + e.dur)) : 0;
  }

  _freq(pitch) { return 440 * Math.pow(2, (pitch - 69) / 12); }

  _waveform(trackIdx) {
    // Simple waveform selection by track index
    const waves = ['triangle', 'sine', 'square', 'sawtooth', 'triangle', 'sine'];
    return waves[trackIdx % waves.length];
  }

  _gain(vel) { return (vel / 127) * 0.15; }

  play(onTick) {
    if (this.playing) return;
    this.ctx = this.ctx || new AudioContext();
    if (this.ctx.state === 'suspended') this.ctx.resume();

    this.playing = true;
    this.startOffset = this.pauseTime;
    const now = this.ctx.currentTime;
    this._playStartTime = now;
    const offset = this.startOffset;

    // Schedule all notes
    this.scheduled = [];
    for (const ev of this.events) {
      if (ev.onset + ev.dur <= offset) continue;
      const start = now + (ev.onset - offset);
      const dur = ev.dur;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = this._waveform(ev.trackIdx);
      osc.frequency.value = this._freq(ev.pitch);
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(this._gain(ev.vel), start + 0.01);
      gain.gain.setValueAtTime(this._gain(ev.vel), start + dur - 0.02);
      gain.gain.linearRampToValueAtTime(0, start + dur);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(start);
      osc.stop(start + dur);
      this.scheduled.push(osc);
    }

    // Tick callback for cursor
    const tick = () => {
      if (!this.playing) return;
      const elapsed = this.ctx.currentTime - now + offset;
      if (elapsed >= this.duration) { this.stop(); return; }
      if (onTick) onTick(elapsed / this.duration);
      this.tickTimer = requestAnimationFrame(tick);
    };
    this.tickTimer = requestAnimationFrame(tick);
  }

  pause() {
    if (!this.playing) return;
    this.playing = false;
    const now = this.ctx.currentTime;
    // We can't perfectly track offset without storing start time, so approximate
    // Better approach: store the actual elapsed time
    this.pauseTime = this.startOffset + (now - this._playStartTime);
    this.scheduled.forEach(o => { try { o.stop(); } catch (_) {} });
    this.scheduled = [];
    if (this.tickTimer) cancelAnimationFrame(this.tickTimer);
  }

  stop() {
    this.playing = false;
    this.pauseTime = 0;
    this.scheduled.forEach(o => { try { o.stop(); } catch (_) {} });
    this.scheduled = [];
    if (this.tickTimer) cancelAnimationFrame(this.tickTimer);
  }
}

// ─── MIDI Parser ────────────────────────────────────────────────
function parseMidi(data) {
  let p = 0;
  const readStr = (len) => { let s = ""; for (let i = 0; i < len; i++) s += String.fromCharCode(data[p++]); return s; };
  const readU32 = () => (data[p++] << 24 | data[p++] << 16 | data[p++] << 8 | data[p++]) >>> 0;
  const readU16 = () => data[p++] << 8 | data[p++];
  const readVarLen = () => { let v = 0; for (let i = 0; i < 4; i++) { v = (v << 7) | (data[p] & 0x7f); if (!(data[p++] & 0x80)) break; } return v; };

  if (readStr(4) !== "MThd") throw new Error("Not a MIDI file");
  const hdrLen = readU32();
  const format = readU16();
  const numTracks = readU16();
  const ppq = readU16();
  p += hdrLen - 6;

  // Find tempo: scan raw bytes for FF 51 03 pattern
  let usPerQuarter = 500000; // default 120 BPM
  for (let i = 0; i < data.length - 5; i++) {
    if (data[i] === 0xff && data[i+1] === 0x51 && data[i+2] === 0x03) {
      usPerQuarter = (data[i+3] << 16 | data[i+4] << 8 | data[i+5]) >>> 0;
      break;
    }
  }
  const secPerTick = usPerQuarter / 1000000 / ppq;

  const result = [];
  for (let t = 0; t < numTracks; t++) {
    if (readStr(4) !== "MTrk") throw new Error("Invalid track chunk");
    const trackLen = readU32();
    const trackEnd = p + trackLen;
    const notes = [];
    let absTick = 0;
    let runningStatus = 0;
    const pending = {};

    while (p < trackEnd) {
      absTick += readVarLen();
      let status = data[p];
      if (status < 0x80) { status = runningStatus; } else { p++; runningStatus = status; }
      const hi = status & 0xf0;

      if (hi === 0x90 || hi === 0x80) {
        const ch = status & 0x0f;
        const note = data[p++];
        const vel = data[p++];
        if (hi === 0x90 && vel > 0) {
          pending[ch + "-" + note] = absTick;
        } else {
          const onTick = pending[ch + "-" + note];
          if (onTick !== undefined) {
            notes.push([onTick * secPerTick, (absTick - onTick) * secPerTick, note, vel || 100]);
            delete pending[ch + "-" + note];
          }
        }
      } else if (hi === 0xc0 || hi === 0xd0) { p++; }
        else if (hi === 0xe0) { p += 2; }
        else if (status === 0xff) { const mt = data[p++]; const len = readVarLen(); p += len; }
        else if (status === 0xf0) { while (data[p++] !== 0xf7); }
        else if (status === 0xf2) { p += 2; }
        else if (status === 0xf3) { p++; }
    }
    if (notes.length) {
      result.push({ name: `Track ${t + 1}`, program: 0, role: "melody", is_drum: false, notes });
    }
  }
  return result;
}

// ─── Playback controls ──────────────────────────────────────────
function renderCursor(fraction) {
  const canvas = document.getElementById("pianoroll-canvas");
  const ctx = canvas.getContext("2d");
  // Redraw the entire piano roll then draw cursor on top
  renderPianoRoll({ tracks: currentTracks });
  if (fraction > 0) {
    const x = fraction * canvas.width;
    ctx.strokeStyle = "#f00";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
}

document.getElementById("btn-play").addEventListener("click", () => {
  if (!currentTracks.length) return;
  if (midiPlayer && midiPlayer.playing) {
    midiPlayer.pause();
    document.getElementById("btn-play").textContent = "Play";
    return;
  }
  if (midiPlayer && midiPlayer.pauseTime > 0) {
    midiPlayer.play(renderCursor);
    document.getElementById("btn-play").textContent = "Pause";
    return;
  }
  midiPlayer = new MidiPlayer(currentTracks);
  midiPlayer.play(renderCursor);
  document.getElementById("btn-play").textContent = "Pause";
});

document.getElementById("btn-stop").addEventListener("click", () => {
  if (midiPlayer) {
    midiPlayer.stop();
    midiPlayer = null;
  }
  document.getElementById("btn-play").textContent = "Play";
  renderPianoRoll({ tracks: currentTracks });
});

// Start at Intro
setStep(STEPS.INTRO);
