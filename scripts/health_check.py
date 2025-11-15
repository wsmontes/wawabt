#!/usr/bin/env python3
"""DuckDB/Parquet health check for WawaBackTrader."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.schema_contracts import TABLE_CONTRACTS, TableContract
from engines.smart_db import SmartDatabaseManager

CRITICAL_TABLES = [
    "news_raw",
    "news_sentiment",
    "news_by_symbol",
    "realtime_alerts",
    "paper_trades",
    "portfolio_state",
]


def collect_contract_stats(
    contracts: Optional[Dict[str, TableContract]] = None,
    root: Path = ROOT,
) -> List[Dict[str, object]]:
    """Inspect parquet roots referenced by the contract metadata."""

    stats = []
    for name, contract in (contracts or TABLE_CONTRACTS).items():
        prefix = contract.storage_pattern.split("{")[0]
        base_path = Path(prefix)
        if not base_path.is_absolute():
            base_path = (root / base_path).resolve()

        entry: Dict[str, object] = {
            "table": name,
            "storage_prefix": str(base_path),
            "path_exists": base_path.exists(),
            "file_count": 0,
            "latest_mtime": None,
            "fixture": contract.fixture,
        }

        if base_path.exists():
            parquet_files = list(base_path.rglob("*.parquet"))
            entry["file_count"] = len(parquet_files)
            if parquet_files:
                latest = max(parquet_files, key=lambda p: p.stat().st_mtime)
                entry["latest_mtime"] = latest.stat().st_mtime
        stats.append(entry)

    return stats


def check_tables(db: SmartDatabaseManager, table_names: Iterable[str]) -> List[Dict[str, object]]:
    """Verify that important DuckDB tables/views exist and list columns."""

    results = []
    for table in table_names:
        record: Dict[str, object] = {"table": table}
        try:
            table_info = db.describe_table(table, limit=1)
        except ValueError as exc:
            record["status"] = "missing"
            record["error"] = str(exc)
        else:
            record["status"] = "ok"
            record["columns"] = [col["name"] for col in table_info["schema"]]
        results.append(record)
    return results


def check_alert_freshness(db: SmartDatabaseManager, max_stale_hours: int) -> Dict[str, object]:
    """Count stale active alerts to surface stuck signals."""

    try:
        query = f"""
            SELECT COUNT(*) AS stale_count
            FROM realtime_alerts
            WHERE status = 'active'
              AND timestamp < now() - INTERVAL '{max_stale_hours} hours'
        """
        row = db.conn.execute(query).fetchone()
    except Exception as exc:  # pragma: no cover - exercised when table missing
        return {"status": "skipped", "error": str(exc)}

    return {"status": "ok", "stale_active": row[0], "max_age_hours": max_stale_hours}


def summarize_results(contract_stats, table_stats, alert_stats) -> Dict[str, object]:
    missing_tables = [t for t in table_stats if t.get("status") != "ok"]
    stale_flag = alert_stats.get("status") == "ok" and alert_stats.get("stale_active", 0) > 0
    overall = "ok" if not missing_tables and not stale_flag else "attention"
    return {
        "status": overall,
        "missing_tables": missing_tables,
        "alert_status": alert_stats,
        "contract_stats": contract_stats,
        "table_stats": table_stats,
    }


def print_report(payload: Dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"[health] overall status: {payload['status']}")
    for table in payload["table_stats"]:
        status = table.get("status", "unknown")
        print(f"  - {table['table']}: {status}")
    alert = payload["alert_status"]
    if alert.get("status") == "ok":
        print(f"[health] stale active alerts: {alert.get('stale_active', 0)} (max {alert.get('max_age_hours')}h)")
    else:
        print(f"[health] alert freshness skipped: {alert.get('error')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DuckDB health check")
    parser.add_argument("--db-path", help="Override DuckDB file path")
    parser.add_argument("--max-stale-hours", type=int, default=6,
                        help="Maximum age (hours) for active alerts before warning")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SmartDatabaseManager(db_path=args.db_path) if args.db_path else SmartDatabaseManager()

    try:
        contract_stats = collect_contract_stats()
        table_stats = check_tables(db, CRITICAL_TABLES)
        alert_stats = check_alert_freshness(db, args.max_stale_hours)
        payload = summarize_results(contract_stats, table_stats, alert_stats)
        print_report(payload, args.json)
        return 0 if payload["status"] == "ok" else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
