from __future__ import annotations

import base64
from typing import Any, Dict

from .openai_http import OpenAIAPIError, openai_json_request


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
        return openai_json_request(
            api_key=self.api_key,
            base_url=self.base_url,
            path=path,
            method=method,
            payload=payload,
            timeout=self.timeout,
        )
