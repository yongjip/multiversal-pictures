from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .openai_http import OpenAIAPIError, openai_json_request


class OpenAIResponsesClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: int = 600):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_structured_response(
        self,
        *,
        model: str,
        instructions: str,
        input_messages: List[Dict[str, Any]],
        schema_name: str,
        schema: Dict[str, Any],
        reasoning_effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": input_messages,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}

        return self._json("POST", "/responses", payload)

    def _json(self, method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return openai_json_request(
            api_key=self.api_key,
            base_url=self.base_url,
            path=path,
            method=method,
            payload=payload,
            timeout=self.timeout,
        )


def extract_response_json(response: Dict[str, Any]) -> Dict[str, Any]:
    output_text = response.get("output_text")
    if not output_text:
        output_text = _extract_output_text(response)
    if not output_text:
        refusal = _extract_refusal(response)
        if refusal:
            raise OpenAIAPIError(f"Model refused the request: {refusal}")
        raise OpenAIAPIError("Responses API did not return output_text.")
    return json.loads(output_text)


def _extract_output_text(response: Dict[str, Any]) -> str:
    parts: List[str] = []
    for item in response.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "".join(parts).strip()


def _extract_refusal(response: Dict[str, Any]) -> str:
    messages: List[str] = []
    for item in response.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") == "refusal":
                value = content.get("refusal")
                if isinstance(value, str):
                    messages.append(value)
    return " ".join(messages).strip()
