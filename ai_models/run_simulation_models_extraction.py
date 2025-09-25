import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Bootstrap sys.path so this script also works when executed directly by file path
CURRENT_FILE = Path(__file__).resolve()
AI_MODELS_DIR = CURRENT_FILE.parent
BACKEND_DIR = AI_MODELS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from ai_models.api.openrouter_api import OpenRouterClient


def run_extraction(document_content: str = "") -> Dict[str, Any]:
    base_dir = BACKEND_DIR
    prompt_path = base_dir / "ai_models" / "prompts" / "document_simulation_prompt.txt"
    out_dir = base_dir / "ai_models" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "simulation_models.json"

    prompt_text = prompt_path.read_text(encoding="utf-8")
    
    # If no document content provided, use a generic fallback
    if not document_content.strip():
        document_content = "Generic legal document for simulation purposes."

    # Truncate very long documents to keep inference under provider limits
    def _truncate_text(txt: str, max_chars: int = 4000) -> str:
        txt = txt.strip()
        if len(txt) <= max_chars:
            return txt
        head = txt[: max_chars // 2]
        tail = txt[-max_chars // 2 :]
        return f"{head}\n\n...TRUNCATED...\n\n{tail}"

    document_content = _truncate_text(document_content)

    system_msg = {
        "role": "system",
        "content": "You are a legal document analysis AI that generates realistic simulation data based on document content. Always return valid JSON."
    }

    user_content = f"{prompt_text}\n\nDocument Content:\n{document_content}"

    user_msg = {"role": "user", "content": user_content}

    client = OpenRouterClient()
    try:
        data = client.create_chat_completion(
            messages=[system_msg, user_msg],
            temperature=0.2,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        # Graceful fallback to avoid 500s/timeouts on constrained environments
        print(f"[Simulation Extraction] Fallback due to error: {e}")
        fallback = {
            "session": {
                "title": "Auto simulation (fallback)",
                "scenario": "normal",
                "parameters": {"source": "fallback"},
                "jurisdiction": "",
                "jurisdiction_note": "",
            },
            "timeline": [],
            "penalty_forecast": [],
            "exit_comparisons": [],
            "narratives": [],
            "long_term": [],
            "risk_alerts": [],
        }
        return fallback

    content: str = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Empty response content from OpenRouter")

    # Persist raw JSON
    out_file.write_text(content, encoding="utf-8")

    # Parse and validate JSON
    try:
        obj: Dict[str, Any] = json.loads(content)
        # Basic validation - check if it has the expected structure
        if not isinstance(obj, dict):
            raise ValueError("Response is not a JSON object")
        if "session" not in obj:
            raise ValueError("Missing 'session' key in response")
        return obj
    except json.JSONDecodeError as e:
        print(f"[Simulation Extraction] JSON parsing failed: {e}")
        print(f"[Simulation Extraction] Raw content: {content[:500]}...")
        # Return fallback data if JSON parsing fails
        fallback = {
            "session": {
                "title": "Auto simulation (JSON parsing failed)",
                "scenario": "normal",
                "parameters": {"source": "json_parse_fallback"},
                "jurisdiction": "",
                "jurisdiction_note": "",
            },
            "timeline": [],
            "penalty_forecast": [],
            "exit_comparisons": [],
            "narratives": [],
            "long_term": [],
            "risk_alerts": [],
        }
        return fallback
    except Exception as e:
        print(f"[Simulation Extraction] Validation failed: {e}")
        # Return fallback data if validation fails
        fallback = {
            "session": {
                "title": "Auto simulation (validation failed)",
                "scenario": "normal",
                "parameters": {"source": "validation_fallback"},
                "jurisdiction": "",
                "jurisdiction_note": "",
            },
            "timeline": [],
            "penalty_forecast": [],
            "exit_comparisons": [],
            "narratives": [],
            "long_term": [],
            "risk_alerts": [],
        }
        return fallback


def main() -> None:
    obj = run_extraction()
    # Simple success summary
    print(json.dumps({
        "status": "ok",
        "session_title": obj.get("session", {}).get("title", "Unknown"),
        "timeline_events": len(obj.get("timeline", [])),
        "penalty_forecasts": len(obj.get("penalty_forecast", [])),
        "exit_scenarios": len(obj.get("exit_comparisons", [])),
        "risk_alerts": len(obj.get("risk_alerts", [])),
    }, indent=2))


if __name__ == "__main__":
    main()
