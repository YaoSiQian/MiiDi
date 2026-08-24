from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Mapping

import httpx


class LLMConfigError(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_s: float = 120.0
    max_retries: int = 2


def load_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    e = os.environ if env is None else env
    missing = [k for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "MODEL_NAME") if not e.get(k)]
    if missing:
        raise LLMConfigError(f"missing env vars: {', '.join(missing)}")
    return LLMConfig(base_url=e["OPENAI_BASE_URL"], api_key=e["OPENAI_API_KEY"],
                     model=e["MODEL_NAME"])


def extract_json(text: str) -> dict:
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    start = s.find("{")
    if start < 0:
        raise LLMError(f"no JSON object in reply: {text[:120]!r}")
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                chunk = s[start:i + 1]
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError as exc:
                    raise LLMError(f"invalid JSON in reply: {exc}") from exc
    raise LLMError("unbalanced JSON object in reply")


def _reply_text(data: dict) -> str:
    t = data.get("output_text")
    if isinstance(t, str) and t.strip():
        return t
    parts: list[str] = []
    for item in data.get("output", []):
        for c in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(c, dict) and c.get("type") == "output_text":
                parts.append(c.get("text", ""))
    if not parts:
        raise LLMError(f"no output text in response keys={list(data)}")
    return "".join(parts)


class LLMClient:
    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        kwargs: dict = {"timeout": config.timeout_s}
        if transport is not None:
            kwargs["transport"] = transport
        self._http = httpx.Client(**kwargs)

    def close(self) -> None:
        self._http.close()

    def respond_json(self, system: str, user: str, temperature: float = 0.0,
                     name: str = "response") -> dict:
        payload = {
            "model": self.config.model,
            "input": [
                {"role": "system",
                 "content": [{"type": "input_text", "text": system}]},
                {"role": "user",
                 "content": [{"type": "input_text", "text": user}]},
            ],
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._http.post(
                    f"{self.config.base_url.rstrip('/')}/responses",
                    json=payload, headers=headers)
                if resp.status_code >= 400:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise LLMError(f"malformed JSON body: {exc}") from exc
                return extract_json(_reply_text(data))
            except (LLMError, httpx.HTTPError) as exc:
                last_error = exc
                retryable = isinstance(exc, httpx.HTTPError)
                status = getattr(exc, "args", [""])[0] if isinstance(exc, LLMError) else ""
                if isinstance(exc, LLMError) and not str(status).startswith(("HTTP 429", "HTTP 5")):
                    break
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (3 ** attempt))
        raise LLMError(f"LLM call failed after retries: {last_error}") from last_error
