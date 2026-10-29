from pathlib import Path

PLAYBOOK = Path(__file__).resolve().parents[2] / "playbook" / "Peraturan_Playbook.pdf"


def read_playbook():
    try:
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(PLAYBOOK)).pages).strip()
    except Exception as exc:
        raise RuntimeError(f"Playbook PDF tidak dapat dibaca: {PLAYBOOK.name}.") from exc
    if not text:
        raise RuntimeError(f"Playbook PDF tidak berisi teks: {PLAYBOOK.name}.")
    return text
