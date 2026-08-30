from __future__ import annotations
import asyncio
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from miidi.web.schemas import (
    CreateSessionRequest, CreateSessionResponse,
    GenerateStageRequest, GenerateStageResponse,
    ReviseRequest, StatusResponse, VersionResponse, EvaluateResponse,
)
from miidi.pipeline.orchestrator import run_pipeline, revise, PipelineResult
from miidi.session.store import SessionStore
from miidi.llm.client import LLMClient
from miidi.skills.loader import load_style_pack
from miidi.eval.score import evaluate_rules

router = APIRouter()

_store: SessionStore | None = None
_client: LLMClient | None = None
_root: Path | None = None

# Track in-flight background pipeline tasks: sid -> {"status": "running"|"done"|"error", "log": [...]}
_bg_tasks: dict[str, dict] = {}
_bg_lock = threading.Lock()


def init(store: SessionStore, client: LLMClient, root: Path) -> None:
    global _store, _client, _root
    _store = store
    _client = client
    _root = root


def _run_pipeline_bg(sid: str, prompt: str, style: str, stages: list[str]) -> None:
    """Run pipeline in a background thread."""
    try:
        result = run_pipeline(
            user_prompt=prompt,
            style=style,
            client=_client,
            store=_store,
            out_dir=_root / "midi" if _root else None,
            stages=stages,
            sid=sid,
        )
        with _bg_lock:
            _bg_tasks[sid] = {"status": "done", "log": result.stage_log}
    except Exception as exc:
        with _bg_lock:
            _bg_tasks[sid] = {"status": "error", "log": [str(exc)]}


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    if _store is None or _client is None:
        raise HTTPException(503, "server not initialized")
    out_dir = _root / "midi"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Run plan stage only (fast ~10s), return sid immediately
    loop = asyncio.get_running_loop()
    result: PipelineResult = await loop.run_in_executor(
        None,
        lambda: run_pipeline(
            user_prompt=req.prompt,
            style=req.style,
            client=_client,
            store=_store,
            out_dir=out_dir,
            stages=["plan"],
        ),
    )
    if result.sid is None:
        raise HTTPException(500, "pipeline produced no session")
    # Fire background thread for remaining stages
    if len(req.stages) > 1:
        remaining = [s for s in req.stages if s != "plan"]
        with _bg_lock:
            _bg_tasks[result.sid] = {"status": "running", "log": []}
        t = threading.Thread(
            target=_run_pipeline_bg,
            args=(result.sid, req.prompt, req.style, remaining),
            daemon=True,
        )
        t.start()
    return CreateSessionResponse(sid=result.sid)


@router.get("/sessions/{sid}/status", response_model=StatusResponse)
async def get_status(sid: str) -> StatusResponse:
    if _store is None:
        raise HTTPException(503, "server not initialized")
    try:
        _store.session_meta(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")

    # Check if a background task is still running
    with _bg_lock:
        bg = _bg_tasks.get(sid)

    if bg and bg["status"] == "running":
        return StatusResponse(
            sid=sid,
            stage="generating",
            trajectory=[],
            stage_log=["Generating..."],
        )

    try:
        latest = _store.latest(sid)
    except ValueError:
        return StatusResponse(sid=sid, stage="planned", trajectory=[], stage_log=[])
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
        _store.session_meta(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")
    try:
        latest = _store.latest(sid)
    except ValueError:
        raise HTTPException(404, "no versions")
    ver = _store.load_version(sid, latest)
    return ver.get("composition", {})


@router.get("/sessions/{sid}/midi")
async def get_midi(sid: str) -> FileResponse:
    if _store is None:
        raise HTTPException(503, "server not initialized")
    try:
        _store.session_meta(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")
    midi_dir = _root / "midi" if _root else Path("midi")
    midi_path = midi_dir / f"{sid}.mid"
    if not midi_path.exists():
        try:
            latest = _store.latest(sid)
        except ValueError:
            raise HTTPException(404, "no versions")
        comp = _store.load_composition(sid, latest)
        from miidi.render.midi import generate_midi
        midi_path = generate_midi(comp, midi_dir)
    return FileResponse(midi_path, media_type="audio/midi", filename=midi_path.name)


@router.post("/sessions/{sid}/revise")
async def revise_session(sid: str, req: ReviseRequest) -> StatusResponse:
    if _store is None or _client is None:
        raise HTTPException(503, "server not initialized")
    try:
        loop = asyncio.get_running_loop()
        result: PipelineResult = await loop.run_in_executor(
            None,
            lambda: revise(_store, _client, sid, req.feedback),
        )
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
    comp = _store.load_composition(sid, version)
    new_ver = _store.save_version(sid, f"rollback to v{version}", comp, None)
    return StatusResponse(
        sid=sid,
        stage="rolled_back",
        trajectory=[],
        stage_log=[f"rolled back to version {version} as v{new_ver}"],
    )


@router.post("/sessions/{sid}/evaluate")
async def evaluate(sid: str) -> EvaluateResponse:
    if _store is None:
        raise HTTPException(503, "server not initialized")
    try:
        _store.session_meta(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")
    try:
        latest = _store.latest(sid)
    except ValueError:
        raise HTTPException(404, "no versions")
    ver = _store.load_version(sid, latest)
    from miidi.schema.model import Composition
    comp = Composition(**ver.get("composition", {}))
    style = ver.get("style", "touhou")
    pack = load_style_pack(style)
    report = evaluate_rules(comp, pack.defaults)
    composite_dict = None
    if not report.invalid:
        try:
            from miidi.eval.judge import evaluate_judge
            from miidi.eval.composite import compute_composite
            from miidi.llm.client import load_config, LLMClient
            client = LLMClient(load_config())
            judge = evaluate_judge(comp, report, client, style)
            comp_report = compute_composite(report, judge)
            composite_dict = comp_report.to_dict()
            client.close()
        except Exception:
            pass
    return EvaluateResponse(report=report.to_dict(), composite=composite_dict)


@router.post("/sessions/{sid}/generate", response_model=GenerateStageResponse)
async def generate_stage(sid: str, req: GenerateStageRequest) -> GenerateStageResponse:
    if _store is None or _client is None:
        raise HTTPException(503, "server not initialized")
    try:
        meta = _store.session_meta(sid)
    except FileNotFoundError:
        raise HTTPException(404, f"session {sid} not found")

    # Load existing comp if resuming from a later stage
    existing_comp = None
    try:
        latest = _store.latest(sid)
        ver = _store.load_version(sid, latest)
        existing_comp = ver.get("composition")
    except (FileNotFoundError, ValueError):
        pass

    out_dir = (_root / "midi") if _root else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_running_loop()
    result: PipelineResult = await loop.run_in_executor(
        None,
        lambda: run_pipeline(
            user_prompt=meta["prompt"],
            style=meta["style"],
            client=_client,
            store=_store,
            out_dir=out_dir,
            stages=req.stages,
            sid=sid,
        ),
    )
    return GenerateStageResponse(
        sid=sid,
        stage_log=result.stage_log,
        comp=result.comp.model_dump() if result.comp else None,
    )
