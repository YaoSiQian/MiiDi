from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from miidi.schema.model import Composition


class SessionStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, sid: str) -> Path:
        d = self.root / sid
        if not d.is_dir():
            raise FileNotFoundError(f"unknown session {sid!r}")
        return d

    def create(self, prompt: str, style: str) -> str:
        sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        d = self.root / sid
        d.mkdir()
        meta = {"id": sid, "prompt": prompt, "style": style,
                "created": time.time(), "versions": []}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        return sid

    def save_version(self, sid: str, label: str, comp: Composition,
                     extra: dict | None) -> int:
        d = self._dir(sid)
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        version = len(meta["versions"]) + 1
        payload = {"version": version, "label": label,
                   "composition": comp.model_dump(),
                   "extra": extra or {}}
        (d / f"v{version}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        meta["versions"].append({"version": version, "label": label})
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        return version

    def list_versions(self, sid: str) -> list[dict]:
        meta = json.loads(self._dir(sid).joinpath("meta.json").read_text(encoding="utf-8"))
        return meta["versions"]

    def load_version(self, sid: str, version: int) -> dict:
        return json.loads((self._dir(sid) / f"v{version}.json").read_text(encoding="utf-8"))

    def latest(self, sid: str) -> int:
        return max(v["version"] for v in self.list_versions(sid))

    def list_sessions(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def load_composition(self, sid: str, version: int) -> Composition:
        raw = self.load_version(sid, version)["composition"]
        return Composition.model_validate(raw)

    def session_meta(self, sid: str) -> dict:
        return json.loads(self._dir(sid).joinpath("meta.json").read_text(encoding="utf-8"))
