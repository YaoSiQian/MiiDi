# AGENTS.md

## What this is

MiiDi — AI-native MIDI music generation and evaluation platform. A natural-language prompt + style pack goes through a 5-stage LLM pipeline (Plan → Core → Arrange → Coordinate → Review) to produce a `Composition` JSON, rendered to MIDI via midiutil. Quality is scored by a dual-track evaluator: deterministic rule axes (R_rule) + LLM judge (J1–J3), combined as `composite = 0.6*R_rule + 0.4*mean(J1..J3)`.

Docs are Chinese and worth reading before deep changes: `docs/architecture.md` (module map + design rationale), `docs/pipeline.md`, `docs/evaluation.md`, `docs/styles.md`, `docs/api.md`.

## Layout

- `src/miidi/` — the package (src layout):
  - `schema/` — pydantic v2 models (`model.py`), LLM-output repair (`normalize.py`), hard constraints (`validate.py`), chord symbol parsing (`chords.py`)
  - `musicutil/` — scales, `band()` score-mapping helper, GM instrument ranges/channel allocation
  - `eval/` — rule axes (`axes.py`), multiplicative anti-degeneration gates (`gates.py`), LLM judge (`judge.py`), aggregation (`score.py`/`composite.py`), shared precomputation (`context.py`)
  - `llm/` — `client.py`: dual protocol — OpenAI Responses API when `OPENAI_BASE_URL` is set, otherwise auto-fallback to OpenCode Zen (free). Retries 429/5xx with backoff; `extract_json` pulls JSON out of LLM prose
  - `skills/` — style-pack loader; packs live in repo-root `skills/<style>/` (pop, classical, jazz, lofi, touhou): `SKILL.md`, `harmony.md`, `instruments.md`, `rhythm.md`, `defaults.json`
  - `pipeline/` — stages (`stages.py`), arrangement coordinator (`orchestrator.py`), all LLM prompts (`prompts.py`), brief builder (`brief.py`)
  - `session/` — version store; snapshots written to `sessions/` (gitignored)
  - `render/` — Composition → MIDI
  - `web/` — FastAPI app (`app.py`), API routes (`routes.py`), request schemas
  - `serve.py` — web entry: `python src/miidi/serve.py` → uvicorn on :8000, loads `.env` from repo root
- `web/` — Vite + vanilla JS frontend (System 6 retro multi-window UI via `@sakun/system.css`); `js/app.js`, `js/window-manager.js`. It is `web/`, not `webapp/` — older paths were renamed, watch for stale references
- `evals/` — eval samples (`samples/*.yaml`), experiment scripts, `runners/run_eval.py`; imported as top-level `evals` module (works because `tests/conftest.py` puts repo root on sys.path)
- `tools/` — standalone MIDI analysis scripts
- `tests/` — pytest suite; LLM calls are mocked, no network or API key needed

## Commands

- Install: `pip install -e ".[dev]"`
- Tests: `python -m pytest tests/ -v`
- Lint: `ruff check src tests evals` (line length 100; isort with `miidi` as first-party)
- CLI: `python -m miidi styles` / `python -m miidi generate --style lofi --prompt "..." [--stages plan,core,...]` / `python -m miidi evaluate --json <composition.json>`
- Web backend: `python src/miidi/serve.py` (README-documented path; console script `miidi-dev` runs FastAPI + Vite dev mode)
- Frontend: `cd web && npm run dev` (:5173, proxies `/api` → :8000) / `npm run build` (→ `web/dist`, which FastAPI serves; falls back to `web/` root if dist missing)
- Full eval runs (`evals/runners/run_eval.py`) hit the real LLM API — not part of the test suite

## Layer rules

- Dependencies flow one way: `schema` → `musicutil` → `eval`/`llm`/`skills`/`render` → `pipeline` → `web`. `schema` imports nothing else in the package; `pipeline` may use everything; `web` touches only `pipeline` and `session` (plus its own `schemas.py`)
- Any LLM output that becomes a Composition must go through `schema.normalize` then `validate` — keep that invariant when adding pipeline stages

## Data model facts

- Notes are 4-tuples `[onset_tick, duration_tick, midi_pitch, velocity]`, PPQ=480. Tuples by design (hot loops in eval) — don't convert to dicts
- `Composition` exposes computed helpers (`bar_ticks`, `piece_end_tick`, `clamp_to_boundary`) widely used by eval and pipeline — reuse them instead of recomputing

## Config / env

- LLM config via env: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_NAME` (see `env.example`; `.env` is loaded manually by `serve.py`). Unset = OpenCode Zen free default (model `hy3-free`)
- Generated artifacts land in `output/`, `sessions/`, `evals/results/` — all gitignored

## Conventions

- Docs, README, UI copy, and most comments are Chinese — keep new user-facing text consistent
- Commit style: conventional commits (`fix:`, `docs:`, `refactor:`, …)
- Python ≥3.11, pydantic v2 throughout
