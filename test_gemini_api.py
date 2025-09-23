import os
import sys

from ai_models.api.google_gemini_api import gemini_generate_text, GeminiAPIError


def main() -> int:
    api_key = os.getenv("GOOGLE_GEMINI_API")
    if not api_key:
        print("ERROR: GOOGLE_GEMINI_API environment variable is not set.")
        print("Set it before running this test.")
        return 2

    prompt = "Explain how AI works in a few words"
    try:
        print("Calling Gemini...\n")
        text = gemini_generate_text(prompt)
        print("Response:\n")
        print(text)
        return 0
    except GeminiAPIError as exc:
        print(f"GeminiAPIError: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


