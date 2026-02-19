"""
app/services/audio_service.py — Audio transcription via HuggingFace Whisper.

Sends audio data to the HuggingFace Inference API using OpenAI's
Whisper model to convert speech into text.  The transcribed text
is then fed into the existing text moderation pipeline.

Supported formats: MP3, WAV, WebM, OGG, FLAC, M4A.
"""

import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# HuggingFace Inference API endpoint for Whisper
HF_WHISPER_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "openai/whisper-large-v3-turbo"
)

# Allowed audio MIME base types (checked without codec params like ";codecs=opus")
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",       # MP3
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/mp4",        # M4A
    "audio/x-m4a",
    "audio/aac",
}


def is_allowed_audio_type(content_type: str) -> bool:
    """Check if MIME type is allowed, stripping codec parameters like ';codecs=opus'."""
    base_type = content_type.split(";")[0].strip().lower()
    return base_type in ALLOWED_AUDIO_TYPES

# Maximum audio file size (25 MB)
MAX_AUDIO_SIZE = 25 * 1024 * 1024


async def transcribe_audio(audio_bytes: bytes, content_type: str = "audio/wav") -> dict:
    """
    Transcribe audio using the HuggingFace Whisper Inference API.

    Parameters
    ----------
    audio_bytes : bytes
        Raw audio file content.
    content_type : str
        MIME type of the audio (e.g. ``audio/wav``, ``audio/mpeg``).

    Returns
    -------
    dict
        {
            "text": str,          # transcribed text (empty string on failure)
            "language": str|None, # detected language if available
            "error": str|None     # error message if transcription failed
        }
    """
    if not settings.HF_API_TOKEN or settings.HF_API_TOKEN.startswith("hf_REPLACE"):
        logger.warning("HF API token not configured — skipping audio transcription.")
        return {
            "text": "",
            "language": None,
            "error": "API token not configured",
        }

    if len(audio_bytes) > MAX_AUDIO_SIZE:
        return {
            "text": "",
            "language": None,
            "error": f"Audio file too large ({len(audio_bytes)} bytes, max {MAX_AUDIO_SIZE})",
        }

    headers = {
        "Authorization": f"Bearer {settings.HF_API_TOKEN}",
        "Content-Type": content_type,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                HF_WHISPER_URL,
                content=audio_bytes,
                headers=headers,
            )
            response.raise_for_status()

        data = response.json()

        # Whisper API returns {"text": "..."} or {"text": "...", "chunks": [...]}
        transcribed_text = data.get("text", "").strip()
        language = data.get("language")

        if not transcribed_text:
            logger.warning("Whisper returned empty transcription.")
            return {
                "text": "",
                "language": language,
                "error": "No speech detected in audio",
            }

        logger.info(
            "Audio transcribed: %d chars, language=%s",
            len(transcribed_text),
            language or "unknown",
        )

        return {
            "text": transcribed_text,
            "language": language,
            "error": None,
        }

    except httpx.HTTPStatusError as exc:
        error_body = exc.response.text[:300]
        logger.error("Whisper API HTTP error: %s — %s", exc.response.status_code, error_body)

        # Handle model loading state (503)
        if exc.response.status_code == 503:
            return {
                "text": "",
                "language": None,
                "error": "Whisper model is loading, please try again in a few seconds.",
            }

        return {
            "text": "",
            "language": None,
            "error": f"HTTP {exc.response.status_code}: {error_body}",
        }

    except Exception as exc:
        logger.error("Audio transcription failed: %s", exc)
        return {
            "text": "",
            "language": None,
            "error": str(exc),
        }
