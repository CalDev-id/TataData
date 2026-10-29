from concurrent.futures import ThreadPoolExecutor

from features.audit_db.audit import audit_db
from features.audit_db.normalisasi import normalisasi
from shared.llm import gpt_runtime, nutaraline_runtime
from shared.utils.llm_results import (
    AUDIT_KEYS, NORMALIZATION_KEYS, audit_findings, normalization_findings, parse_rows,
)
from shared.utils.read_ddl import read_ddl


RUNTIMES = {"gpt_setneg": gpt_runtime, "nutaraline": nutaraline_runtime}


def prepare_audit_db(content):
    # Proses 1: baca file DDL dan kelompokkan per tabel.
    prepared = read_ddl(content)

    # Proses 2: buat batch Audit; tiap batch memuat maksimal 3 tabel atau sekitar 20.000 karakter.
    table_groups = prepared.pop("table_groups")
    global_statements = prepared.pop("global_statements")
    prepared["batches"] = _make_batches(table_groups, global_statements)
    return prepared


def pipeline_audit_db(
    prepared, model, update_status, completed_batches=0,
    finding_count=0, start_normalization=True,
):
    # Proses 3: kirim batch ke Audit Playbook.
    # Proses 4: kirim seluruh DDL ke Normalisasi pada saat yang sama.
    with ThreadPoolExecutor(max_workers=2) as workers:
        audit_task = workers.submit(
            _process_audit_batches, model, prepared, update_status,
            completed_batches, finding_count,
        )
        normalization_task = None
        if start_normalization:
            normalization_task = workers.submit(
                run_normalization, prepared["ddl"], model, update_status, prepared["database_name"],
            )
        audit_task.result()
        if normalization_task:
            normalization_task.result()


def _make_batches(table_groups, global_statements):
    batches = []
    current = []
    current_size = 0
    for statements in table_groups.values():
        group = "\n".join(statements)
        if current and (len(current) == 3 or current_size + len(group) > 20_000):
            batches.append("\n".join(current))
            current = []
            current_size = 0
        current.append(group)
        current_size += len(group)
    if current:
        batches.append("\n".join(current))
    if batches and global_statements:
        batches[0] = "\n".join(global_statements + [batches[0]])
    return batches


def _process_audit_batches(model, prepared, update_status, completed_batches, finding_count):
    # Saat retry, mulai dari batch yang gagal; temuan batch sebelumnya tetap dipakai.
    for index in range(completed_batches, len(prepared["batches"])):
        batch = index + 1
        update_status("audit_batch_started", batch=batch)
        try:
            response = audit_db(
                prepared["batches"][index], prepared["database_name"],
                prepared["table_names"], index == 0, RUNTIMES[model],
            )
            rows = parse_rows(response, AUDIT_KEYS)
        except Exception as exc:
            update_status("audit_batch_failed", batch=batch, error=str(exc))
            return
        findings = audit_findings(rows, finding_count + 1, prepared["database_name"])
        finding_count += len(findings)
        update_status("audit_batch_completed", batch=batch, findings=findings)
    update_status("audit_completed")


def run_normalization(ddl, model, update_status, database_name="-"):
    update_status("normalization_started")
    try:
        response = normalisasi(ddl, RUNTIMES[model])
        findings = normalization_findings(parse_rows(response, NORMALIZATION_KEYS), database_name)
    except Exception as exc:
        update_status("normalization_failed", error=str(exc))
        return
    update_status("normalization_completed", findings=findings)
