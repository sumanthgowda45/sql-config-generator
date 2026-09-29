"""Generate configuration SQL scripts from table metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from metadata_loader import ColumnMeta, TableMeta


@dataclass
class GeneratorOptions:
    dialect: str = "mysql"  # mysql | postgres
    include_drop: bool = False
    include_create: bool = True
    include_seed_inserts: bool = True
    config_prefix: str = "cfg_"
    seed_rows: int = 1


def _qi(name: str, dialect: str) -> str:
    if dialect == "postgres":
        return f'"{name}"'
    return f"`{name}`"


def _full_table(table: TableMeta, dialect: str) -> str:
    if table.schema and table.schema not in {"public", ""}:
        return f"{_qi(table.schema, dialect)}.{_qi(table.name, dialect)}"
    return _qi(table.name, dialect)


def _sql_type(col: ColumnMeta, dialect: str) -> str:
    t = col.data_type.upper()
    if dialect == "postgres":
        replacements = {
            "DATETIME": "TIMESTAMP",
            "TINYINT": "SMALLINT",
            "DOUBLE": "DOUBLE PRECISION",
            "LONGTEXT": "TEXT",
            "MEDIUMTEXT": "TEXT",
        }
        for src, dst in replacements.items():
            if t.startswith(src):
                return t.replace(src, dst, 1)
    return col.data_type


def _default_sql(col: ColumnMeta, dialect: str) -> str:
    if col.default is None or col.default == "":
        return ""
    value = col.default
    upper = str(value).upper()
    if upper in {"CURRENT_TIMESTAMP", "NOW()", "NULL"}:
        return f" DEFAULT {upper if upper != 'NOW()' else ('NOW()' if dialect == 'postgres' else 'CURRENT_TIMESTAMP')}"
    if str(value).replace(".", "", 1).isdigit():
        return f" DEFAULT {value}"
    escaped = str(value).replace("'", "''")
    return f" DEFAULT '{escaped}'"


def generate_create_table(table: TableMeta, options: GeneratorOptions) -> str:
    dialect = options.dialect
    lines = [f"CREATE TABLE {_full_table(table, dialect)} ("]
    col_lines: list[str] = []
    pk_cols = [c.name for c in table.columns if c.primary_key]

    for col in table.columns:
        null_sql = "NULL" if col.nullable and not col.primary_key else "NOT NULL"
        line = f"  {_qi(col.name, dialect)} {_sql_type(col, dialect)} {null_sql}{_default_sql(col, dialect)}"
        col_lines.append(line)

    if pk_cols:
        pk = ", ".join(_qi(c, dialect) for c in pk_cols)
        col_lines.append(f"  PRIMARY KEY ({pk})")

    lines.append(",\n".join(col_lines))
    lines.append(");")

    if table.comment:
        if dialect == "mysql":
            lines[-1] = lines[-1][:-1] + f" COMMENT='{table.comment.replace(chr(39), chr(39)*2)}';"
        else:
            lines.append(
                f"COMMENT ON TABLE {_full_table(table, dialect)} IS '{table.comment.replace(chr(39), chr(39)*2)}';"
            )
    return "\n".join(lines)


def _sample_value(col: ColumnMeta, row_index: int) -> str:
    name = col.name.lower()
    t = col.data_type.upper()

    if col.primary_key and ("INT" in t or t in {"SERIAL", "BIGSERIAL"}):
        return str(row_index)

    if "BOOL" in t or t == "BIT":
        return "1" if row_index % 2 else "0"

    if any(x in t for x in ("INT", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE")):
        return str(row_index * 10)

    if "DATE" in t or "TIME" in t:
        return "'2026-01-01 00:00:00'"

    if name.endswith("_code") or name == "code":
        return f"'{options_safe(name)}_{row_index}'"

    if name in {"name", "title", "label"}:
        return f"'{table_label(name)} {row_index}'"

    if name in {"is_active", "enabled", "active"}:
        return "1"

    if col.default not in (None, ""):
        upper = str(col.default).upper()
        if upper in {"CURRENT_TIMESTAMP", "NOW()", "NULL"}:
            return "NULL" if upper == "NULL" else "CURRENT_TIMESTAMP"
        if str(col.default).replace(".", "", 1).isdigit():
            return str(col.default)
        return f"'{str(col.default).replace(chr(39), chr(39)*2)}'"

    return f"'sample_{col.name}_{row_index}'"


def options_safe(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).upper()


def table_label(value: str) -> str:
    return value.replace("_", " ").title()


def generate_seed_inserts(table: TableMeta, options: GeneratorOptions) -> str:
    if not table.columns:
        return f"-- No columns for {table.name}"

    dialect = options.dialect
    cols = [c for c in table.columns]
    col_list = ", ".join(_qi(c.name, dialect) for c in cols)
    statements: list[str] = []

    for i in range(1, options.seed_rows + 1):
        values = ", ".join(_sample_value(c, i) for c in cols)
        statements.append(
            f"INSERT INTO {_full_table(table, dialect)} ({col_list}) VALUES ({values});"
        )
    return "\n".join(statements)


def generate_config_registry_sql(tables: list[TableMeta], options: GeneratorOptions) -> str:
    """Generate inserts into a configuration registry table driven by metadata."""
    dialect = options.dialect
    registry = _qi(f"{options.config_prefix}table_registry", dialect)
    lines = [
        f"-- Configuration registry entries generated from table metadata",
        f"CREATE TABLE IF NOT EXISTS {registry} (",
        f"  {_qi('id', dialect)} INT NOT NULL,",
        f"  {_qi('table_name', dialect)} VARCHAR(128) NOT NULL,",
        f"  {_qi('schema_name', dialect)} VARCHAR(128) NOT NULL,",
        f"  {_qi('column_count', dialect)} INT NOT NULL,",
        f"  {_qi('has_pk', dialect)} TINYINT NOT NULL,",
        f"  {_qi('description', dialect)} VARCHAR(512) NULL,",
        f"  {_qi('created_at', dialect)} TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,",
        f"  PRIMARY KEY ({_qi('id', dialect)})",
        ");",
        "",
    ]

    for idx, table in enumerate(tables, start=1):
        has_pk = 1 if any(c.primary_key for c in table.columns) else 0
        desc = (table.comment or f"Config metadata for {table.name}").replace("'", "''")
        lines.append(
            "INSERT INTO {reg} ({id}, {tn}, {sn}, {cc}, {pk}, {ds}) VALUES ({i}, '{name}', '{schema}', {count}, {has_pk}, '{desc}');".format(
                reg=registry,
                id=_qi("id", dialect),
                tn=_qi("table_name", dialect),
                sn=_qi("schema_name", dialect),
                cc=_qi("column_count", dialect),
                pk=_qi("has_pk", dialect),
                ds=_qi("description", dialect),
                i=idx,
                name=table.name.replace("'", "''"),
                schema=table.schema.replace("'", "''"),
                count=len(table.columns),
                has_pk=has_pk,
                desc=desc,
            )
        )
    return "\n".join(lines)


def generate_script(tables: list[TableMeta], selected: list[str], options: GeneratorOptions) -> str:
    selected_set = set(selected)
    chosen = [t for t in tables if t.name in selected_set]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    parts = [
        f"-- Generated by sql-config-generator",
        f"-- Generated at: {now}",
        f"-- Dialect: {options.dialect}",
        f"-- Tables: {', '.join(t.name for t in chosen)}",
        "",
    ]

    if options.include_drop:
        for table in reversed(chosen):
            parts.append(f"DROP TABLE IF EXISTS {_full_table(table, options.dialect)};")
        parts.append("")

    if options.include_create:
        parts.append("-- ===== CREATE TABLES =====")
        for table in chosen:
            parts.append(generate_create_table(table, options))
            parts.append("")

    if options.include_seed_inserts:
        parts.append("-- ===== SEED CONFIG DATA =====")
        for table in chosen:
            parts.append(f"-- Seed rows for {table.name}")
            parts.append(generate_seed_inserts(table, options))
            parts.append("")

    parts.append("-- ===== CONFIG REGISTRY =====")
    parts.append(generate_config_registry_sql(chosen, options))
    parts.append("")
    return "\n".join(parts)
