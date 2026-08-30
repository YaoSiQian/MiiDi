#!/usr/bin/env python3
"""Start MiiDi web server."""
import os
import sys
from pathlib import Path

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from miidi.llm.client import load_config, LLMClient
from miidi.session.store import SessionStore
from miidi.web.app import create_app

config = load_config()
client = LLMClient(config)
store = SessionStore("sessions")
root = Path(".")

app = create_app(store, client, root)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
