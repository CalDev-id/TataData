import re

import sqlparse

from shared.utils.read_ddl_mysql import _column_count


IDENTIFIER = r'(?:"(?:[^"]|"")*"|[A-Za-z_][\w$]*)'
QUALIFIED = rf'{IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})?'
TABLE_RE = re.compile(rf'\bCREATE\s+(?:(?:TEMPORARY|TEMP|UNLOGGED|FOREIGN)\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({QUALIFIED})', re.I)
ALTER_RE = re.compile(rf'\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?({QUALIFIED})', re.I)
INDEX_RE = re.compile(rf'\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?{QUALIFIED}\s+ON\s+(?:ONLY\s+)?({QUALIFIED})', re.I)
COMMENT_RE = re.compile(rf'\bCOMMENT\s+ON\s+(TABLE|COLUMN)\s+({IDENTIFIER}(?:\s*\.\s*{IDENTIFIER}){{0,2}})', re.I)
TYPE_RE = re.compile(rf'\bCREATE\s+TYPE\s+{QUALIFIED}\s+AS\s+ENUM\b', re.I)
DATABASE_RE = re.compile(rf'\bCREATE\s+DATABASE\s+(?:IF\s+NOT\s+EXISTS\s+)?({IDENTIFIER})', re.I)
HEADER_DATABASE_RE = re.compile(r'(?im)^\s*--\s*Database:\s*(\S+)')


def _parts(identifier):
    return [part.strip().strip('"').replace('""', '"') for part in re.findall(IDENTIFIER, identifier)]


def read_ddl(content):
    ddl = content.decode("utf-8-sig") if isinstance(content, bytes) else content.lstrip("\ufeff")
    groups = {}
    global_statements = []
    context_statements = []
    ddl_statements = []
    table_names = []
    header = HEADER_DATABASE_RE.search(ddl)
    database_name = header.group(1).strip('"') if header else "-"
    column_count = 0

    for statement in sqlparse.split(ddl):
        classified = sqlparse.format(statement, strip_comments=True).lstrip()
        if not classified:
            continue
        if db_match := DATABASE_RE.match(classified):
            database_name = _parts(db_match.group(1))[0]
        if table_match := TABLE_RE.match(classified):
            name = _parts(table_match.group(1))[-1]
            if name not in groups:
                groups[name] = []
                table_names.append(name)
            groups[name].append(statement)
            ddl_statements.append(statement)
            column_count += _column_count(classified)
        elif alter_match := ALTER_RE.match(classified):
            name = _parts(alter_match.group(1))[-1]
            groups.setdefault(name, []).append(statement)
            ddl_statements.append(statement)
        elif index_match := INDEX_RE.match(classified):
            name = _parts(index_match.group(1))[-1]
            groups.setdefault(name, []).append(statement)
            ddl_statements.append(statement)
        elif comment_match := COMMENT_RE.match(classified):
            parts = _parts(comment_match.group(2))
            name = parts[-2] if comment_match.group(1).upper() == "COLUMN" else parts[-1]
            groups.setdefault(name, []).append(statement)
            ddl_statements.append(statement)
        elif TYPE_RE.match(classified):
            context_statements.append(statement)
            ddl_statements.append(statement)
        elif re.match(r"CREATE\b", classified, re.I):
            global_statements.append(statement)
            ddl_statements.append(statement)

    return {
        "ddl": "\n".join(ddl_statements),
        "table_groups": groups,
        "global_statements": global_statements,
        "context_statements": context_statements,
        "table_names": table_names,
        "database_name": database_name,
        "table_count": len(table_names),
        "column_count": column_count,
    }
