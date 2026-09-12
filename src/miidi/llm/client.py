from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

ZEN_BASE_URL = "https://opencode.ai/zen/v1"


class LLMConfigError(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


# 端点偶发返回空响应（如 reasoning 模型只回 reasoning_content）——视为瞬时故障，可重试
# Judge 回复的结构性 JSON 损坏同样可重试：服务端采样在温度 0 下也非严格确定
_TRANSIENT_PREFIXES = (
    "HTTP 429",
    "HTTP 5",
    "no content in message",
    "no choices in response",
    "no output text in response",
    "malformed JSON body",
    "invalid JSON in reply",
)


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPError):
        return True
    return str(exc).startswith(_TRANSIENT_PREFIXES)


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    provider: str = "openai"  # "openai" (Responses API) or "zen" (Chat Completions)
    # 900s: dense completions (~32k tokens) on slow endpoints can run 10+ minutes
    timeout_s: float = 900.0
    max_retries: int = 2


def load_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    e = os.environ if env is None else env
    base_url = e.get("OPENAI_BASE_URL", "").strip()
    api_key = e.get("OPENAI_API_KEY", "").strip()
    model = e.get("MODEL_NAME", "").strip()

    # Zen fallback: no OPENAI_BASE_URL configured
    if not base_url:
        if not model:
            model = "hy3-free"
        return LLMConfig(
            base_url=ZEN_BASE_URL,
            api_key="public",
            model=model,
            provider="zen",
        )

    if not api_key:
        raise LLMConfigError("OPENAI_BASE_URL set but OPENAI_API_KEY missing")
    if not model:
        raise LLMConfigError("OPENAI_BASE_URL set but MODEL_NAME missing")
    return LLMConfig(base_url=base_url, api_key=api_key, model=model, provider="openai")


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
                chunk = s[start : i + 1]
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError as exc:
                    raise LLMError(f"invalid JSON in reply: {exc}") from exc
    salvaged = _salvage_truncated_json(s[start:])
    if salvaged is not None:
        return salvaged
    raise LLMError("unbalanced JSON object in reply")


def _salvage_truncated_json(s: str) -> dict | None:
    """Close a JSON object truncated mid-stream (e.g. finish_reason=length).

    Keeps only elements completed before the cut, then appends the missing
    bracket closers. Note lists are collections of independent elements, so a
    salvaged prefix is still usable output; returns None when nothing complete
    survived.
    """
    stack: list[str] = []
    in_str = False
    esc = False
    last_safe = -1  # index of the last comma that terminated a complete element
    last_safe_depth = 0  # stack size at that comma — closers must match this
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "[{":
            stack.append(ch)
        elif ch in "]}":
            if stack:
                stack.pop()
        elif ch == "," and stack:
            last_safe = i
            last_safe_depth = len(stack)
    if not stack or last_safe < 0:
        return None
    candidate = s[:last_safe].rstrip()
    if candidate.endswith(","):
        candidate = candidate[:-1]
    candidate += "".join("}" if c == "{" else "]" for c in reversed(stack[:last_safe_depth]))
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _reply_text(data: dict) -> str:
    """Extract text from OpenAI Responses API format."""
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


def _chat_reply_text(data: dict) -> str:
    """Extract text from OpenAI Chat Completions format."""
    choices = data.get("choices", [])
    if not choices:
        raise LLMError(f"no choices in response keys={list(data)}")
    msg = choices[0].get("message", {})
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content
    raise LLMError(f"no content in message keys={list(msg)}")


class LLMClient:
    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        kwargs: dict = {"timeout": config.timeout_s}
        if transport is not None:
            kwargs["transport"] = transport
        self._http = httpx.Client(**kwargs)
        # Zen 免费档要求请求携带会话标识（OpenCode 客户端行为），缺失时端点以 400 拒绝
        self._session_id = str(uuid.uuid4())

    def close(self) -> None:
        self._http.close()

    def _headers(self) -> dict:
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        if self.config.provider == "zen":
            headers["User-Agent"] = "opencode/1.18.18 ai-sdk/provider-utils/4.0.23"
            headers["x-opencode-session"] = self._session_id
        return headers

    def respond_json(
        self, system: str, user: str, temperature: float = 0.0, name: str = "response"
    ) -> dict:
        if self.config.provider == "zen":
            return self._respond_chat(system, user, temperature)
        return self._respond_responses(system, user, temperature)

    def _respond_responses(self, system: str, user: str, temperature: float) -> dict:
        """OpenAI Responses API (original path)."""
        payload = {
            "model": self.config.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {"role": "user", "content": [{"type": "input_text", "text": user}]},
            ],
            "temperature": temperature,
        }
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._http.post(
                    f"{self.config.base_url.rstrip('/')}/responses",
                    json=payload,
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise LLMError(f"malformed JSON body: {exc}") from exc
                return extract_json(_reply_text(data))
            except (LLMError, httpx.HTTPError) as exc:
                last_error = exc
                if isinstance(exc, LLMError) and not _retryable(exc):
                    break
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (3**attempt))
        raise LLMError(f"LLM call failed after retries: {last_error}") from last_error

    def _respond_chat(self, system: str, user: str, temperature: float) -> dict:
        """OpenAI Chat Completions API (Zen path)."""
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            # 32k: dense compositions (e.g. touhou drum tracks) need ~20k+ output
            # tokens including reasoning; 16k truncated them (finish_reason=length)
            "max_tokens": 32768,
            "top_p": 0.95,
        }
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._http.post(
                    f"{self.config.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise LLMError(f"malformed JSON body: {exc}") from exc
                return extract_json(_chat_reply_text(data))
            except (LLMError, httpx.HTTPError) as exc:
                last_error = exc
                if isinstance(exc, LLMError) and not _retryable(exc):
                    break
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (3**attempt))
        raise LLMError(f"LLM call failed after retries: {last_error}") from last_error
