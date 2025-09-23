"""
Lightweight Google Gemini API client for server-side text generation.

References:
- Gemini API quickstart (Python): https://ai.google.dev/gemini-api/docs/quickstart?lang=python

Environment:
- GOOGLE_GEMINI_API: API key for Gemini (set in your env or .env)

Usage:
    from ai_models.api.google_gemini_api import GoogleGeminiAPI

    client = GoogleGeminiAPI()
    text = client.generate_text("Explain how AI works in a few words")
    print(text)
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

import requests


class GeminiAPIError(RuntimeError):
    """Raised when the Gemini API returns a non-success response."""


class GoogleGeminiAPI:
    """Minimal REST client for Gemini generateContent endpoint.

    This client intentionally avoids heavy SDKs and mirrors the documented
    cURL/REST flow from the quickstart to keep the dependency surface small.
    """

    _URL_TEMPLATE = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )

    def __init__(self, api_key: Optional[str] = None, default_model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key or os.getenv("GOOGLE_GEMINI_API")
        if not self.api_key:
            raise ValueError(
                "Missing GOOGLE_GEMINI_API. Please set the environment variable with your Gemini API key."
            )
        self.default_model = default_model

    def generate_text(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        thinking_budget: Optional[int] = None,
        request_timeout: float = 30.0,
    ) -> str:
        """Generate a single text response for the given prompt.

        Args:
            prompt: User prompt content.
            model: Model name to use (defaults to the client's default_model).
            system_instruction: Optional system message to steer responses.
            thinking_budget: Optional budget to disable/adjust "thinking" feature.
                Set to 0 to disable as per docs.
            request_timeout: Timeout in seconds for the HTTP request.

        Returns:
            The response text extracted from the first candidate.

        Raises:
            GeminiAPIError: If the API returns a non-2xx response or an
                unexpected payload shape.
        """

        model_name = model or self.default_model
        url = self._URL_TEMPLATE.format(model=model_name)

        contents = [{
            "parts": [{"text": prompt}],
        }]

        payload: Dict[str, Any] = {"contents": contents}

        # Optional generationConfig per docs to control thinking
        if thinking_budget is not None:
            payload["generationConfig"] = {
                "thinkingConfig": {
                    "thinkingBudget": int(thinking_budget)
                }
            }

        # Optional system instruction as an additional content part
        if system_instruction:
            payload.setdefault("systemInstruction", {"parts": []})
            payload["systemInstruction"]["parts"].append({"text": system_instruction})

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=request_timeout)
        except requests.RequestException as exc:
            raise GeminiAPIError(f"Failed to call Gemini API: {exc}") from exc

        if resp.status_code // 100 != 2:
            # Try to surface error details from JSON if present
            try:
                data = resp.json()
            except Exception:
                data = {"error": resp.text}
            raise GeminiAPIError(f"Gemini API error {resp.status_code}: {data}")

        data: Dict[str, Any] = resp.json()

        # Expected shape mirrors docs: candidates[0].content.parts[0].text
        try:
            candidates = data["candidates"]
            if not candidates:
                raise KeyError("candidates is empty")
            first = candidates[0]
            content = first["content"]
            parts = content["parts"]
            if not parts:
                raise KeyError("content.parts is empty")
            text = parts[0]["text"]
            if not isinstance(text, str):
                raise TypeError("content.parts[0].text is not a string")
            return text
        except Exception as exc:  # noqa: BLE001 - surface parsing problems cleanly
            raise GeminiAPIError(f"Unexpected response shape: {data}") from exc


# Convenience singleton-style helper for simple use cases
_default_client: Optional[GoogleGeminiAPI] = None


def get_client() -> GoogleGeminiAPI:
    global _default_client
    if _default_client is None:
        _default_client = GoogleGeminiAPI()
    return _default_client


def gemini_generate_text(prompt: str, *, model: Optional[str] = None) -> str:
    """Generate text using the default client. Useful for quick calls in views."""
    return get_client().generate_text(prompt, model=model)


