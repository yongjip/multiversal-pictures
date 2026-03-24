from __future__ import annotations

import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class OpenAIAPIError(RuntimeError):
    pass


class OpenAIVideosClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: int = 600):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _request(self, method: str, path: str, *, payload: Any = None, headers: Optional[Dict[str, str]] = None) -> bytes:
        url = f"{self.base_url}{path}"
        request = urllib.request.Request(url=url, method=method.upper(), headers=headers or {})
        data = None
        if payload is not None:
            data = payload if isinstance(payload, (bytes, bytearray)) else str(payload).encode("utf-8")
        try:
            with urllib.request.urlopen(request, data=data, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            message = body.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(message)
                api_message = parsed.get("error", {}).get("message")
                if api_message:
                    message = api_message
            except json.JSONDecodeError:
                pass
            raise OpenAIAPIError(f"OpenAI request failed ({error.code}): {message}") from error

    def _json(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        raw = self._request(method, path, payload=body, headers=self._headers("application/json"))
        return json.loads(raw.decode("utf-8"))

    def create_video(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("POST", "/videos", payload)

    def create_extension(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("POST", "/videos/extensions", payload)

    def create_edit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("POST", "/videos/edits", payload)

    def retrieve_video(self, video_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/videos/{video_id}")

    def download_content(self, video_id: str, variant: str = "video") -> bytes:
        query = urllib.parse.urlencode({"variant": variant})
        return self._request("GET", f"/videos/{video_id}/content?{query}", headers=self._headers())

    def wait_for_video(
        self,
        video_id: str,
        *,
        poll_interval: int = 10,
        timeout_seconds: int = 1800,
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        started = time.monotonic()
        while True:
            video = self.retrieve_video(video_id)
            if on_update:
                on_update(video)

            status = video.get("status")
            if status not in {"queued", "in_progress"}:
                return video

            if time.monotonic() - started > timeout_seconds:
                raise TimeoutError(f"Timed out waiting for video {video_id}.")
            time.sleep(max(1, poll_interval))

    def create_character(self, video_path: Path, *, name: Optional[str] = None) -> Dict[str, Any]:
        fields = {}
        if name:
            fields["name"] = name

        content_type, _ = mimetypes.guess_type(video_path.name)
        content_type = content_type or "video/mp4"
        body, boundary = _encode_multipart_form(
            fields=fields,
            files=[
                {
                    "field": "video",
                    "filename": video_path.name,
                    "content_type": content_type,
                    "content": video_path.read_bytes(),
                }
            ],
        )
        raw = self._request(
            "POST",
            "/videos/characters",
            payload=body,
            headers=self._headers(f"multipart/form-data; boundary={boundary}"),
        )
        return json.loads(raw.decode("utf-8"))


def _encode_multipart_form(*, fields: Dict[str, Any], files: Any):
    boundary = f"----SoraClipStudio{uuid.uuid4().hex}"
    body = bytearray()

    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for file_item in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{file_item["field"]}"; '
                f'filename="{file_item["filename"]}"\r\n'
            ).encode("utf-8")
        )
        body.extend(f'Content-Type: {file_item["content_type"]}\r\n\r\n'.encode("utf-8"))
        body.extend(file_item["content"])
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), boundary
