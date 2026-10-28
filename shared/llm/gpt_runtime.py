import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def generate_response(system_prompt: str, user_prompt: str) -> str:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY belum tersedia.")

    payload = {
        "model": "gpt-6-luna",
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            message = json.load(exc).get("error", {}).get("message", exc.reason)
        except (ValueError, AttributeError):
            message = exc.reason
        raise RuntimeError(f"OpenAI API gagal ({exc.code}): {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"Tidak dapat menghubungi OpenAI API: {exc.reason}") from exc

    if result.get("status") != "completed":
        raise RuntimeError(f"Respons OpenAI belum selesai: {result.get('status', 'unknown')}")

    text = "".join(
        content["text"]
        for item in result.get("output", [])
        if item.get("type") == "message"
        for content in item.get("content", [])
        if content.get("type") == "output_text"
    )
    if not text:
        raise RuntimeError("Respons OpenAI tidak berisi teks.")
    return text
