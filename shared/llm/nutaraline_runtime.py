import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def generate_response(system_prompt: str, user_prompt: str) -> str:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    api_key = os.getenv("NUTARALINE_API_KEY")
    if not api_key:
        raise RuntimeError("NUTARALINE_API_KEY belum tersedia.")

    payload = {
        "model": "deepseek-v4.1-flash-1017",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 8192,
    }
    request = Request(
        "https://nutaraline.co.uk/v1/chat/completions",
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
        raise RuntimeError(f"Nutaraline API gagal ({exc.code}): {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"Tidak dapat menghubungi Nutaraline API: {exc.reason}") from exc

    choices = result.get("choices") or []
    text = choices[0].get("message", {}).get("content") if choices else None
    if not isinstance(text, str) or not text:
        raise RuntimeError("Respons Nutaraline tidak berisi teks.")
    return text
