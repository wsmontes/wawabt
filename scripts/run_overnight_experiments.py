#!/usr/bin/env python
"""Orchestrate overnight Optuna sweeps across symbols and techniques."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from engines.optim.optuna_runner import OptunaBacktestOptimizer
from engines.optim.recipes import ExperimentRecipe

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("overnight")


STOCK_SYMBOLS: List[str] = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "TSLA",
    "META",
    "NVDA",
    "NFLX",
    "JPM",
    "XOM",
]

CRYPTO_SYMBOLS: List[str] = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "MATICUSDT",
]


@dataclass(frozen=True)
class Technique:
    name: str
    recipe_path: Path
    asset_classes: Iterable[str]


TECHNIQUES: List[Technique] = [
    Technique(
        name="sma_cross",
        recipe_path=Path("samples/recipes/sma_optuna.json"),
        asset_classes=("stock", "crypto"),
    ),
    Technique(
        name="rsi_meanreversion",
        recipe_path=Path("samples/recipes/rsi_optuna.json"),
        asset_classes=("stock", "crypto"),
    ),
    Technique(
        name="breakout",
        recipe_path=Path("samples/recipes/breakout_optuna.json"),
        asset_classes=("stock", "crypto"),
    ),
    Technique(
        name="vol_regime_filter",
        recipe_path=Path("samples/recipes/vol_regime_optuna.json"),
        asset_classes=("stock", "crypto"),
    ),
    Technique(
        name="sentiment_trend_filter",
        recipe_path=Path("samples/recipes/sentiment_trend_optuna.json"),
        asset_classes=("stock",),
    ),
    Technique(
        name="sentiment_contrarian",
        recipe_path=Path("samples/recipes/sentiment_contrarian_optuna.json"),
        asset_classes=("stock",),
    ),
]


def today_iso() -> str:
    return dt.date.today().isoformat()


def ensure_live_candidates_table(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS live_candidates (
            as_of TIMESTAMP,
            symbol TEXT,
            asset_class TEXT,
            technique TEXT,
            recipe_name TEXT,
            trial_id INTEGER,
            combined_metric DOUBLE,
            train_sharpe DOUBLE,
            test_sharpe DOUBLE,
            max_drawdown DOUBLE,
            closed_trades INTEGER,
            params_json JSON,
            metadata JSON
        )
        """
    )
    con.close()


def insert_live_candidate(db_path: Path, row: Dict[str, Any]) -> None:
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        INSERT INTO live_candidates (
            as_of,
            symbol,
            asset_class,
            technique,
            recipe_name,
            trial_id,
            combined_metric,
            train_sharpe,
            test_sharpe,
            max_drawdown,
            closed_trades,
            params_json,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            row["as_of"],
            row["symbol"],
            row["asset_class"],
            row["technique"],
            row["recipe_name"],
            row["trial_id"],
            row.get("combined_metric"),
            row.get("train_sharpe"),
            row.get("test_sharpe"),
            row.get("max_drawdown"),
            row.get("closed_trades"),
            json.dumps(row.get("params", {})),
            json.dumps(row.get("metadata", {})),
        ],
    )
    con.close()


def build_recipe_for(
    base_recipe_path: Path,
    symbol: str,
    asset_class: str,
    fromdate: str,
    todate: str,
) -> ExperimentRecipe:
    recipe = ExperimentRecipe.from_path(str(base_recipe_path))
    recipe.name = f"{recipe.name}_{symbol}"
    recipe.symbols = [symbol]
    recipe.fromdate = fromdate
    recipe.todate = todate

    if asset_class == "crypto":
        recipe.source = recipe.source or "binance"
        recipe.commission_preset = recipe.commission_preset or "crypto_binance_default"
    else:
        recipe.source = recipe.source or "yahoo_finance"
        recipe.commission_preset = recipe.commission_preset or "us_stocks_zero"

    metadata = dict(recipe.metadata or {})
    if "train_range" not in metadata or "test_range" not in metadata:
        start = dt.date.fromisoformat(fromdate)
        end = dt.date.fromisoformat(todate)
        midpoint = start + (end - start) / 2
        metadata.setdefault("train_range", [start.isoformat(), midpoint.isoformat()])
        metadata.setdefault("test_range", [midpoint.isoformat(), end.isoformat()])
    metadata.setdefault("min_closed_trades", metadata.get("min_closed_trades", 20))
    metadata.setdefault("penalty_value", metadata.get("penalty_value", 1_000_000))
    recipe.metadata = metadata
    return recipe


def summarize_metadata(best_trial: Any) -> Dict[str, Any]:
    metadata = best_trial.user_attrs.get("metadata", {}) if best_trial else {}
    analyzers: Dict[str, Any] = metadata.get("analyzers", {}) if isinstance(metadata, dict) else {}

    sharpe = None
    sharpe_data = analyzers.get("sharpe")
    if isinstance(sharpe_data, dict):
        sharpe = sharpe_data.get("sharperatio")

    drawdown = None
    drawdown_data = analyzers.get("drawdown")
    if isinstance(drawdown_data, dict):
        max_section = drawdown_data.get("max") or {}
        if isinstance(max_section, dict):
            drawdown = max_section.get("drawdown")

    trades = None
    trade_data = analyzers.get("trades")
    if isinstance(trade_data, dict):
        total = trade_data.get("total")
        if isinstance(total, dict):
            closed = total.get("closed")
            if isinstance(closed, dict):
                trades = closed.get("total")
            elif isinstance(closed, (int, float)):
                trades = closed

    return {
        "metadata": metadata,
        "sharpe": sharpe,
        "drawdown": drawdown,
        "closed_trades": trades,
    }


