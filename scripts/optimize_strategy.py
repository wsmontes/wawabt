#!/usr/bin/env python3
"""CLI wrapper for OptunaBacktestOptimizer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.optim import ExperimentRecipe, OptunaBacktestOptimizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize a strategy using Optuna")
    parser.add_argument("--recipe", required=True, help="Path to recipe JSON/YAML")
    parser.add_argument("--n-trials", type=int, default=20, help="Number of trials")
    parser.add_argument("--n-jobs", type=int, default=1, help="Parallel jobs for Optuna")
    parser.add_argument("--study-name", help="Override Optuna study name")
    parser.add_argument("--storage", help="Optuna storage URL (e.g., sqlite:///studies.db)")
    parser.add_argument("--db-path", help="DuckDB path for logging trials")
    parser.add_argument("--print-best", action="store_true", help="Print best params at the end")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    recipe = ExperimentRecipe.from_path(args.recipe)
    optimizer = OptunaBacktestOptimizer(
        recipe=recipe,
        db_path=args.db_path,
        study_name=args.study_name,
        storage=args.storage,
    )
    study = optimizer.optimize(n_trials=args.n_trials, n_jobs=args.n_jobs)

    if args.print_best:
        print("\nBest trial:")
        print(json.dumps({
            "value": study.best_value,
            "params": study.best_params,
            "number": study.best_trial.number,
        }, indent=2))

    print(f"Study '{study.study_name}' finished with best value {study.best_value:.4f}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
