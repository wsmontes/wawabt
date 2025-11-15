"""Optuna-powered hyper-parameter search wired into CerebroRunner."""
from __future__ import annotations

import importlib
import json
import math
import time
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - exercised when optuna missing
    import optuna  # type: ignore
except ImportError:  # pragma: no cover
    optuna = None  # type: ignore


from ..analyzer_helper import AnalyzerHelper
from ..cerebro_runner import CerebroRunner
from ..smart_db import SmartDatabaseManager
from .recipes import ExperimentRecipe, ParameterSpace


class OptunaBacktestOptimizer:
    """High-level orchestrator that keeps studies consistent with Zenguinis."""

    def __init__(
        self,
        recipe: ExperimentRecipe,
        db_path: Optional[str] = None,
        study_name: Optional[str] = None,
        storage: Optional[str] = None,
    ) -> None:
        if optuna is None:
            raise ImportError(
                "Optuna is required for OptunaBacktestOptimizer. Install it via "
                "pip install -r requirements-experiments.txt"
            )

        self.recipe = recipe
        self.db = SmartDatabaseManager(db_path=db_path) if db_path else None
        direction = "maximize" if recipe.maximize else "minimize"
        self.study = optuna.create_study(
            study_name=study_name or recipe.name,
            direction=direction,
            storage=storage,
            load_if_exists=bool(storage),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def optimize(self, n_trials: int = 20, n_jobs: int = 1) -> Any:
        """Run the study and return the Optuna study object."""

        self.study.optimize(self._objective, n_trials=n_trials, n_jobs=n_jobs)
        return self.study

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _objective(self, trial: Any) -> float:
        params = self.recipe.apply_constraints(self._sample_params(trial))
        start = time.time()
        metric_value, metadata = self._run_trial(params)
        duration = time.time() - start

        trial.set_user_attr("duration_seconds", duration)
        trial.set_user_attr("metadata", metadata)
        self._persist_trial(trial.number, params, metric_value, metadata, duration)
        return metric_value

    def _sample_params(self, trial) -> Dict[str, Any]:
        sampled = {}
        for spec in self.recipe.iter_parameter_specs():
            if not isinstance(spec, ParameterSpace):
                spec = ParameterSpace(**spec)
            sampled[spec.name] = spec.sample(trial)
        sampled.update(self.recipe.fixed_params)
        return sampled

    def _run_trial(self, params: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
        timeframe = self.recipe.timeframe()
        module = importlib.import_module(self.recipe.strategy_module)
        strategy_class = getattr(module, self.recipe.strategy_class)

        runner = CerebroRunner(
            cash=self.recipe.cash,
            commission_preset=self.recipe.commission_preset,
        )
        runner.add_multiple_data(
            symbols=self.recipe.symbols,
            fromdate=timeframe["fromdate"],
            todate=timeframe["todate"],
            source=self.recipe.source,
            interval=self.recipe.interval,
        )
        runner.add_strategy(strategy_class, **params)
        if self.recipe.analyzer_preset:
            runner.add_analyzers(self.recipe.analyzer_preset)
        results = runner.run(save_results=False, print_results=False)

        analyzer_results = self._extract_analyzers(runner, results)
        metric_value = self._calculate_metric(runner, analyzer_results)
        metadata = {
            "params": params,
            "analyzers": analyzer_results,
            "final_value": runner.cerebro.broker.getvalue(),
            "cash": self.recipe.cash,
        }
        return metric_value, metadata

    def _extract_analyzers(self, runner: CerebroRunner, results: List[Any]) -> Dict[str, Any]:
        if not results:
            return {}
        # Handle optimization results (list of lists)
        strat = results[0][0] if isinstance(results[0], list) else results[0]
        helper: Optional[AnalyzerHelper] = getattr(runner, "analyzer_helper", None)
        if helper and hasattr(strat, "analyzers"):
            return helper.extract_results(strat)
        return {}

    def _calculate_metric(self, runner: CerebroRunner, analyzers: Dict[str, Any]) -> float:
        metric = self.recipe.metric.lower()
        final_value = runner.cerebro.broker.getvalue()
        pnl = final_value - self.recipe.cash
        pnl_pct = pnl / self.recipe.cash * 100 if self.recipe.cash else 0

        if not self._passes_trade_guard(analyzers):
            return self._penalty_value()

        if metric == "final_value":
            return self._coerce_metric(final_value)
        if metric == "pnl":
            return self._coerce_metric(pnl)
        if metric == "pnl_pct":
            return self._coerce_metric(pnl_pct)
        if metric == "sharpe":
            sharpe = analyzers.get("sharpe", {})
            value = sharpe.get("sharperatio")
            return self._coerce_metric(value)
        if metric in {"max_drawdown", "drawdown"}:
            drawdown = analyzers.get("drawdown", {})
            if isinstance(drawdown, dict):
                max_section = drawdown.get("max") or {}
                value = max_section.get("drawdown")
                magnitude = self._coerce_metric(value)
                return -abs(magnitude)
        # Default fallback
        return self._coerce_metric(final_value)

    def _penalty_value(self) -> float:
        magnitude = self.recipe.metadata.get("penalty_value", 1e6)
        try:
            magnitude = float(magnitude)
        except (TypeError, ValueError):
            magnitude = 1e6
        return -abs(magnitude) if self.recipe.maximize else abs(magnitude)

    def _coerce_metric(self, value: Any, fallback: Optional[float] = None) -> float:
        penalty = self._penalty_value()
        fallback_value = penalty if fallback is None else fallback
        try:
            numeric = float(value)
            if math.isnan(numeric) or math.isinf(numeric):
                return fallback_value
            return numeric
        except (TypeError, ValueError):
            return fallback_value

    def _passes_trade_guard(self, analyzers: Dict[str, Any]) -> bool:
        min_trades = int(self.recipe.metadata.get("min_closed_trades", 0) or 0)
        if min_trades <= 0:
            return True
        closed_trades = self._extract_closed_trades(analyzers)
        return closed_trades >= min_trades

    def _extract_closed_trades(self, analyzers: Dict[str, Any]) -> int:
        trades = analyzers.get("trades")
        if not isinstance(trades, dict):
            return 0

        def _coerce_int(value: Any) -> Optional[int]:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        candidates = []
        total = trades.get("total")
        if isinstance(total, dict):
            total_closed = total.get("closed")
            if isinstance(total_closed, dict):
                candidates.append(total_closed.get("total"))
            candidates.append(total_closed)
        candidates.append(trades.get("closed"))

        for candidate in candidates:
            if isinstance(candidate, dict):
                value = candidate.get("total")
                maybe_int = _coerce_int(value)
                if maybe_int is not None:
                    return maybe_int
            maybe_int = _coerce_int(candidate)
            if maybe_int is not None:
                return maybe_int

        return 0

    def _persist_trial(
        self,
        trial_number: int,
        params: Dict[str, Any],
        metric_value: float,
        metadata: Dict[str, Any],
        duration: float,
    ) -> None:
        if not self.db:
            return
        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "recipe": self.recipe.name,
            "trial": trial_number,
            "metric": self.recipe.metric,
            "metric_value": metric_value,
            "duration": duration,
            "params": json.dumps(params),
            "analyzers": json.dumps(metadata.get("analyzers", {})),
        }
        self._ensure_table()
        self.db.conn.execute(
            "DELETE FROM optim_trials WHERE recipe = ? AND trial = ?",
            (payload["recipe"], payload["trial"]),
        )
        placeholders = ", ".join(["?"] * len(payload))
        columns = ", ".join(payload.keys())
        self.db.conn.execute(
            f"INSERT INTO optim_trials ({columns}) VALUES ({placeholders})",
            list(payload.values()),
        )

    def _ensure_table(self) -> None:
        if not self.db:
            return
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS optim_trials (
                timestamp VARCHAR,
                recipe VARCHAR,
                trial INTEGER,
                metric VARCHAR,
                metric_value DOUBLE,
                duration DOUBLE,
                params VARCHAR,
                analyzers VARCHAR,
                PRIMARY KEY (recipe, trial)
            )
            """
        )