def run_optuna_for_symbol_technique(
    db_path: Path,
    symbol: str,
    asset_class: str,
    technique: Technique,
    fromdate: str,
    todate: str,
    n_trials: int,
    n_jobs: int,
) -> Optional[Dict[str, Any]]:
    if not technique.recipe_path.exists():
        LOGGER.warning("Skipping %s – missing recipe %s", technique.name, technique.recipe_path)
        return None

    recipe = build_recipe_for(
        base_recipe_path=technique.recipe_path,
        symbol=symbol,
        asset_class=asset_class,
        fromdate=fromdate,
        todate=todate,
    )

    optimizer = OptunaBacktestOptimizer(recipe=recipe, db_path=str(db_path))
    study = optimizer.optimize(n_trials=n_trials, n_jobs=n_jobs)

    best = study.best_trial
    summary = summarize_metadata(best)

    return {
    "as_of": dt.datetime.now(dt.timezone.utc),
        "symbol": symbol,
        "asset_class": asset_class,
        "technique": technique.name,
        "recipe_name": recipe.name,
        "trial_id": best.number,
        "combined_metric": best.value,
        "train_sharpe": summary["sharpe"],
        "test_sharpe": summary["sharpe"],  # placeholder until split runs are recorded separately
        "max_drawdown": summary["drawdown"],
        "closed_trades": summary["closed_trades"],
        "params": best.params,
        "metadata": summary["metadata"],
    }


def plan_symbols(
    include_stocks: bool,
    include_cryptos: bool,
    only_symbols: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    plan: List[Dict[str, str]] = []
    requested = set(symbol.upper() for symbol in only_symbols) if only_symbols else None

    if include_stocks:
        for symbol in STOCK_SYMBOLS:
            if requested and symbol.upper() not in requested:
                continue
            plan.append({"symbol": symbol, "asset_class": "stock"})

    if include_cryptos:
        for symbol in CRYPTO_SYMBOLS:
            if requested and symbol.upper() not in requested:
                continue
            plan.append({"symbol": symbol, "asset_class": "crypto"})

    if requested:
        covered = {entry["symbol"].upper() for entry in plan}
        missing = requested - covered
        for symbol in sorted(missing):
            LOGGER.warning("Requested symbol '%s' is not in the default universe", symbol)

    return plan


def run_overnight_experiments(
    db_path: Path,
    n_trials: int,
    n_jobs: int,
    include_stocks: bool,
    include_cryptos: bool,
    techniques: Iterable[Technique],
    only_symbols: Optional[List[str]] = None,
) -> None:
    ensure_live_candidates_table(db_path)

    fromdate = "2023-01-01"
    todate = today_iso()

    for entry in plan_symbols(include_stocks, include_cryptos, only_symbols):
        symbol = entry["symbol"]
        asset_class = entry["asset_class"]

        for technique in techniques:
            if asset_class not in technique.asset_classes:
                continue

            LOGGER.info("Running %s for %s (%s)", technique.name, symbol, asset_class)
            candidate = run_optuna_for_symbol_technique(
                db_path=db_path,
                symbol=symbol,
                asset_class=asset_class,
                technique=technique,
                fromdate=fromdate,
                todate=todate,
                n_trials=n_trials,
                n_jobs=n_jobs,
            )
            if not candidate:
                continue

            LOGGER.info(
                "Best metric %.4f trial=%s params=%s",
                candidate["combined_metric"],
                candidate["trial_id"],
                candidate["params"],
            )
            insert_live_candidate(db_path, candidate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run overnight Optuna experiments across symbols and techniques.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/experiments.duckdb"),
        help="DuckDB path storing optim_trials/live_candidates.",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=30,
        help="Optuna trials per (symbol, technique).",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=1,
        help="Optuna parallel jobs (per symbol/technique batch).",
    )
    parser.add_argument(
        "--no-stocks",
        action="store_true",
        help="Skip stock universe.",
    )
    parser.add_argument(
        "--no-cryptos",
        action="store_true",
        help="Skip crypto universe.",
    )
    parser.add_argument(
        "--technique",
        action="append",
        help="Restrict to specific technique name(s).",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        help="Restrict to specific symbol(s).",
    )
    return parser.parse_args()


def filter_techniques(selected: Optional[List[str]]) -> List[Technique]:
    if not selected:
        return TECHNIQUES
    allowed = set(selected)
    filtered = [tech for tech in TECHNIQUES if tech.name in allowed]
    missing = allowed - {tech.name for tech in filtered}
    for name in sorted(missing):
        LOGGER.warning("Requested technique '%s' is not defined", name)
    return filtered


def main() -> None:
    args = parse_args()
    techniques = filter_techniques(args.technique)
    if not techniques:
        LOGGER.error("No techniques available. Exiting.")
        return

    run_overnight_experiments(
        db_path=args.db_path,
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
        include_stocks=not args.no_stocks,
        include_cryptos=not args.no_cryptos,
        techniques=techniques,
        only_symbols=args.symbol,
    )


if __name__ == "__main__":
    main()
