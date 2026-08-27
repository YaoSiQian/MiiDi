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
