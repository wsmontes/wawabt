"""Declarative experiment recipes feeding the optimization runners.

Recipes keep CLI/agents agnostic to the underlying optimizer (Optuna, Nevergrad,
manual sweeps). Each recipe is serializable to JSON/YAML so that experiments can
be launched from scripts, tests, or notebooks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import json


@dataclass
class ParameterSpace:
    """Describe how a single parameter should be sampled.

    Attributes:
        name: Strategy parameter name.
        kind: Sampling type ("int", "float", "categorical").
        low: Minimum value (for numeric kinds).
        high: Maximum value (for numeric kinds).
        step: Step size for int sampling.
        log: Whether to sample on a log scale.
        choices: Explicit categorical options.
    """

    name: str
    kind: str
    low: Optional[float] = None
    high: Optional[float] = None
    step: Optional[float] = None
    log: bool = False
    choices: Optional[List[Any]] = None

    def sample(self, trial) -> Any:
        """Sample a value using an Optuna-style trial object."""

        kind = self.kind.lower()
        if kind == "int":
            if self.low is None or self.high is None:
                raise ValueError(f"Integer parameter '{self.name}' requires low/high")
            if self.step:
                return trial.suggest_int(
                    self.name,
                    int(self.low),
                    int(self.high),
                    step=int(self.step),
                )
            return trial.suggest_int(self.name, int(self.low), int(self.high))
        if kind == "float":
            if self.low is None or self.high is None:
                raise ValueError(f"Float parameter '{self.name}' requires low/high")
            return trial.suggest_float(self.name, float(self.low), float(self.high), log=self.log, step=self.step)
        if kind == "categorical":
            if not self.choices:
                raise ValueError(f"Categorical parameter '{self.name}' requires choices")
            return trial.suggest_categorical(self.name, self.choices)
        raise ValueError(f"Unsupported parameter kind '{self.kind}'")


@dataclass
class ExperimentRecipe:
    """Serializable description of a hyper-parameter experiment."""

    name: str
    strategy_module: str
    strategy_class: str
    symbols: List[str]
    fromdate: Optional[str] = None
    todate: Optional[str] = None
    source: str = "yahoo_finance"
    interval: str = "1d"
    cash: float = 100_000.0
    commission_preset: Optional[str] = "us_stocks_zero"
    analyzer_preset: str = "minimal"
    metric: str = "sharpe"
    maximize: bool = True
    fixed_params: Dict[str, Any] = field(default_factory=dict)
    parameter_space: List[ParameterSpace] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def timeframe(self) -> Dict[str, Optional[datetime]]:
        fmt = "%Y-%m-%d"
        return {
            "fromdate": datetime.strptime(self.fromdate, fmt) if self.fromdate else None,
            "todate": datetime.strptime(self.todate, fmt) if self.todate else None,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ExperimentRecipe":
        params = payload.copy()
        params["parameter_space"] = [ParameterSpace(**spec) for spec in payload.get("parameter_space", [])]
        return cls(**params)

    @classmethod
    def from_path(cls, path: str | Path) -> "ExperimentRecipe":
        raw = Path(path).read_text()
        if path.endswith((".yaml", ".yml")):
            try:
                import yaml  # type: ignore
            except ImportError as exc:  # pragma: no cover
                raise ImportError("PyYAML is required to parse recipe YAML files") from exc
            payload = yaml.safe_load(raw)
        else:
            payload = json.loads(raw)
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        data["parameter_space"] = [vars(spec) for spec in self.parameter_space]
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def iter_parameter_specs(self) -> Iterable[ParameterSpace]:
        return list(self.parameter_space)

    def apply_constraints(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce light-weight domain constraints (like fast < slow)."""

        specs = {spec.name: spec for spec in self.parameter_space}
        fast = params.get("fast_period")
        slow = params.get("slow_period")
        if fast is None or slow is None:
            return params

        fast_spec = specs.get("fast_period")
        slow_spec = specs.get("slow_period")

        fast_low = int(fast_spec.low) if fast_spec and fast_spec.low is not None else None
        fast_high = int(fast_spec.high) if fast_spec and fast_spec.high is not None else None
        slow_low = int(slow_spec.low) if slow_spec and slow_spec.low is not None else None
        slow_high = int(slow_spec.high) if slow_spec and slow_spec.high is not None else None

        # Ensure slow is always ahead of fast
        min_slow = fast + 1
        if slow_low is not None:
            min_slow = max(min_slow, slow_low)

        if slow_high is not None and slow_high < min_slow:
            # Clamp fast down to make room for slow
            max_fast = slow_high - 1
            if fast_low is not None:
                max_fast = max(fast_low, max_fast)
            fast = min(fast, max_fast)
            min_slow = fast + 1

        # Clamp fast into its bounds
        if fast_high is not None:
            fast = min(fast, fast_high)
        if fast_low is not None:
            fast = max(fast, fast_low)

        slow = max(slow, min_slow)
        if slow_high is not None:
            slow = min(slow, slow_high)

        if slow <= fast:
            slow = fast + 1
            if slow_high is not None and slow > slow_high:
                slow = slow_high
            if slow <= fast:
                fast = slow - 1
                if fast_low is not None:
                    fast = max(fast, fast_low)

        params["fast_period"] = int(fast)
        params["slow_period"] = int(slow)
        return params
