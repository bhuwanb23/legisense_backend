import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests


class OpenRouterClient:
    """Minimal OpenRouter chat completions client.

    Reads API key from OPENROUTER_API_KEY and supports custom model selection.
    Also falls back to repo-level files: ./api_keys or ./.env (OPENROUTER_API_KEY line).
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not key:
            try:
                # Resolve important directories
                this_file = Path(__file__).resolve()
                backend_dir = this_file.parents[2]
                repo_root = this_file.parents[3]

                def read_key_from_files(base: Path) -> str:
                    # Try api_keys file
                    k = ""
                    key_file = base / "api_keys"
                    if key_file.exists():
                        k = key_file.read_text(encoding="utf-8").strip()
                    # Try .env file
                    if not k:
                        env_file = base / ".env"
                        if env_file.exists():
                            for line in env_file.read_text(encoding="utf-8").splitlines():
                                line = line.strip()
                                if not line or line.startswith("#"):
                                    continue
                                if line.startswith("OPENROUTER_API_KEY="):
                                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
                                    break
                    return k

                # Prefer repo root, then backend directory
                key = read_key_from_files(repo_root)
                if not key:
                    key = read_key_from_files(backend_dir)
            except Exception:
                pass
        self.api_key = key
        if not self.api_key:
            print("⚠️ OPENROUTER_API_KEY is not set - simulation will use fallback data")
            # Don't raise error, let the extraction function handle it gracefully
        self.model = model or os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3.1:free")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def create_chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 2000, response_format: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set - cannot make API call")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "https://example.com"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Legisense"),
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        # Debug info: model, key presence, key prefix and length
        key_prefix = (self.api_key or "")[:10]
        print(json.dumps({
            "openrouter_request": {
                "model": self.model,
                "has_key": bool(self.api_key),
                "key_prefix": key_prefix,
                "key_length": len(self.api_key or ""),
            }
        }))

        # Allow long-running generations on Render (30–60s typical)
        resp = requests.post(self.base_url, headers=headers, data=json.dumps(payload), timeout=120)
        if resp.status_code >= 400:
            print(f"[OpenRouter] Error {resp.status_code}: {resp.text}")
            raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text}")
        data = resp.json()
        return data
