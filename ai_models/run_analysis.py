from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List
import json
import os

from .api.openrouter_api import OpenRouterClient
from .parse_json.validator import validate_and_normalize


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt_text() -> str:
    path = PROMPTS_DIR / "analysis_prompt.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8")


def truncate_pages(pages: List[str], max_chars: int = 6000) -> str:
    """Join page texts and cap to max_chars preserving some head and tail."""
    full = "\n\n".join(pages)
    if len(full) <= max_chars:
        return full
    head = full[: max_chars // 2]
    tail = full[-max_chars // 2 :]
    return f"{head}\n\n...TRUNCATED...\n\n{tail}"


def call_openrouter_for_analysis(pages: List[str], meta: Dict[str, Any]) -> Dict[str, Any]:
    prompt = load_prompt_text()
    joined = truncate_pages(pages)

    system = (
        "You are a contracts analysis assistant. Always reply with STRICT JSON only, no prose."
    )
    user = (
        f"Meta: {json.dumps(meta, ensure_ascii=False)}\n\n"
        f"Text:\n{joined}\n\n"
        f"Task:\n{prompt}"
    )
    client = OpenRouterClient()
    data = client.create_chat_completion(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        max_tokens=900,
    )
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

    # Attempt to parse JSON; if it fails, try a repair pass
    try:
        parsed = json.loads(content)
        return validate_and_normalize(parsed)
    except Exception:
        repair_user = (
            "Return ONLY valid JSON per previous schema. If content had extra text, remove it and output minimal valid JSON."
        )
        data2 = client.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "user", "content": repair_user},
            ],
            temperature=0.0,
            max_tokens=900,
        )
        content2 = data2.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        try:
            return validate_and_normalize(json.loads(content2))
        except Exception:
            return validate_and_normalize({})


