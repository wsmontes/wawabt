"""Optimization utilities for WawaBackTrader.

The modules in this package keep Mode A experiments (bt_run / CerebroRunner)
entirely declarative. Start with :mod:`engines.optim.optuna_runner` for
hyper-parameter search driven by experiment recipes.
"""

from .recipes import ExperimentRecipe, ParameterSpace  # noqa: F401
from .optuna_runner import OptunaBacktestOptimizer  # noqa: F401
