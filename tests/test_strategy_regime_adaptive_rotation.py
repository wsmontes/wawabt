"""Regression tests for the Regime-Adaptive Rotation strategy."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import backtrader as bt

from strategies.regime_adaptive_rotation import RegimeAdaptiveRotationStrategy


def _synthetic_feed(seed: int) -> bt.feeds.PandasData:
    """Create a deterministic synthetic OHLCV dataset with 400 business days."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(datetime(2020, 1, 1), periods=400, freq="B")

    trend = np.linspace(0, 15, len(index))
    noise = rng.normal(0, 2, size=len(index))
    base = 150 + trend + noise.cumsum() * 0.2
    closes = np.maximum(5, base)

    df = pd.DataFrame(
        {
            "open": closes + rng.normal(0, 0.5, len(index)),
            "high": closes + rng.uniform(0.5, 1.5, len(index)),
            "low": closes - rng.uniform(0.5, 1.5, len(index)),
            "close": closes,
            "volume": rng.uniform(80_000, 120_000, len(index)),
            "openinterest": 0,
        },
        index=index,
    )

    return bt.feeds.PandasData(dataname=df)


def test_regime_adaptive_rotation_runs_without_errors():
    """Ensure the strategy can run end-to-end on synthetic multi-symbol data."""
    cerebro = bt.Cerebro()
    cerebro.addstrategy(
        RegimeAdaptiveRotationStrategy,
        printlog=False,
        warmup=150,
        rebalance_days=10,
    )

    cerebro.broker.setcash(100_000)
    cerebro.broker.setcommission(commission=0.0005)

    cerebro.adddata(_synthetic_feed(seed=1), name="AAA")
    cerebro.adddata(_synthetic_feed(seed=7), name="BBB")
    cerebro.adddata(_synthetic_feed(seed=21), name="CCC")

    results = cerebro.run()
    assert results, "Strategy should return a result list"
    assert cerebro.broker.getvalue() > 0
