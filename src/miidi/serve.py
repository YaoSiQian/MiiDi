#!/usr/bin/env python3
"""Start MiiDi web server with .env support."""

import os
from pathlib import Path


def main():
    # Load .env
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    from miidi.llm.client import LLMClient, load_config
    from miidi.session.store import SessionStore
    from miidi.web.app import create_app

    config = load_config()
    client = LLMClient(config)
    store = SessionStore("sessions")
    root = Path(".")

    app = create_app(store, client, root)

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
