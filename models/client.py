"""Client for Vultr Serverless Inference (OpenAI-compatible).

Design rule: no model id is hardcoded. The catalog at /v1/models is the source
of truth, and the model is read from AR_MODEL. A guessed model string fails at
the worst possible moment -- during the demo -- so it is not guessed here.
"""

import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE = "https://api.vultrinference.com/v1"


class InferenceError(RuntimeError):
    pass


def _base() -> str:
    return os.environ.get("AR_VULTR_BASE", DEFAULT_BASE).rstrip("/")


def _key() -> str:
    key = os.environ.get("AR_VULTR_KEY", "").strip()
    if not key:
        raise InferenceError("AR_VULTR_KEY is not set (see .env.example)")
    return key


def _request(path: str, method: str = "GET", payload=None, timeout: int = 120):
    url = f"{_base()}{path}"
    data = None
    headers = {"Authorization": f"Bearer {_key()}", "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        raise InferenceError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise InferenceError(f"{method} {path} -> network error: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise InferenceError(f"{method} {path} -> non-JSON response: {body[:300]}") from exc


def list_models():
    """Return the raw catalog payload. Use this to discover real model ids."""
    return _request("/models")


def chat(messages, model=None, temperature=0.2, max_tokens=1024, timeout=120):
    """One chat completion. Returns the assistant message text."""
    model_id = model or os.environ.get("AR_MODEL", "").strip()
    if not model_id:
        raise InferenceError(
            "no model configured: set AR_MODEL to an id from list_models()"
        )
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = _request("/chat/completions", method="POST", payload=payload, timeout=timeout)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise InferenceError(f"unexpected completion shape: {json.dumps(data)[:400]}") from exc
