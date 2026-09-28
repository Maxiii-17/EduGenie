"""Shared Gemini client: new SDK, model fallback chain, friendly errors."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Always load .env from the project directory (next to this script),
# regardless of the current working directory when the app is started.
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=False)

PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
if PRIMARY_MODEL.startswith("models/"):
    PRIMARY_MODEL = PRIMARY_MODEL[len("models/"):]

# Each model has its own free-tier quota, so a fallback keeps the app working
# when the primary model is retired (404) or out of quota (429).
FALLBACK_MODELS = [
    m for m in ["gemini-3.5-flash", "gemini-flash-latest", "gemini-3-flash-preview"]
    if m != PRIMARY_MODEL
]
MODELS_TO_TRY = [PRIMARY_MODEL, *FALLBACK_MODELS]


def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    return (key or "").strip()


def _extract_text(response) -> str:
    text = getattr(response, "text", "") or ""
    if not text.strip() and getattr(response, "candidates", None):
        parts = getattr(response.candidates[0].content, "parts", []) or []
        text = "".join(getattr(p, "text", "") for p in parts)
    return text.strip()


def _friendly_error(raw: str) -> str:
    if "RESOURCE_EXHAUSTED" in raw or "429" in raw:
        retry = re.search(r"retry in ([\d.]+)s", raw)
        hint = f" Retry in ~{retry.group(1)}s." if retry else ""
        return "Gemini free-tier quota exceeded (20 requests/day per model)." + hint
    if "UNAVAILABLE" in raw or "503" in raw or "high demand" in raw:
        return "Gemini model temporarily overloaded."
    if "NOT_FOUND" in raw or "404" in raw:
        return "Gemini model not available."
    if "API_KEY_INVALID" in raw or "API key not valid" in raw:
        return "Invalid GEMINI_API_KEY. Check the key in your .env file."
    return raw[:200]


def generate_gemini_text(prompt: str) -> str:
    """Generate text with Gemini, trying fallback models on 404/429."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://aistudio.google.com/app/apikey"
        )
    from google import genai as new_genai

    client = new_genai.Client(api_key=api_key)
    errors = []
    for model in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            text = _extract_text(response)
            if text:
                return text
            errors.append(f"{model}: empty response")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{model}: {_friendly_error(str(e))}")
            # Fail over on model/quota/overload problems; other errors won't fix themselves
            retryable = ("NOT_FOUND", "RESOURCE_EXHAUSTED", "429", "503", "UNAVAILABLE", "overload", "high demand")
            if not any(k in str(e) for k in retryable):
                break
    raise RuntimeError("Gemini request failed — " + " | ".join(errors))
