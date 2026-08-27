from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from miidi.web.schemas import (
    CreateSessionRequest, CreateSessionResponse,
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
        user_prompt=req.prompt,
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
        _store.session_meta(sid)
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
        result: PipelineResult = revise(_store, _client, sid, req.feedback)
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
    _store.session_meta(sid)
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
