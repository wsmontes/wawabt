#!/usr/bin/env python
import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import backtrader as bt

# Garantir que o pacote engines seja encontrado mesmo quando o script roda fora da raiz
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engines import AutoFetchData, CommissionHelper


# =========================
#  Strategias leves
# =========================

class BuyHoldStrategy(bt.Strategy):
    params = dict(printlog=False)

    def __init__(self):
        self.order = None

    def next(self):
        # Buy tudo na primeira barra e segura
        if not self.position:
            cash = self.broker.getcash()
            size = int(cash / self.data.close[0])
            if size > 0:
                self.buy(size=size)


class SMACrossStrategy(bt.Strategy):
    params = dict(
        fast_period=10,
        slow_period=50,
        printlog=False,
    )

    def __init__(self):
        self.fast = bt.ind.SMA(self.data.close, period=self.p.fast_period)
        self.slow = bt.ind.SMA(self.data.close, period=self.p.slow_period)
        self.crossover = bt.ind.CrossOver(self.fast, self.slow)

    def next(self):
        if not self.position:
            if self.crossover > 0:
                self.buy()
        else:
            if self.crossover < 0:
                self.sell()


class RSIMeanReversionStrategy(bt.Strategy):
    params = dict(
        rsi_period=14,
        oversold=30,
        overbought=70,
        printlog=False,
    )

    def __init__(self):
        self.rsi = bt.ind.RSI(self.data.close, period=self.p.rsi_period)

    def next(self):
        if not self.position:
            if self.rsi[0] < self.p.oversold:
                self.buy()
        else:
            # Saiu da zona de “barato”
            if self.rsi[0] > 50:
                self.sell()


class DonchianBreakoutStrategy(bt.Strategy):
    params = dict(
        channel_period=20,
        printlog=False,
    )

    def __init__(self):
        self.dc_high = bt.ind.Highest(self.data.high, period=self.p.channel_period)
        self.dc_low = bt.ind.Lowest(self.data.low, period=self.p.channel_period)

    def next(self):
        if not self.position:
            if self.data.close[0] > self.dc_high[-1]:
                self.buy()
        else:
            if self.data.close[0] < self.dc_low[-1]:
                self.sell()


class BollingerMeanReversionStrategy(bt.Strategy):
    params = dict(
        period=20,
        devfactor=2.0,
        printlog=False,
    )

    def __init__(self):
        self.boll = bt.ind.BollingerBands(
            self.data.close,
            period=self.p.period,
            devfactor=self.p.devfactor,
        )

    def next(self):
        if not self.position:
            if self.data.close[0] < self.boll.lines.bot[0]:
                self.buy()
        else:
            if self.data.close[0] > self.boll.lines.mid[0]:
                self.sell()


class EnsembleSMARSIStrategy(bt.Strategy):
    """
    Combina:
      - Tendência via SMA crossover
      - Temporização via RSI
    Entra comprado quando ambos sugerem compra.
    """
    params = dict(
        fast_period=10,
        slow_period=50,
        rsi_period=14,
        oversold=30,
        overbought=70,
        printlog=False,
    )

    def __init__(self):
        self.fast = bt.ind.SMA(self.data.close, period=self.p.fast_period)
        self.slow = bt.ind.SMA(self.data.close, period=self.p.slow_period)
        self.crossover = bt.ind.CrossOver(self.fast, self.slow)
        self.rsi = bt.ind.RSI(self.data.close, period=self.p.rsi_period)

    def next(self):
        sma_long = self.crossover > 0
        sma_short = self.crossover < 0

        rsi_long = self.rsi[0] < self.p.oversold
        rsi_short = self.rsi[0] > self.p.overbought

        score = 0
        if sma_long:
            score += 1
        if sma_short:
            score -= 1
        if rsi_long:
            score += 1
        if rsi_short:
            score -= 1

        if not self.position:
            if score >= 2:
                self.buy()
        else:
            if score <= 0:
                self.sell()


