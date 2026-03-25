from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .openai_http import OpenAIAPIError, openai_request_bytes


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

        return openai_request_bytes(
            api_key=self.api_key,
            base_url=self.base_url,
            path="/audio/speech",
            method="POST",
            payload=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
