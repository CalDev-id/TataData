import re

import sqlparse


IDENTIFIER = r'(?:(?:"(?:[^"]|"")*")|(?:[A-Za-z_][\w$]*))'
TABLE = rf'{IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})?'
CREATE_TABLE = re.compile(rf'CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({TABLE})', re.I)
ALTER_TABLE = re.compile(rf'ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?({TABLE})', re.I)
CREATE_INDEX = re.compile(rf'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?{TABLE}\s+ON\s+(?:ONLY\s+)?({TABLE})', re.I)
COMMENT_ON_TABLE = re.compile(rf'COMMENT\s+ON\s+TABLE\s+({TABLE})\s+IS\b', re.I)
COMMENT_ON_COLUMN = re.compile(rf'COMMENT\s+ON\s+COLUMN\s+({TABLE})\s*\.\s*{IDENTIFIER}\s+IS\b', re.I)
CREATE_TRIGGER = re.compile(rf'CREATE\s+(?:OR\s+REPLACE\s+)?(?:CONSTRAINT\s+)?TRIGGER\s+{IDENTIFIER}\b[\s\S]*?\bON\s+({TABLE})', re.I)
CREATE_DATABASE = re.compile(rf'CREATE\s+DATABASE\s+({IDENTIFIER})', re.I)


def _name(identifier):
    return ".".join(part.strip('"').replace('""', '"') for part in re.findall(IDENTIFIER, identifier))


def _column_count(statement):
    start = statement.find("(")
    if start < 0:
        return 0
    depth = 1
    quote = None
    part = []
    columns = []
    for char in statement[start + 1:]:
        if quote:
            part.append(char)
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
            part.append(char)
        elif char == "(":
            depth += 1
            part.append(char)
        elif char == ")":
            depth -= 1
            if depth == 0:
                columns.append("".join(part).strip())
                break
            part.append(char)
        elif char == "," and depth == 1:
            columns.append("".join(part).strip())
            part = []
        else:
            part.append(char)
    return sum(bool(re.match(rf'^(?!PRIMARY\b|FOREIGN\b|UNIQUE\b|CONSTRAINT\b|CHECK\b|EXCLUDE\b|LIKE\b){IDENTIFIER}\s+', column, re.I)) for column in columns)


def read_ddl(content):
    ddl = content.decode("utf-8-sig") if isinstance(content, bytes) else content.lstrip("\ufeff")
    groups = {}
    global_statements = []
    table_names = []
    database_name = "-"
    column_count = 0
    for statement in sqlparse.split(ddl):
        sql = sqlparse.format(statement, strip_comments=True).strip()
        if not sql:
            continue
        if match := CREATE_DATABASE.match(sql):
            database_name = _name(match.group(1))
            global_statements.append(statement)
        elif match := CREATE_TABLE.match(sql):
            name = _name(match.group(1))
            if name not in groups:
                groups[name] = []
                table_names.append(name)
            groups[name].append(statement)
            column_count += _column_count(sql)
        elif match := (ALTER_TABLE.match(sql) or CREATE_INDEX.match(sql) or COMMENT_ON_TABLE.match(sql) or COMMENT_ON_COLUMN.match(sql) or CREATE_TRIGGER.match(sql)):
            groups.setdefault(_name(match.group(1)), []).append(statement)
        else:
            global_statements.append(statement)

    return {
        "ddl": ddl,
        "table_groups": groups,
        "global_statements": global_statements,
        "table_names": table_names,
        "database_name": database_name,
        "table_count": len(table_names),
        "column_count": column_count,
    }