class EnsembleSMADonchianStrategy(bt.Strategy):
    """
    Combina:
      - SMA trend
      - Donchian breakout
    Exige consenso para entrar.
    """
    params = dict(
        fast_period=10,
        slow_period=50,
        channel_period=20,
        printlog=False,
    )

    def __init__(self):
        self.fast = bt.ind.SMA(self.data.close, period=self.p.fast_period)
        self.slow = bt.ind.SMA(self.data.close, period=self.p.slow_period)
        self.crossover = bt.ind.CrossOver(self.fast, self.slow)

        self.dc_high = bt.ind.Highest(self.data.high, period=self.p.channel_period)
        self.dc_low = bt.ind.Lowest(self.data.low, period=self.p.channel_period)

    def next(self):
        sma_long = self.crossover > 0
        sma_short = self.crossover < 0

        breakout_long = self.data.close[0] > self.dc_high[-1]
        breakout_exit = self.data.close[0] < self.dc_low[-1]

        if not self.position:
            if sma_long and breakout_long:
                self.buy()
        else:
            if sma_short or breakout_exit:
                self.sell()


# =========================
#  Config do universo
# =========================

STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META",
          "NVDA", "TSLA", "JPM", "JNJ", "XOM"]

CRYPTOS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "LTCUSDT",
           "XRPUSDT", "ADAUSDT", "DOGEUSDT", "MATICUSDT", "AVAXUSDT"]

# Modelos e parâmetros default (tudo leve)
MODEL_CONFIGS = {
    "buy_hold": (BuyHoldStrategy, {}),
    "sma_trend": (SMACrossStrategy, {"fast_period": 10, "slow_period": 50}),
    "rsi_meanrev": (RSIMeanReversionStrategy, {"rsi_period": 14, "oversold": 30, "overbought": 70}),
    "donchian_breakout": (DonchianBreakoutStrategy, {"channel_period": 20}),
    "boll_meanrev": (BollingerMeanReversionStrategy, {"period": 20, "devfactor": 2.0}),
    "ensemble_sma_rsi": (EnsembleSMARSIStrategy, {"fast_period": 10, "slow_period": 50,
                                                  "rsi_period": 14, "oversold": 30, "overbought": 70}),
    "ensemble_sma_donchian": (EnsembleSMADonchianStrategy, {"fast_period": 10, "slow_period": 50,
                                                            "channel_period": 20}),
}


# =========================
#  Helpers
# =========================

DEFAULT_SOURCE_BY_CLASS = {
    "stock": "yahoo_finance",
    "crypto": "binance",
}
DEFAULT_COMMISSION_PRESETS = {
    "stock": "us_stocks_zero",
    "crypto": "crypto_binance",
}
DEFAULT_INTERVAL = "1d"
DEFAULT_DB_CONFIG = str(PROJECT_ROOT / "config" / "database.json")
DEFAULT_CONNECTOR_CONFIG = str(PROJECT_ROOT / "config" / "connector.json")
COMMISSION_CONFIG_PATH = str(PROJECT_ROOT / "config" / "commission.json")
_COMMISSION_HELPER: Optional[CommissionHelper] = None


def ensure_project_path(path_str: str) -> str:
    """Resolve relative paths against the project root so scripts work anywhere."""
    path = Path(path_str)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


def get_commission_helper() -> CommissionHelper:
    global _COMMISSION_HELPER
    if _COMMISSION_HELPER is None:
        _COMMISSION_HELPER = CommissionHelper(config_path=COMMISSION_CONFIG_PATH)
    return _COMMISSION_HELPER


def resolve_data_source(asset_class: str, stock_source: str, crypto_source: str) -> str:
    if asset_class == "stock":
        return stock_source
    if asset_class == "crypto":
        return crypto_source
    raise ValueError(f"Unsupported asset class '{asset_class}'")


def resolve_commission_preset(asset_class: str, preset: Optional[str]) -> Optional[str]:
    if not preset or preset.lower() == "auto":
        return DEFAULT_COMMISSION_PRESETS.get(asset_class)

    lowered = preset.lower()
    if lowered in {"none", "off"}:
        return None

    return preset


def apply_commission_scheme(broker: bt.brokers.BackBroker,
                            asset_class: str,
                            commission_preset: Optional[str],
                            manual_commission: Optional[float]) -> Optional[str]:
    preset_to_use = resolve_commission_preset(asset_class, commission_preset)
    if preset_to_use:
        helper = get_commission_helper()
        helper.apply_to_broker(broker, preset_name=preset_to_use)
        return preset_to_use

    if manual_commission is not None:
        broker.setcommission(commission=manual_commission, stocklike=True, percabs=True)
        return "manual"

    return None


