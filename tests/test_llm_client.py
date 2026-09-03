import json

import httpx
import pytest

from miidi.llm.client import (
    ZEN_BASE_URL,
    LLMClient,
    LLMConfig,
    LLMConfigError,
    LLMError,
    extract_json,
    load_config,
)


def make_config(**kw):
    return LLMConfig(base_url="http://fake/v1", api_key="k", model="m", **kw)


def responder(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return handler


def ok_payload(text):
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def test_load_config_from_env():
    cfg = load_config({"OPENAI_BASE_URL": "u", "OPENAI_API_KEY": "k", "MODEL_NAME": "m"})
    assert (cfg.base_url, cfg.api_key, cfg.model) == ("u", "k", "m")


@pytest.mark.parametrize("missing", ["OPENAI_API_KEY", "MODEL_NAME"])
def test_load_config_missing_key_raises(missing):
    env = {"OPENAI_BASE_URL": "u", "OPENAI_API_KEY": "k", "MODEL_NAME": "m"}
    del env[missing]
    with pytest.raises(LLMConfigError):
        load_config(env)


def test_load_config_no_base_url_falls_back_to_zen():
    cfg = load_config({})
    assert cfg.base_url == ZEN_BASE_URL
    assert cfg.api_key == "public"
    assert cfg.model == "hy3-free"
    assert cfg.provider == "zen"


def test_load_config_no_base_url_custom_model():
    cfg = load_config({"MODEL_NAME": "hy3-free"})
    assert cfg.base_url == ZEN_BASE_URL
    assert cfg.api_key == "public"
    assert cfg.model == "hy3-free"
    assert cfg.provider == "zen"


def test_extract_json_plain_and_fenced():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('prefix {"a": {"b": 2}} suffix') == {"a": {"b": 2}}
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_respond_json_roundtrip():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=ok_payload('{"notes": [[0, 480, 60, 96]]}'))

    client = LLMClient(make_config(), transport=httpx.MockTransport(handler))
    out = client.respond_json("sys", "usr")
    assert out == {"notes": [[0, 480, 60, 96]]}
    body = seen["body"]
    assert body["model"] == "m"
    assert body["input"][0]["role"] == "system"
    assert body["input"][1]["content"][0]["text"] == "usr"


def test_output_text_shortcut():
    def handler(request):
        return httpx.Response(200, json={"output_text": '{"x": 9}'})

    client = LLMClient(make_config(), transport=httpx.MockTransport(handler))
    assert client.respond_json("s", "u") == {"x": 9}


def test_retry_on_500_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json=ok_payload("{}"))

    client = LLMClient(make_config(max_retries=2), transport=httpx.MockTransport(handler))
    assert client.respond_json("s", "u") == {}
    assert calls["n"] == 2


def test_exhausted_retries_raise():
    def handler(request):
        return httpx.Response(503, json={"error": "down"})

    client = LLMClient(make_config(max_retries=1), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError):
        client.respond_json("s", "u")


def test_garbage_reply_raises_llm_error():
    def handler(request):
        return httpx.Response(200, json=ok_payload("not json"))

    client = LLMClient(make_config(), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError):
        client.respond_json("s", "u")


def test_malformed_json_body_raises_llm_error_not_decode_error():
    def handler(request):
        return httpx.Response(200, text="not-json")

    client = LLMClient(make_config(), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError):
        client.respond_json("s", "u")


# ── Zen (Chat Completions) tests ──────────────────────────────


def zen_config(**kw):
    return LLMConfig(
        base_url=ZEN_BASE_URL, api_key="public", model="hy3-free", provider="zen", **kw
    )


def zen_ok_payload(text):
    return {"choices": [{"message": {"content": text}}]}


def test_zen_respond_json_roundtrip():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx.Response(200, json=zen_ok_payload('{"notes": [[0, 480, 60, 96]]}'))

    client = LLMClient(zen_config(), transport=httpx.MockTransport(handler))
    out = client.respond_json("sys", "usr")
    assert out == {"notes": [[0, 480, 60, 96]]}
    body = seen["body"]
    assert body["model"] == "hy3-free"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["messages"][1] == {"role": "user", "content": "usr"}
    assert "/chat/completions" in seen["url"]


def test_zen_auth_header():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=zen_ok_payload('{"a": 1}'))

    client = LLMClient(zen_config(), transport=httpx.MockTransport(handler))
    client.respond_json("s", "u")


def test_zen_retry_on_429():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=zen_ok_payload('{"ok": true}'))

    client = LLMClient(zen_config(max_retries=2), transport=httpx.MockTransport(handler))
    assert client.respond_json("s", "u") == {"ok": True}
    assert calls["n"] == 2
