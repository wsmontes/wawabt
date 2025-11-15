#!/usr/bin/env python
"""
Resumir experimentos do Optuna em cima de data/experiments.duckdb.

Saídas:
- Tabela no terminal com o melhor trial por recipe (já existe na tabela optim_trials)
- (Opcional) JSON com melhores setups por símbolo, agregando múltiplos recipes

Uso básico:
    python scripts/summarize_experiments.py
    python scripts/summarize_experiments.py --out-json data/experiments_summary.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

import duckdb


DEFAULT_DB_PATH = Path("data/experiments.duckdb")


@dataclass
class ParsedRecipe:
    raw: str
    technique: str
    asset_class: Optional[str]
    symbol: str
    fromdate: Optional[str]
    todate: Optional[str]


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_recipe_name(name: str) -> ParsedRecipe:
    """
    Heurística pra decodificar nomes como:
      - sma_optuna_crypto_BTCUSDT_2023-01-01_2025-11-14
      - sma_optuna_stock_AAPL_2023-01-01_2025-11-14
      - sma_optuna_example_TSLA
      - rsi_meanreversion_optuna_NVDA
      - sma_optuna_example

    Não precisa ficar perfeito, só consistente.
    """
    parts = name.split("_")

    technique = "unknown"
    asset_class: Optional[str] = None
    symbol = "UNKNOWN"
    fromdate: Optional[str] = None
    todate: Optional[str] = None

    # technique por prefixo
    if name.startswith("sma_"):
        technique = "sma"
    elif name.startswith("rsi_"):
        technique = "rsi"
    else:
        technique = parts[0]

    #deteção de datas a partir do fim
    dates = [p for p in parts if DATE_RE.match(p)]
    if len(dates) >= 1:
        # assumindo formato ... SYMBOL FROM TO
        # exemplo: sma_optuna_crypto_BTCUSDT_2023-01-01_2025-11-14
        fromdate = dates[0]
        todate = dates[1] if len(dates) >= 2 else None

        # símbolo é o token imediatamente antes da primeira data
        first_date_idx = parts.index(dates[0])
        if first_date_idx - 1 >= 0:
            symbol = parts[first_date_idx - 1]
        # asset_class é o token imediatamente antes do símbolo (quando existir)
        if first_date_idx - 2 >= 0:
            asset_class = parts[first_date_idx - 2]
    else:
        # Não tem datas → formatos tipo rsi_meanreversion_optuna_TSLA
        # ou sma_optuna_example_META
        if len(parts) >= 2:
            symbol = parts[-1]
        if "crypto" in parts:
            asset_class = "crypto"
        elif "stock" in parts:
            asset_class = "stock"
        elif "example" in parts:
            asset_class = "example"

    return ParsedRecipe(
        raw=name,
        technique=technique,
        asset_class=asset_class,
        symbol=symbol,
        fromdate=fromdate,
        todate=todate,
    )


def load_best_trials_per_recipe(db_path: Path) -> list[Dict[str, Any]]:
    """
    Retorna uma lista de dicts com o melhor trial por recipe,
    já ordenado pela métrica (desc).
    Ignora trials de penalidade muito extrema (<= -1e5).
    """
    con = duckdb.connect(str(db_path))

    df = con.execute(
        """
        WITH ranked AS (
            SELECT
              recipe,
              trial,
              metric,
              metric_value,
              duration,
              timestamp,
              params,
              analyzers,
              ROW_NUMBER() OVER (PARTITION BY recipe ORDER BY metric_value DESC) AS rn
            FROM optim_trials
        )
        SELECT
          recipe,
          trial,
          metric,
          metric_value,
          duration,
          timestamp,
          params,
          analyzers
        FROM ranked
        WHERE rn = 1
        """
    ).df()

    # filtrar penalidades grotescas (ex: -1e6)
    results: list[Dict[str, Any]] = []
    for _, row in df.iterrows():
        metric_value = float(row["metric_value"])
        if metric_value <= -1e5:
            # muito provavelmente é penalidade, mas ainda guardamos se quiser olhar depois
            # por enquanto, só pula pra "resumo acionável"
            continue

        parsed = parse_recipe_name(row["recipe"])
        params = json.loads(row["params"]) if row["params"] else {}

        results.append(
            {
                "recipe": row["recipe"],
                "trial": int(row["trial"]),
                "metric_name": row["metric"],
                "metric_value": metric_value,
                "duration": float(row["duration"]) if row["duration"] is not None else None,
                "timestamp": row["timestamp"],
                "params": params,
                "parsed": {
                    "technique": parsed.technique,
                    "asset_class": parsed.asset_class,
                    "symbol": parsed.symbol,
                    "fromdate": parsed.fromdate,
                    "todate": parsed.todate,
                },
            }
        )

    # ordena globalmente pelos melhores Sharpe
    results.sort(key=lambda r: r["metric_value"], reverse=True)
    return results


def build_best_by_symbol(best_by_recipe: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    A partir da lista de melhores por recipe, escolhe o melhor por símbolo,
    independente da técnica. (Se quiser por técnica, dá pra refinar depois.)
    """
    best: Dict[str, Dict[str, Any]] = {}

    for rec in best_by_recipe:
        symbol = rec["parsed"]["symbol"]
        if symbol == "UNKNOWN":
            continue

        current = best.get(symbol)
        if current is None or rec["metric_value"] > current["metric_value"]:
            best[symbol] = rec

    return best


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Optuna experiments from DuckDB")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to DuckDB experiments file (default: data/experiments.duckdb)",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Optional path to write JSON summary with best setup per symbol",
    )
    args = parser.parse_args()

    if not args.db_path.exists():
        raise SystemExit(f"DB not found: {args.db_path}")

    best_by_recipe = load_best_trials_per_recipe(args.db_path)
    best_by_symbol = build_best_by_symbol(best_by_recipe)

    # 1) print tabela humana
    print("=== BEST TRIAL PER RECIPE (filtered, ordered by metric) ===")
    for rec in best_by_recipe:
        p = rec["parsed"]
        params = rec["params"]
        print(
            f"{rec['metric_value']:8.4f}  "
            f"{p['technique']:<5}  "
            f"{(p['asset_class'] or ''):<7}  "
            f"{p['symbol']:<10}  "
            f"{rec['recipe']}"
        )
        print("    params:", params)
        print()

    # 2) print resumo por símbolo
    print("=== BEST CONFIG PER SYMBOL ===")
    for symbol, rec in sorted(best_by_symbol.items(), key=lambda kv: kv[1]["metric_value"], reverse=True):
        p = rec["parsed"]
        print(
            f"{symbol:<10}  {rec['metric_value']:8.4f}  "
            f"technique={p['technique']}  "
            f"asset_class={p['asset_class']}"
        )
        print("    recipe: ", rec["recipe"])
        print("    params: ", rec["params"])
        print()

    # 3) opcional: salvar JSON
    if args.out_json:
        payload = {
            "db_path": str(args.db_path),
            "best_by_recipe": best_by_recipe,
            "best_by_symbol": best_by_symbol,
        }
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
        print(f"JSON summary written to {args.out_json}")


if __name__ == "__main__":
    main()
