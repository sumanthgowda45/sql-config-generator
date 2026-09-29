#!/usr/bin/env python3
"""CLI helper to generate SQL without launching the GUI."""

from __future__ import annotations

import argparse
from pathlib import Path

from metadata_loader import load_metadata
from sql_generator import GeneratorOptions, generate_script


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate configuration SQL from table metadata")
    parser.add_argument("metadata", type=Path, help="Path to metadata .json or .csv")
    parser.add_argument("-o", "--output", type=Path, help="Output .sql path")
    parser.add_argument("--dialect", choices=["mysql", "postgres"], default="mysql")
    parser.add_argument("--tables", nargs="*", help="Table names (default: all)")
    parser.add_argument("--drop", action="store_true")
    parser.add_argument("--no-create", action="store_true")
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--seed-rows", type=int, default=2)
    parser.add_argument("--prefix", default="cfg_")
    args = parser.parse_args()

    tables = load_metadata(args.metadata)
    selected = args.tables or [t.name for t in tables]
    options = GeneratorOptions(
        dialect=args.dialect,
        include_drop=args.drop,
        include_create=not args.no_create,
        include_seed_inserts=not args.no_seed,
        config_prefix=args.prefix,
        seed_rows=args.seed_rows,
    )
    sql = generate_script(tables, selected, options)
    if args.output:
        args.output.write_text(sql + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(sql)


if __name__ == "__main__":
    main()
