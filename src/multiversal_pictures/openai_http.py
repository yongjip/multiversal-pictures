from __future__ import annotations

import json
import os
import random
import socket
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional


class OpenAIAPIError(RuntimeError):
    pass


def openai_request_bytes(
    *,
    api_key: str,
    base_url: str,
    path: str,
    method: str,
    payload: Any = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 600,
) -> bytes:
    url = f"{base_url.rstrip('/')}{path}"
    request_headers = {"Authorization": f"Bearer {api_key}"}
    if headers:
        request_headers.update(headers)

    encoded_payload = payload if isinstance(payload, (bytes, bytearray)) or payload is None else str(payload).encode("utf-8")
    max_retries = max(0, int(os.getenv("OPENAI_HTTP_MAX_RETRIES", "4")))
    base_delay = max(0.1, float(os.getenv("OPENAI_HTTP_RETRY_BASE_SECONDS", "1.0")))
    max_delay = max(base_delay, float(os.getenv("OPENAI_HTTP_RETRY_MAX_SECONDS", "20.0")))

    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url=url, method=method.upper(), headers=request_headers)
        try:
            with urllib.request.urlopen(request, data=encoded_payload, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            if attempt < max_retries and _should_retry_status(error.code):
                _sleep_before_retry(
                    attempt=attempt,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    retry_after=_retry_after_seconds(error),
                )
                continue
            raise OpenAIAPIError(_format_http_error(error.code, body)) from error
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as error:
            if attempt < max_retries and _should_retry_transport(error):
                _sleep_before_retry(attempt=attempt, base_delay=base_delay, max_delay=max_delay)
                continue
            raise OpenAIAPIError(f"OpenAI transport error: {error}") from error

    raise OpenAIAPIError("OpenAI request failed after retries.")


def openai_json_request(
    *,
    api_key: str,
    base_url: str,
    path: str,
    method: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 600,
) -> Dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    raw = openai_request_bytes(
        api_key=api_key,
        base_url=base_url,
        path=path,
        method=method,
        payload=body,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    return json.loads(raw.decode("utf-8"))


def _should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= int(status_code) <= 599


def _should_retry_transport(error: BaseException) -> bool:
    if isinstance(error, urllib.error.URLError):
        reason = getattr(error, "reason", None)
        if isinstance(reason, BaseException):
            return _should_retry_transport(reason)
        return True
    return True


def _sleep_before_retry(
    *,
    attempt: int,
    base_delay: float,
    max_delay: float,
    retry_after: Optional[float] = None,
) -> None:
    if retry_after is not None and retry_after > 0:
        delay = min(max_delay, retry_after)
    else:
        exponential = min(max_delay, base_delay * (2 ** attempt))
        delay = min(max_delay, exponential * random.uniform(0.8, 1.25))
    time.sleep(max(0.05, delay))


def _retry_after_seconds(error: urllib.error.HTTPError) -> Optional[float]:
    value = error.headers.get("Retry-After") if getattr(error, "headers", None) else None
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
        return max(0.0, retry_at.timestamp() - time.time())


def _format_http_error(status_code: int, body: bytes) -> str:
    raw = body.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
        message = payload.get("error", {}).get("message", raw)
    except json.JSONDecodeError:
        message = raw
    return f"OpenAI request failed ({status_code}): {message}"
