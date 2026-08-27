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
