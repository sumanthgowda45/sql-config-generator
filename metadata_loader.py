"""Load table/column metadata from JSON or CSV files."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


@dataclass
class ColumnMeta:
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    default: str | None = None
    comment: str = ""


@dataclass
class TableMeta:
    name: str
    schema: str = "public"
    columns: list[ColumnMeta] | None = None
    comment: str = ""

    def __post_init__(self) -> None:
        if self.columns is None:
            self.columns = []


def load_metadata(path: str | Path) -> list[TableMeta]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")

    if path.suffix.lower() == ".json":
        return _from_json(path)
    if path.suffix.lower() == ".csv":
        return _from_csv(path)
    raise ValueError("Supported metadata formats: .json, .csv")


def _from_json(path: Path) -> list[TableMeta]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    tables: list[TableMeta] = []
    for item in raw:
        cols = [
            ColumnMeta(
                name=c["name"],
                data_type=c.get("data_type", "VARCHAR(255)"),
                nullable=bool(c.get("nullable", True)),
                primary_key=bool(c.get("primary_key", False)),
                default=c.get("default"),
                comment=c.get("comment", ""),
            )
            for c in item.get("columns", [])
        ]
        tables.append(
            TableMeta(
                name=item["name"],
                schema=item.get("schema", "public"),
                columns=cols,
                comment=item.get("comment", ""),
            )
        )
    return tables


def _from_csv(path: Path) -> list[TableMeta]:
    """
    CSV columns:
    table_name,schema,column_name,data_type,nullable,primary_key,default,table_comment,column_comment
    """
    grouped: dict[tuple[str, str], TableMeta] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = (row.get("schema") or "public", row["table_name"])
            if key not in grouped:
                grouped[key] = TableMeta(
                    name=row["table_name"],
                    schema=row.get("schema") or "public",
                    comment=row.get("table_comment") or "",
                )
            grouped[key].columns.append(
                ColumnMeta(
                    name=row["column_name"],
                    data_type=row.get("data_type") or "VARCHAR(255)",
                    nullable=str(row.get("nullable", "true")).lower() in {"1", "true", "yes", "y"},
                    primary_key=str(row.get("primary_key", "false")).lower() in {"1", "true", "yes", "y"},
                    default=row.get("default") or None,
                    comment=row.get("column_comment") or "",
                )
            )
    return list(grouped.values())


def tables_to_dict(tables: Iterable[TableMeta]) -> list[dict]:
    return [asdict(t) for t in tables]