def create_data_feed(symbol: str,
                     start: datetime,
                     end: datetime,
                     source: str,
                     interval: str,
                     db_config_path: str,
                     connector_config_path: str) -> bt.feeds.PandasData:
    data_feed = AutoFetchData.create(
        symbol=symbol,
        fromdate=start,
        todate=end,
        source=source,
        interval=interval,
        db_config_path=db_config_path,
        connector_config=connector_config_path,
        use_smart_db=True,
        auto_fetch=True,
    )

    if data_feed is None:
        raise RuntimeError(f"No data available for {symbol} ({source}, {interval})")

    return data_feed


def run_backtest(symbol: str,
                 asset_class: str,
                 model_name: str,
                 strategy_cls: Any,
                 params: Dict[str, Any],
                 start: datetime,
                 end: datetime,
                 data_source: str,
                 interval: str,
                 db_config_path: str,
                 connector_config_path: str,
                 cash: float = 100_000.0,
                 commission: Optional[float] = None,
                 commission_preset: Optional[str] = None) -> Dict[str, Any]:
    t0 = time.perf_counter()
    data_feed = create_data_feed(
        symbol=symbol,
        start=start,
        end=end,
        source=data_source,
        interval=interval,
        db_config_path=db_config_path,
        connector_config_path=connector_config_path,
    )

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    applied_commission = apply_commission_scheme(
        broker=cerebro.broker,
        asset_class=asset_class,
        commission_preset=commission_preset,
        manual_commission=commission,
    )

    cerebro.adddata(data_feed, name=f"{symbol}_{interval}")
    cerebro.addstrategy(strategy_cls, **params)

    # Analyzers leves
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

    strat = cerebro.run()[0]
    t1 = time.perf_counter()

    analyzers = strat.analyzers

    # Sharpe
    sharpe_analysis = analyzers.sharpe.get_analysis()
    sharpe = sharpe_analysis.get("sharperatio", float("nan"))

    # Drawdown
    dd_analysis = analyzers.dd.get_analysis()
    max_dd = None
    if "max" in dd_analysis and isinstance(dd_analysis["max"], dict):
        max_dd = dd_analysis["max"].get("drawdown")

    # Returns / CAGR
    ret_analysis = analyzers.returns.get_analysis()
    # 'rtot' = total return, 'ravg' = average, 'rnorm' / 'rnorm100' etc
    total_return = ret_analysis.get("rtot")  # fração (ex 0.25 = +25%)
    cagr = ret_analysis.get("rnorm")  # aproximado

    # Trades
    trades_analysis = analyzers.trades.get_analysis()
    total_trades = trades_analysis.get("total", {}).get("total", 0)
    won_trades = trades_analysis.get("won", {}).get("total", 0)
    lost_trades = trades_analysis.get("lost", {}).get("total", 0)
    winrate = (won_trades / total_trades) if total_trades > 0 else None

    final_value = cerebro.broker.getvalue()
    pnl_pct = (final_value / cash - 1.0) if cash > 0 else None

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "asset_class": asset_class,
    "source": data_source,
    "interval": interval,
    "commission_preset": applied_commission,
    "manual_commission": commission,
        "model": model_name,
        "start": start.date().isoformat(),
        "end": end.date().isoformat(),
        "params": params,
        "metrics": {
            "final_value": final_value,
            "pnl_pct": pnl_pct,
            "total_return": total_return,
            "cagr": cagr,
            "sharpe": sharpe,
            "max_drawdown_pct": max_dd,
            "total_trades": total_trades,
            "won_trades": won_trades,
            "lost_trades": lost_trades,
            "winrate": winrate,
        },
        "runtime_sec": t1 - t0,
    }


