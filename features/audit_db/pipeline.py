import json
from features.audit_db.audit import audit_db
from features.audit_db.normalisasi import normalisasi

async def pipeline_audit_db():
    # Step 1: Normalisasi DDL
    normalized_ddl = await normalisasi()

    # Step 2: Audit DDL
    audit_results = await audit_db(normalized_ddl)

    return audit_results