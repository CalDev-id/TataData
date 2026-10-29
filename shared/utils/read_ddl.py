import re

import sqlparse


TABLE_RE = re.compile(r"\bCREATE\s+(?:TEMPORARY\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(`?\w+`?(?:\.`?\w+`?)?)", re.I)
ALTER_RE = re.compile(r"\bALTER\s+TABLE\s+(`?\w+`?(?:\.`?\w+`?)?)", re.I)
INDEX_RE = re.compile(r"\bCREATE\s+(?:(?:UNIQUE|FULLTEXT|SPATIAL)\s+)?INDEX\s+`?\w+`?\s+ON\s+(`?\w+`?(?:\.`?\w+`?)?)", re.I)
DATABASE_RE = re.compile(r"\b(?:USE|CREATE\s+DATABASE(?:\s+IF\s+NOT\s+EXISTS)?)\s+`?(\w+)`?", re.I)
HEADER_DATABASE_RE = re.compile(r"(?m)^[ \t]*--[ \t]+`?(\w+)`?\.`?\w+`?[ \t]+definition\b", re.I)


def _table_name(identifier):
    return identifier.split(".")[-1].strip("`")


def _column_count(statement):
    start = statement.find("(")
    if start < 0:
        return 0
    columns = []
    depth = 1
    quote = None
    escaped = False
    part = []
    for char in statement[start + 1:]:
        if quote:
            part.append(char)
            if escaped:
                escaped = False
            elif char == "\\" and quote != "`":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "'\"`":
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
    return sum(bool(re.match(r"^(?!PRIMARY\b|FOREIGN\b|UNIQUE\b|KEY\b|INDEX\b|CONSTRAINT\b|CHECK\b)[`\w]+\s+", column, re.I)) for column in columns)


def read_ddl(content):
    ddl = content.decode("utf-8-sig") if isinstance(content, bytes) else content.lstrip("\ufeff")
    groups = {}
    global_statements = []
    ddl_statements = []
    table_names = []
    header = HEADER_DATABASE_RE.search(ddl)
    database_name = header.group(1) if header else "-"
    column_count = 0
    for statement in sqlparse.split(ddl):
        classified = sqlparse.format(statement, strip_comments=True).lstrip()
        db_match = DATABASE_RE.match(classified)
        if db_match:
            database_name = db_match.group(1)
        table_match = TABLE_RE.match(classified)
        if table_match:
            ddl_statements.append(statement)
            if database_name == "-" and "." in table_match.group(1):
                database_name = table_match.group(1).split(".", 1)[0].strip("`")
            name = _table_name(table_match.group(1))
            if name not in groups:
                groups[name] = []
                table_names.append(name)
            groups[name].append(statement)
            column_count += _column_count(classified)
        elif (alter_match := ALTER_RE.match(classified)):
            ddl_statements.append(statement)
            name = _table_name(alter_match.group(1))
            groups.setdefault(name, []).append(statement)
        elif (index_match := INDEX_RE.match(classified)):
            ddl_statements.append(statement)
            name = _table_name(index_match.group(1))
            groups.setdefault(name, []).append(statement)
        elif re.match(r"(?:CREATE|USE)\b", classified, re.I):
            ddl_statements.append(statement)
            global_statements.append(statement)

    return {
        "ddl": "\n".join(ddl_statements),
        "table_groups": groups,
        "global_statements": global_statements,
        "table_names": table_names,
        "database_name": database_name,
        "table_count": len(table_names),
        "column_count": column_count,
    }