def task_runner(task: Tuple[str, str, str], sweep_ctx: Dict[str, Any]) -> Dict[str, Any]:
    symbol, asset_class, model_name = task
    start: datetime = sweep_ctx["start"]
    end: datetime = sweep_ctx["end"]
    cash: float = sweep_ctx["cash"]
    commission: Optional[float] = sweep_ctx["commission"]
    raw_commission_preset: Optional[str] = sweep_ctx["commission_preset"]
    interval: str = sweep_ctx["interval"]
    stock_source: str = sweep_ctx["stock_source"]
    crypto_source: str = sweep_ctx["crypto_source"]
    db_config: str = sweep_ctx["db_config"]
    connector_config: str = sweep_ctx["connector_config"]

    data_source = resolve_data_source(asset_class, stock_source, crypto_source)
    resolved_commission = resolve_commission_preset(asset_class, raw_commission_preset)
    strategy_cls, base_params = MODEL_CONFIGS[model_name]
    params = dict(base_params)

    try:
        return run_backtest(
            symbol=symbol,
            asset_class=asset_class,
            model_name=model_name,
            strategy_cls=strategy_cls,
            params=params,
            start=start,
            end=end,
            data_source=data_source,
            interval=interval,
            db_config_path=db_config,
            connector_config_path=connector_config,
            cash=cash,
            commission=commission,
            commission_preset=resolved_commission,
        )
    except Exception as exc:  # noqa: BLE001 - propagate error details to output
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "asset_class": asset_class,
            "source": data_source,
            "interval": interval,
            "commission_preset": resolved_commission,
            "manual_commission": commission,
            "model": model_name,
            "start": start.date().isoformat(),
            "end": end.date().isoformat(),
            "params": params,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }


def main():
    parser = argparse.ArgumentParser(
        description="Run multi-model sweep over main stocks & cryptos and log JSON lines."
    )
    parser.add_argument("--start", default="2023-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD, default: today)")
    parser.add_argument("--cash", type=float, default=100_000.0, help="Initial cash")
    parser.add_argument("--commission", type=float, default=None,
                        help="Manual commission per trade (only used if preset is 'none')")
    parser.add_argument("--commission-preset", default="auto",
                        help="Commission preset (auto, none, us_stocks_zero, crypto_binance, ...)")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="Data interval (ex: 1d, 1h, 5m)")
    parser.add_argument("--stock-source", default=DEFAULT_SOURCE_BY_CLASS["stock"],
                        help="Data source for stocks (yahoo_finance, alpaca, ...)")
    parser.add_argument("--crypto-source", default=DEFAULT_SOURCE_BY_CLASS["crypto"],
                        help="Data source for cryptos (binance, ccxt, ...)")
    parser.add_argument("--db-config", default=DEFAULT_DB_CONFIG,
                        help="Path to database config JSON")
    parser.add_argument("--connector-config", default=DEFAULT_CONNECTOR_CONFIG,
                        help="Path to connector config JSON")
    parser.add_argument("--max-workers", type=int, default=4, help="Parallel workers")
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end) if args.end else datetime.utcnow()
    stock_source = args.stock_source or DEFAULT_SOURCE_BY_CLASS["stock"]
    crypto_source = args.crypto_source or DEFAULT_SOURCE_BY_CLASS["crypto"]
    db_config = ensure_project_path(args.db_config)
    connector_config = ensure_project_path(args.connector_config)

    universe: List[Tuple[str, str]] = []
    for s in STOCKS:
        universe.append((s, "stock"))
    for c in CRYPTOS:
        universe.append((c, "crypto"))

    tasks: List[Tuple[str, str, str]] = []
    for symbol, asset_class in universe:
        for model_name in MODEL_CONFIGS.keys():
            tasks.append((symbol, asset_class, model_name))

    sweep_ctx: Dict[str, Any] = {
        "start": start,
        "end": end,
        "cash": args.cash,
        "commission": args.commission,
        "commission_preset": args.commission_preset,
        "interval": args.interval,
        "stock_source": stock_source,
        "crypto_source": crypto_source,
        "db_config": db_config,
        "connector_config": connector_config,
    }

    print(f"# multi_model_sweep start={start.date()} end={end.date()} "
          f"interval={args.interval} stock_source={stock_source} crypto_source={crypto_source} "
          f"symbols={len(universe)} models={len(MODEL_CONFIGS)} tasks={len(tasks)}",
          flush=True)

    runner = partial(task_runner, sweep_ctx=sweep_ctx)
    with ProcessPoolExecutor(max_workers=args.max_workers) as ex:
        futures = [ex.submit(runner, t) for t in tasks]
        for fut in as_completed(futures):
            rec = fut.result()
            # 1 linha JSON por resultado
            print(json.dumps(rec, default=str), flush=True)


if __name__ == "__main__":
    main()
