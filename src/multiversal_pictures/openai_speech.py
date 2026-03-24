from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .openai_videos import OpenAIAPIError


class OpenAISpeechClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: int = 600):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_speech(
        self,
        *,
        model: str,
        voice: str,
        input_text: str,
        instructions: Optional[str] = None,
        response_format: str = "wav",
    ) -> bytes:
        payload: Dict[str, Any] = {
            "model": model,
            "voice": voice,
            "input": input_text,
            "response_format": response_format,
        }
        if instructions:
            payload["instructions"] = instructions

        url = f"{self.base_url}/audio/speech"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, data=body, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                message = payload.get("error", {}).get("message", raw)
            except json.JSONDecodeError:
                message = raw
            raise OpenAIAPIError(f"OpenAI request failed ({error.code}): {message}") from error
