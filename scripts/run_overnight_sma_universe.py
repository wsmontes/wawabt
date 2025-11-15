#!/usr/bin/env python
"""
Run overnight SMA optimization across a small universe of symbols
using the existing Optuna CLI (scripts/optimize_strategy.py).

- Reusa samples/recipes/sma_optuna.json como template
- Gera recipes temporários por símbolo / asset class
- Chama o CLI via subprocess
- Escreve todos os trials em data/experiments.duckdb
"""

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Dict, Any, Iterable

# Raiz do repo (este script está em scripts/)
ROOT = Path(__file__).resolve().parents[1]

# Recipe base já existente
BASE_RECIPE_PATH = ROOT / "samples" / "recipes" / "sma_optuna.json"

# Onde vamos guardar recipes gerados (só para rastreabilidade)
RECIPES_OUT_DIR = ROOT / "data" / "experiments" / "recipes"

# DuckDB onde o Optuna já sabe escrever (como você já usou)
EXPERIMENTS_DB_PATH = ROOT / "data" / "experiments.duckdb"


# ====== Configuração do universo ======

# 10 stocks (Yahoo Finance)
STOCK_SYMBOLS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA",
    "NVDA",
    "JPM",
    "JNJ",
    "XOM",
]

# 10 cryptos (Binance)
CRYPTO_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "MATICUSDT",
    "LTCUSDT",
]

# Período global da experiência
GLOBAL_FROM = "2023-01-01"
GLOBAL_TO = date.today().isoformat()

# Quantos trials por símbolo (ajusta isso conforme o tempo que quer gastar)
TRIALS_PER_SYMBOL = 30
N_JOBS = 1  # deixa em 1 pra não estressar o DuckDB/IO


# ====== Helpers ======

def load_base_recipe() -> Dict[str, Any]:
    with BASE_RECIPE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_recipe_for_symbol(
    base: Dict[str, Any],
    symbol: str,
    source: str,
    interval: str,
    tag: str,
) -> Dict[str, Any]:
    """
    Clona o recipe base e ajusta apenas o que é específico:
    - name
    - symbols
    - fromdate / todate
    - source / interval
    """
    recipe = dict(base)  # shallow copy

    # Campos de topo
    recipe["name"] = f"sma_optuna_{tag}_{symbol}_{GLOBAL_FROM}_{GLOBAL_TO}"
    recipe["symbols"] = [symbol]
    recipe["fromdate"] = GLOBAL_FROM
    recipe["todate"] = GLOBAL_TO
    recipe["source"] = source
    recipe["interval"] = interval

    # fixed_params a gente só mantém; se quiser tunar mais tarde, faz aqui
    # metadata: copiamos como está; min_closed_trades continua valendo

    return recipe


def save_recipe(recipe: Dict[str, Any], tag: str, symbol: str) -> Path:
    RECIPES_OUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{recipe['name']}.json"
    path = RECIPES_OUT_DIR / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(recipe, f, indent=2, sort_keys=False)
    return path


def run_optuna_cli(recipe_path: Path, n_trials: int) -> int:
    """
    Chama o scripts/optimize_strategy.py com o recipe gerado.
    Retorna o returncode do processo.
    """
    cmd = [
        "python",
        "scripts/optimize_strategy.py",
        "--recipe",
        str(recipe_path),
        "--n-trials",
        str(n_trials),
        "--n-jobs",
        str(N_JOBS),
        "--db-path",
        str(EXPERIMENTS_DB_PATH),
        "--print-best",
    ]
    print("\n==> Running:", " ".join(cmd))
    proc = subprocess.run(cmd)
    return proc.returncode


def iter_jobs() -> Iterable[Dict[str, Any]]:
    # Stocks: yahoo_finance, 1d
    for symbol in STOCK_SYMBOLS:
        yield {
            "symbol": symbol,
            "source": "yahoo_finance",
            "interval": "1d",
            "tag": "stock",
        }

    # Cryptos: binance, 1d
    for symbol in CRYPTO_SYMBOLS:
        yield {
            "symbol": symbol,
            "source": "binance",
            "interval": "1d",
            "tag": "crypto",
        }


def main() -> None:
    if not BASE_RECIPE_PATH.exists():
        raise SystemExit(f"Base recipe not found: {BASE_RECIPE_PATH}")

    base_recipe = load_base_recipe()
    print(f"Loaded base recipe from {BASE_RECIPE_PATH}")
    print(f"Experiments DB: {EXPERIMENTS_DB_PATH}")

    for job in iter_jobs():
        symbol = job["symbol"]
        source = job["source"]
        interval = job["interval"]
        tag = job["tag"]

        print("\n" + "=" * 72)
        print(f"[JOB] {tag.upper()} – {symbol} – source={source} interval={interval}")
        print("=" * 72)

        recipe = build_recipe_for_symbol(
            base=base_recipe,
            symbol=symbol,
            source=source,
            interval=interval,
            tag=tag,
        )
        recipe_path = save_recipe(recipe, tag=tag, symbol=symbol)

        rc = run_optuna_cli(recipe_path, n_trials=TRIALS_PER_SYMBOL)
        if rc != 0:
            print(f"!! Optuna CLI returned non-zero code ({rc}) for {symbol}")
        else:
            print(f"✓ Finished optimization for {symbol}")

    print("\nAll jobs submitted. Results stored in:", EXPERIMENTS_DB_PATH)


if __name__ == "__main__":
    main()
