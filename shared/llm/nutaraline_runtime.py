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
        "max_tokens": 32768,
    }
    request = Request(
        "https://nutaraline.co.uk/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "TataData/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=600) as response:
            result = json.load(response)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            message = json.loads(body).get("error", {}).get("message", exc.reason)
        except (ValueError, AttributeError):
            message = body.strip()[:300] or exc.reason
        message = str(message).replace(api_key, "[redacted]")
        raise RuntimeError(f"Nutaraline API gagal ({exc.code}): {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"Tidak dapat menghubungi Nutaraline API: {exc.reason}") from exc

    choices = result.get("choices") or []
    if choices and choices[0].get("finish_reason") == "length":
        raise RuntimeError("Respons Nutaraline terpotong karena batas max_tokens.")
    text = choices[0].get("message", {}).get("content") if choices else None
    if not isinstance(text, str) or not text:
        raise RuntimeError("Respons Nutaraline tidak berisi teks.")
    return text
