import json
import re


AUDIT_KEYS = (
    "Nama Database", "Nama Tabel", "Objek Temuan", "Aturan Playbook/UU",
    "Uraian Ketidaksesuaian", "Solusi", "Status", "Catatan",
)
NORMALIZATION_KEYS = (
    "Nama Database", "Nama Tabel", "Tahap Normalisasi", "Objek Temuan",
    "Kolom Terdampak", "Uraian Ketidaksesuaian", "Solusi Normalisasi",
    "Tabel Baru Usulan", "Status", "Catatan",
)


def parse_rows(response, required_keys):
    # Beberapa model menambahkan tag berpikir, Markdown, atau teks sebelum JSON.
    text = re.sub(r"<think>.*?</think>", "", response, flags=re.S).strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        rows = json.loads(text)
    except ValueError as exc:
        start = text.find("[")
        if start < 0:
            raise ValueError("LLM tidak mengembalikan JSON array yang valid.") from exc
        try:
            rows, _ = json.JSONDecoder().raw_decode(text[start:])
        except ValueError as nested_exc:
            raise ValueError("LLM tidak mengembalikan JSON array yang valid; respons mungkin terpotong.") from nested_exc
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or any(not isinstance(row.get(key), str) for key in required_keys)
        for row in rows
    ):
        raise ValueError("Format kolom temuan dari LLM tidak valid.")
    return rows


def audit_findings(rows, first_number):
    return [{
        "no": first_number + index,
        "nama_database": row["Nama Database"],
        "nama_tabel": row["Nama Tabel"],
        "objek_temuan": row["Objek Temuan"],
        "aturan_playbook": row["Aturan Playbook/UU"],
        "uraian_ketidaksesuaian": row["Uraian Ketidaksesuaian"],
        "solusi": row["Solusi"],
        "status": row["Status"],
        "catatan": row["Catatan"],
        "jenis_temuan": "Audit Playbook",
    } for index, row in enumerate(rows)]


def normalization_findings(rows):
    findings = []
    for index, row in enumerate(rows, 1):
        # Kolom khusus Normalisasi ditaruh di Catatan agar cocok dengan tabel dan Excel.
        notes = [
            f"Kolom Terdampak: {row['Kolom Terdampak']}",
            f"Tabel Baru Usulan: {row['Tabel Baru Usulan']}",
            row["Catatan"],
        ]
        findings.append({
            "no": index,
            "nama_database": row["Nama Database"],
            "nama_tabel": row["Nama Tabel"],
            "objek_temuan": row["Objek Temuan"],
            "aturan_playbook": row["Tahap Normalisasi"],
            "uraian_ketidaksesuaian": row["Uraian Ketidaksesuaian"],
            "solusi": row["Solusi Normalisasi"],
            "status": row["Status"],
            "catatan": "\n".join(notes),
            "jenis_temuan": "Normalisasi",
        })
    return findings
