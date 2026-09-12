/*
 * MiiDi 静态演示运行时（仅在 demo 构建中随 demo-data.js 一起注入）。
 *
 * 通过包装 window.fetch 拦截全部 /api/... 请求，按状态机回放预生成的
 * 会话数据：Generate(plan) → Continue(core) → Continue(arrange) →
 * Evaluate → Revise。真实站点（无 window.MIIDI_DEMO_DATA）不受影响。
 */
(function () {
  "use strict";
  const DATA = window.MIIDI_DEMO_DATA;
  if (!DATA) return;

  const S = DATA.stateVersions; // {plan:1, core:2, arrange:4, revise:5}
  const VERSIONS = DATA.session.versions;
  const origFetch = window.fetch.bind(window);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // 当前所处阶段：null（未创建）→ plan → core → arrange → revise
  const state = { phase: null, polls: 0 };

  const STAGE_LABEL = {
    plan: "planning",
    core: "composing core tracks",
    arrange: "arranging & reviewing",
    revise: "revising",
  };

  function versionIndex(n) {
    return VERSIONS.findIndex((v) => v.version === n);
  }

  function currentVersion() {
    if (!state.phase) {
      // 未走流程（如直接从 Sessions 恢复）时回退到 arrange 完成版，保证可播放
      return (
        VERSIONS.find((v) => v.version === S.arrange) || VERSIONS[VERSIONS.length - 1]
      );
    }
    const n = S[state.phase];
    return VERSIONS.find((v) => v.version === n) || VERSIONS[0];
  }

  function sessionSummary() {
    const upto = versionIndex(currentVersion().version);
    return {
      sid: DATA.session.sid,
      prompt: DATA.session.prompt,
      style: DATA.session.style,
      created: DATA.session.created,
      versions: VERSIONS.slice(0, upto + 1).map((v) => ({
        version: v.version,
        label: v.label,
      })),
    };
  }

  function evalKeyForCurrent() {
    const n = String(currentVersion().version);
    if (DATA.evals[n]) return n;
    // 当前版本没有专属评估（如 plan/core 阶段）时回退到最早的已评估版本
    const keys = Object.keys(DATA.evals);
    return keys.length ? keys.sort((a, b) => a - b)[0] : null;
  }

  async function jsonResponse(obj, delayMs) {
    await sleep(delayMs);
    return new Response(JSON.stringify(obj), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  async function route(path, options) {
    let m;

    if (path === "/api/sessions") {
      if ((options.method || "GET") === "POST") {
        state.phase = "plan";
        state.polls = 0;
        return jsonResponse({ sid: DATA.session.sid }, 600);
      }
      return jsonResponse({ sessions: [sessionSummary()] }, 200);
    }

    m = path.match(/^\/api\/sessions\/[^/]+\/status$/);
    if (m) {
      state.polls += 1;
      if (state.phase === null) return jsonResponse({ stage: "done", stage_log: [] }, 100);
      if (state.polls === 1) {
        return jsonResponse(
          {
            stage: STAGE_LABEL[state.phase] || "generating",
            stage_log: [STAGE_LABEL[state.phase] || "generating"],
          },
          1500,
        );
      }
      return jsonResponse({ stage: "done", stage_log: [] }, 100);
    }

    m = path.match(/^\/api\/sessions\/[^/]+\/composition$/);
    if (m) return jsonResponse(currentVersion().composition, 500);

    m = path.match(/^\/api\/sessions\/[^/]+\/versions$/);
    if (m) {
      const upto = versionIndex(currentVersion().version);
      return jsonResponse({ versions: VERSIONS.slice(0, upto + 1) }, 200);
    }

    m = path.match(/^\/api\/sessions\/[^/]+\/generate$/);
    if (m) {
      const body = JSON.parse(options.body || "{}");
      const stages = body.stages || [];
      state.phase = stages.includes("arrange") ? "arrange" : "core";
      state.polls = 0;
      return jsonResponse({ sid: DATA.session.sid, accepted: true, stage_log: [] }, 600);
    }

    m = path.match(/^\/api\/sessions\/[^/]+\/evaluate$/);
    if (m) {
      const key = evalKeyForCurrent();
      if (!key) return jsonResponse({ detail: "no eval data" }, 100);
      return jsonResponse(DATA.evals[key], 1200);
    }

    m = path.match(/^\/api\/sessions\/[^/]+\/revise$/);
    if (m) {
      state.phase = "revise";
      state.polls = 0;
      await sleep(2500); // 模拟真实修订耗时
      return jsonResponse({ ok: true, version: S.revise });
    }

    m = path.match(/^\/api\/sessions\/[^/]+\/midi$/);
    if (m) return origFetch("demo.mid"); // 随包预渲染的静态 MIDI

    return undefined;
  }

  window.fetch = async function (url, options) {
    const p = String(url instanceof Request ? url.url : url);
    if (p.includes("/api/")) {
      const handled = await route(p.replace(/^.*\/\/[^/]+/, ""), options || {});
      if (handled) return handled;
    }
    return origFetch(url, options);
  };

  // ─── 引导与预填（等 DOM 与 app.js 初始化完成） ─────────────────
  function setupUi() {
    document.title = "MiiDi Demo — 演示模式";

    // 融合像素字体（与 demo 录屏字幕同款）；加载失败时回退 monospace
    const fontCss = document.createElement("style");
    fontCss.textContent = `
      @font-face {
        font-family: "Fusion Pixel 12px Monospaced zh_hans";
        src: url("https://fusion-pixel-font.takwolf.com/fusion-pixel-12px-monospaced-zh_hans.otf.woff2")
          format("woff2");
        font-display: swap;
      }`;
    document.head.appendChild(fontCss);

    const banner = document.createElement("div");
    banner.style.cssText =
      "position:fixed;top:0;left:0;right:0;z-index:9999;display:flex;gap:12px;" +
      "align-items:center;justify-content:center;background:#000;color:#fff;" +
      "border-bottom:2px solid #fff;padding:9px 12px;font-size:12px;" +
      "font-family:'Fusion Pixel 12px Monospaced zh_hans',monospace;letter-spacing:0.5px;";
    banner.innerHTML =
      "<span>🎬 演示模式 —— 所有数据已预生成，生成过程为模拟回放</span>" +
      '<a href="https://github.com/YaoSiQian/MiiDi" target="_blank" ' +
      'style="color:#7fd4ff;text-decoration:underline;">查看项目</a>' +
      '<span style="cursor:pointer;opacity:0.7;position:absolute;right:12px;" id="demo-banner-close">✕</span>';
    document.body.appendChild(banner);
    document.body.style.paddingTop = "32px";
    banner.querySelector("#demo-banner-close").addEventListener("click", () => {
      banner.remove();
      document.body.style.paddingTop = "";
    });

    const promptEl = document.getElementById("prompt-input");
    if (promptEl) promptEl.value = DATA.session.prompt;
    const styleEl = document.querySelector(`input[name="style"][value="${DATA.session.style}"]`);
    if (styleEl) styleEl.checked = true;
    const feedback = "鼓太吵了，整体密度降一点";
    const fbEl = document.getElementById("feedback-input");
    if (fbEl) fbEl.value = feedback;
    const gateFbEl = document.getElementById("gate-feedback");
    if (gateFbEl) gateFbEl.value = feedback;

    const status = document.getElementById("status-text");
    if (status) status.textContent = "演示就绪：直接点击 Generate 开始回放";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupUi);
  } else {
    setupUi();
  }
})();
