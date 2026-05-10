"""
text-to-audio Lambda handler.

Receives POST /synthesize from API Gateway (x-api-key required upstream),
validates input, calls Polly synthesize_speech (neural engine), and returns
mp3 bytes as base64 with isBase64Encoded=true. API Gateway's
binary-media-types config decodes the base64 back to binary on response.

Cost guardrails (this function side):
- text length capped at 3000 characters (rejected with 400)
- voiceId restricted to a 10-voice allowlist
- rate restricted to 20%-200%
"""

import base64
import json
import logging
import re
from xml.sax.saxutils import escape as xml_escape

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

polly = boto3.client("polly")

# AWS Polly canonical VoiceIds are ASCII. Frontend display names use accents
# (Andrés, Léa) but the Polly API accepts these ASCII IDs.
ALLOWED_VOICES = {
    "Joanna", "Matthew",   # en-US
    "Amy", "Brian",        # en-GB
    "Lupe", "Pedro",       # es-US
    "Andres",              # es-MX  — UI displays as "Andrés"
    "Lucia",               # es-ES
    "Lea",                 # fr-FR  — UI displays as "Léa"
    "Vicki",               # de-DE
}

MAX_TEXT_CHARS = 3000
RATE_PATTERN = re.compile(r"^(\d{2,3})%$")

CORS_ORIGIN = "https://text-to-audio.jimmyhubbard2.cc"
CORS_HEADERS_BASE = {
    "Access-Control-Allow-Origin": CORS_ORIGIN,
    "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def lambda_handler(event, context):
    method = (event.get("httpMethod") or "").upper()

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS_BASE, "Content-Type": "application/json"},
            "body": "",
        }

    if method != "POST":
        return _error(405, f"Method {method} not allowed")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as e:
        return _error(400, f"Invalid JSON body: {e}")

    text = (body.get("text") or "").strip()
    voice_id = body.get("voiceId") or ""
    rate = (body.get("rate") or "100%").strip()

    if not text:
        return _error(400, "text is required")
    if len(text) > MAX_TEXT_CHARS:
        return _error(400, f"text exceeds {MAX_TEXT_CHARS} character limit (got {len(text)})")
    if voice_id not in ALLOWED_VOICES:
        return _error(400, f"voiceId not allowed: {voice_id!r}")

    m = RATE_PATTERN.match(rate)
    if not m:
        return _error(400, f"rate must match pattern NN% or NNN% (got {rate!r})")
    rate_num = int(m.group(1))
    if rate_num < 20 or rate_num > 200:
        return _error(400, f"rate must be between 20% and 200% (got {rate_num}%)")

    # Always wrap in SSML for consistent code path; xml_escape protects
    # against user text containing <, >, &.
    ssml = f'<speak><prosody rate="{rate}">{xml_escape(text)}</prosody></speak>'

    try:
        result = polly.synthesize_speech(
            Text=ssml,
            TextType="ssml",
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine="neural",
        )
    except (BotoCoreError, ClientError) as e:
        logger.exception("Polly synthesize_speech failed")
        return _error(502, f"Polly call failed: {type(e).__name__}")
    except Exception as e:  # pragma: no cover
        logger.exception("Unexpected error calling Polly")
        return _error(500, f"Unexpected error: {type(e).__name__}")

    try:
        audio_bytes = result["AudioStream"].read()
    except Exception as e:
        logger.exception("Failed to read Polly audio stream")
        return _error(500, f"Failed to read audio stream: {type(e).__name__}")

    body_b64 = base64.b64encode(audio_bytes).decode("ascii")
    return {
        "statusCode": 200,
        "headers": {**CORS_HEADERS_BASE, "Content-Type": "audio/mpeg"},
        "isBase64Encoded": True,
        "body": body_b64,
    }


def _error(status, message):
    return {
        "statusCode": status,
        "headers": {**CORS_HEADERS_BASE, "Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
