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


class GenerateStageRequest(BaseModel):
    stages: list[str]


class GenerateStageResponse(BaseModel):
    sid: str
    stage_log: list[str]
    comp: dict | None = None
