"""
Regime-Adaptive Rotation Strategy
=================================

This strategy combines trend, momentum, and volatility filters to rotate into
high-quality symbols while enforcing volatility-based position sizing and
risk management. Designed for multi-symbol daily data.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Dict, Optional

import backtrader as bt


class RegimeAdaptiveRotationStrategy(bt.Strategy):
    """Multi-factor rotation with adaptive risk controls.

    Parameters
    ----------
    fast_period : int
        Fast EMA period for trend filter (default 50).
    slow_period : int
        Slow EMA period for trend confirmation (default 200).
    roc_period : int
        Lookback for rate-of-change momentum (default 63 trading days ~ 3 months).
    atr_period : int
        ATR lookback for volatility sizing (default 20).
    max_positions : int
        Maximum concurrent long positions (default 4).
    rebalance_days : int
        Bars between ranking / allocation updates (default 5).
    risk_per_trade : float
        Fraction of equity risked per position using ATR stop (default 0.02).
    atr_stop_multiple : float
        Multiple of ATR used for trailing stop distance (default 2.5).
    take_profit : float
        Profit target expressed as fraction of entry price (default 0.1 => 10%).
    trend_weight : float
        Weight applied to EMA slope component (default 1.0).
    momentum_weight : float
        Weight applied to ROC component (default 0.7).
    volatility_weight : float
        Penalty weight applied to ATR percent (default 0.5).
    minimum_score : float
        Minimum composite score required to participate (default 0.0).
    warmup : int
        Minimum bars required before turning on logic (default 220).
    printlog : bool
        Toggle verbose logs.
    """

    params = (
        ("fast_period", 50),
        ("slow_period", 200),
        ("roc_period", 63),
        ("atr_period", 20),
        ("max_positions", 4),
        ("rebalance_days", 5),
        ("risk_per_trade", 0.02),
        ("atr_stop_multiple", 2.5),
        ("take_profit", 0.10),
        ("trend_weight", 1.0),
        ("momentum_weight", 0.7),
        ("volatility_weight", 0.5),
        ("minimum_score", 0.0),
        ("warmup", 220),
        ("printlog", False),
    )

    def log(self, txt: str, dt: Optional[date] = None) -> None:
        """Logging helper respecting the printlog parameter."""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"[{dt.isoformat()}] {txt}")

    def __init__(self) -> None:
        self.indicators: Dict[bt.LineRoot, Dict[str, bt.Indicator]] = {}
        self.entry_prices: Dict[str, float] = {}
        self.stop_levels: Dict[str, float] = {}
        self.last_rebalance = -self.p.rebalance_days
        self.pending_orders: Dict[str, bt.Order] = {}

        for data in self.datas:
            self.indicators[data] = {
                "ema_fast": bt.indicators.EMA(data.close, period=self.p.fast_period),
                "ema_slow": bt.indicators.EMA(data.close, period=self.p.slow_period),
                "roc": bt.indicators.ROC(data.close, period=self.p.roc_period),
                "atr": bt.indicators.ATR(data, period=self.p.atr_period),
            }

    # ---------------------------------------------------------------------
    # Notification hooks
    # ---------------------------------------------------------------------
    def notify_order(self, order: bt.Order) -> None:
        name = order.data._name or order.data._dataname
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            side = "BUY" if order.isbuy() else "SELL"
            self.log(
                f"{side} EXECUTED [{name}] Price: {order.executed.price:.2f} "
                f"Size: {order.executed.size:.0f} Comm: {order.executed.comm:.2f}"
            )

            if order.isbuy():
                self.entry_prices[name] = order.executed.price
                atr = self.indicators[order.data]["atr"][0]
                if math.isfinite(atr):
                    self.stop_levels[name] = order.executed.price - (
                        self.p.atr_stop_multiple * atr
                    )
            else:
                self.entry_prices.pop(name, None)
                self.stop_levels.pop(name, None)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"ORDER {order.getstatusname()} [{name}]")

        self.pending_orders.pop(name, None)

    def notify_trade(self, trade: bt.Trade) -> None:
        if trade.isclosed:
            name = trade.data._name or trade.data._dataname
            self.log(
                f"TRADE CLOSED [{name}] Gross: {trade.pnl:.2f} Net: {trade.pnlcomm:.2f}"
            )

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------
    def next(self) -> None:
        self._manage_open_positions()

        if len(self) < self.p.warmup:
            return

        if (len(self) - self.last_rebalance) < self.p.rebalance_days:
            return

        self._rebalance_portfolio()
        self.last_rebalance = len(self)

    def _manage_open_positions(self) -> None:
        for data in self.datas:
            position = self.getposition(data)
            if position.size <= 0:
                continue

            name = data._name or data._dataname
            close = data.close[0]
            atr = self.indicators[data]["atr"][0]
            if not (math.isfinite(close) and math.isfinite(atr) and atr > 0):
                continue

            stop = self.stop_levels.get(name)
            entry = self.entry_prices.get(name)
            if stop is None or entry is None:
                continue

            new_stop = max(stop, close - self.p.atr_stop_multiple * atr)
            self.stop_levels[name] = new_stop

            if close <= new_stop:
                self.log(f"Stop hit [{name}] Close={close:.2f} Stop={new_stop:.2f}")
                self.pending_orders[name] = self.close(data=data)
                continue

            target_price = entry * (1 + self.p.take_profit)
            if close >= target_price:
                self.log(
                    f"Take profit [{name}] Close={close:.2f} Target={target_price:.2f}"
                )
                self.pending_orders[name] = self.close(data=data)

    def _rebalance_portfolio(self) -> None:
        candidates = []
        for data in self.datas:
            if len(data) < self.p.warmup:
                continue

            score_tuple = self._compute_score(data)
            if not score_tuple:
                continue

            score, atr, close = score_tuple
            candidates.append((score, data, atr, close))

        if not candidates:
            self.log("No candidates met the score threshold")
            return

        candidates.sort(key=lambda item: item[0], reverse=True)
        eligible = [item for item in candidates if item[0] >= self.p.minimum_score]
        pool = eligible if eligible else candidates
        selected = pool[: self.p.max_positions]
        self.log(
            "Rebalance triggered: "
            f"candidates={len(candidates)} top_score={candidates[0][0]:.4f} "
            f"selected={[ (data._name or data._dataname) for _, data, _, _ in selected ]}"
        )
        target_set = {data for _, data, _, _ in selected}

        for data in self.datas:
            if data in target_set:
                continue
            position = self.getposition(data)
            if position.size > 0:
                name = data._name or data._dataname
                self.log(f"Exiting {name} - no longer ranked")
                self.pending_orders[name] = self.close(data=data)

        for score, data, atr, close in selected:
            name = data._name or data._dataname
            target_size = self._target_position_size(close, atr)
            if target_size <= 0:
                self.log(
                    f"Skipping {name}: close={close:.2f} atr={atr:.2f} "
                    f"target_size={target_size}"
                )
                continue

            position = self.getposition(data)
            if position.size == target_size:
                continue

            self.log(
                f"Allocating {name} Score={score:.4f} Target shares={target_size}"
            )
            self.pending_orders[name] = self.order_target_size(
                data=data, target=target_size
            )

    def _compute_score(self, data: bt.LineRoot) -> Optional[tuple[float, float, float]]:
        ind = self.indicators[data]
        ema_fast = ind["ema_fast"][0]
        ema_slow = ind["ema_slow"][0]
        roc = ind["roc"][0]
        atr = ind["atr"][0]
        close = data.close[0]

        if not all(
            math.isfinite(val)
            for val in (ema_fast, ema_slow, roc, atr, close)
        ):
            return None

        if ema_slow == 0 or close <= 0 or atr <= 0:
            return None

        trend_strength = (ema_fast - ema_slow) / ema_slow
        momentum_strength = roc / 100.0
        atr_pct = atr / close

        score = (
            self.p.trend_weight * trend_strength
            + self.p.momentum_weight * momentum_strength
            - self.p.volatility_weight * atr_pct
        )

        return score, atr, close

    def _target_position_size(self, close: float, atr: float) -> int:
        if close <= 0 or atr <= 0:
            return 0

        equity = self.broker.getvalue()
        risk_budget = equity * self.p.risk_per_trade
        per_share_risk = atr * self.p.atr_stop_multiple
        if per_share_risk <= 0:
            return 0

        atr_based_size = int(risk_budget / per_share_risk)
        max_value_per_position = equity / max(1, self.p.max_positions)
        value_capped_size = int(max_value_per_position / close)

        size = min(atr_based_size, value_capped_size)
        return max(size, 0)

    def stop(self) -> None:
        self.log(f"Final Portfolio Value: {self.broker.getvalue():.2f}")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, "..")
    from engines.bt_data import create_multiple_feeds

    cerebro = bt.Cerebro()
    cerebro.addstrategy(RegimeAdaptiveRotationStrategy)

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM"]
    feeds = create_multiple_feeds(
        symbols,
        fromdate=datetime.now() - timedelta(days=365 * 2),
        todate=datetime.now(),
    )

    if feeds:
        for symbol, feed in feeds.items():
            cerebro.adddata(feed, name=symbol)

        cerebro.broker.setcash(100_000)
        cerebro.broker.setcommission(commission=0.0005)
        cerebro.run()
        print(f"Final Portfolio Value: {cerebro.broker.getvalue():.2f}")
    else:
        print("Failed to load data feeds")
