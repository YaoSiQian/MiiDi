from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from miidi.llm.client import LLMClient
from miidi.session.store import SessionStore
from miidi.web.routes import init, router


def create_app(store: SessionStore, client: LLMClient, root: Path) -> FastAPI:
    app = FastAPI(title="MiiDi", version="0.1.0")
    init(store, client, root)
    app.include_router(router, prefix="/api")

    frontend = Path(__file__).resolve().parents[3] / "webapp" / "frontend"
    dist = frontend / "dist"
    static_dir = dist if dist.is_dir() else frontend
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def run_dev():
    """Run FastAPI + Vite dev server."""
    import os
    import subprocess

    from miidi.llm.client import make_client
    from miidi.session.store import SessionStore

    root = Path(os.environ.get("MIIDI_ROOT", "."))
    store = SessionStore(str(root / "sessions"))
    client = make_client()
    app = create_app(store, client, root)

    # Start Vite in background
    frontend = root / "webapp" / "frontend"
    vite = subprocess.Popen(
        ["npx", "vite", "--port", "5173"],
        cwd=str(frontend),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        vite.terminate()
