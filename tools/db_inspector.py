#!/usr/bin/env python3
"""CLI helper to inspect the SmartDatabaseManager artifacts quickly."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.schema_contracts import get_contract
from engines.smart_db import SmartDatabaseManager


def print_summary(db: SmartDatabaseManager) -> None:
    summary = db.get_data_summary()
    if not summary:
        print("No parquet files detected yet.")
        return
    print("Data Summary (files / size MB):")
    for data_type, stats in summary.items():
        print(f"- {data_type}: {stats['files']} files, {stats['size_mb']} MB")


def print_navigation(db: SmartDatabaseManager) -> None:
    navigation = db.get_navigation_map()
    print(json.dumps(navigation, indent=2))


def print_tables(db: SmartDatabaseManager) -> None:
    tables = db.list_tables()
    if not tables:
        print("No DuckDB tables or views found yet.")
        return
    print("Tables/Views:")
    for table in tables:
        print(f"- {table}")


def print_table(db: SmartDatabaseManager, table: str, limit: int) -> None:
    info = db.describe_table(table, limit=limit)
    print(f"Schema for {table}:")
    for column in info['schema']:
        print(f"  - {column['name']}: {column['type']}")
    print(f"\nPreview (first {limit} rows):")
    for row in info['preview']:
        print(row)


def print_explain(db: SmartDatabaseManager, limit: int) -> None:
    blob = db.get_self_documentation(preview_limit=limit)
    print(json.dumps(blob, indent=2, default=str))


def print_contract(table: str) -> None:
    contract = get_contract(table)
    payload = {
        "description": contract.description,
        "storage_pattern": contract.storage_pattern,
        "unique_key": contract.unique_key,
        "fixture": contract.fixture,
        "columns": contract.columns,
    }
    print(json.dumps(payload, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DuckDB/Parquet inspector for WawaBackTrader")
    parser.add_argument('--db-path', default=None, help='Override DuckDB file path')
    parser.add_argument('--table', help='Table/view name to describe')
    parser.add_argument('--limit', type=int, default=5, help='Number of preview rows')
    parser.add_argument('--navigation', action='store_true', help='Print data navigation map')
    parser.add_argument('--tables', action='store_true', help='List DuckDB tables/views')
    parser.add_argument('--explain', action='store_true', help='Print combined layout/table preview (uses --limit)')
    parser.add_argument('--contract', help='Print canonical schema contract for a managed table')
    parser.add_argument('--summary', action='store_true', help='Print data summary (default action)')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SmartDatabaseManager(db_path=args.db_path) if args.db_path else SmartDatabaseManager()

    try:
        action_taken = False
        if args.navigation:
            print_navigation(db)
            action_taken = True
        if args.tables:
            print_tables(db)
            action_taken = True
        if args.table:
            print_table(db, args.table, args.limit)
            action_taken = True
        if args.contract:
            print_contract(args.contract)
            action_taken = True
        if args.explain:
            print_explain(db, args.limit)
            action_taken = True
        if args.summary or not action_taken:
            print_summary(db)
    finally:
        db.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
