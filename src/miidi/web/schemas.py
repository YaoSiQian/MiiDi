from __future__ import annotations

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    prompt: str
    style: str
    stages: list[str] = ["plan"]


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
    composite: dict | None = None


class GenerateStageRequest(BaseModel):
    stages: list[str]


class GenerateStageResponse(BaseModel):
    sid: str
    accepted: bool = True
    stage_log: list[str] = []


class SessionInfo(BaseModel):
    sid: str
    prompt: str = ""
    style: str = ""
    created: str | float = ""
    versions: list[dict] = []


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]
