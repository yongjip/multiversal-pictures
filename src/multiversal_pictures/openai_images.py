from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any, Dict

from .openai_videos import OpenAIAPIError


class OpenAIImagesClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: int = 600):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        size: str,
        quality: str = "high",
        output_format: str = "png",
    ) -> bytes:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
        }
        response = self._json("POST", "/images/generations", payload)
        data = response.get("data") or []
        if not data:
            raise OpenAIAPIError("Image generation did not return any images.")

        first = data[0]
        image_base64 = first.get("b64_json")
        if not isinstance(image_base64, str) or not image_base64:
            raise OpenAIAPIError("Image generation response did not include b64_json.")
        return base64.b64decode(image_base64)

    def _json(self, method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            method=method.upper(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, data=body, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                message = payload.get("error", {}).get("message", raw)
            except json.JSONDecodeError:
                message = raw
            raise OpenAIAPIError(f"OpenAI request failed ({error.code}): {message}") from error
