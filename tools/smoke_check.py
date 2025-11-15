#!/usr/bin/env python3
"""Utility script with fast offline checks for WawaBackTrader.

Run with no arguments to execute all checks:
    python tools/smoke_check.py

Use individual flags to run a subset.
"""
from __future__ import annotations

import argparse
import compileall
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtrader as bt
DATAS_DIR = ROOT / "datas"
SAMPLE_DATA = DATAS_DIR / "orcl-2014.txt"


class SampleSMAStrategy(bt.Strategy):
    params = (('fast', 10), ('slow', 30))

    def __init__(self):
        self.sma_fast = bt.indicators.SMA(period=self.p.fast)
        self.sma_slow = bt.indicators.SMA(period=self.p.slow)

    def next(self):
        if not self.position and self.sma_fast[0] > self.sma_slow[0]:
            self.buy(size=10)
        elif self.position and self.sma_fast[0] < self.sma_slow[0]:
            self.close()


def run_compile(paths: list[Path]) -> None:
    print("[smoke] Compiling python files for syntax check...")
    for path in paths:
        if not path.exists():
            continue
        compileall.compile_dir(str(path), quiet=1)
    print("[smoke] Compile step completed")


def run_strategy_smoke() -> None:
    if not SAMPLE_DATA.exists():
        raise FileNotFoundError(f"Sample data file not found: {SAMPLE_DATA}")

    print("[smoke] Running sample SMA strategy with local CSV data...")
    cerebro = bt.Cerebro()
    data = bt.feeds.YahooFinanceCSVData(
        dataname=str(SAMPLE_DATA),
        reverse=False,
    )
    cerebro.adddata(data)
    cerebro.addstrategy(SampleSMAStrategy)
    cerebro.broker.setcash(10000)
    cerebro.run()
    print(f"[smoke] Strategy finished. Final equity: {cerebro.broker.getvalue():.2f}")


def run_bt_run_help() -> None:
    print("[smoke] Inspecting bt_run.py CLI...")
    subprocess.run([sys.executable, str(ROOT / "bt_run.py"), "--help"], check=True)


def run_pipeline_smoke(fixtures_dir: Path) -> None:
    try:
        from engines import pipeline_scheduler
    except ImportError as exc:  # pragma: no cover - defensive guard
        print(f"[smoke] Skipping pipeline test (import error): {exc}")
        return

    if not getattr(pipeline_scheduler, "APSCHEDULER_AVAILABLE", False):
        print("[smoke] Skipping pipeline test because APScheduler is missing")
        return

    print("[smoke] Running pipeline scheduler in mock/test mode...")
    scheduler = pipeline_scheduler.PipelineScheduler(
        test_mode=True,
        use_mock_pipelines=True,
        fixtures_dir=str(fixtures_dir),
    )

    try:
        scheduler.start()
    finally:
        try:
            scheduler.stop()
        except Exception:
            pass
    print("[smoke] Pipeline scheduler mock cycle complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WawaBackTrader smoke checks")
    parser.add_argument("--skip-compile", action="store_true", help="Skip compileall step")
    parser.add_argument("--skip-strategy", action="store_true", help="Skip sample strategy run")
    parser.add_argument("--skip-cli", action="store_true", help="Skip bt_run.py --help execution")
    parser.add_argument("--skip-pipeline", action="store_true", help="Skip pipeline scheduler smoke test")
    parser.add_argument(
        "--pipeline-fixtures",
        default=str(ROOT / "tests" / "fixtures" / "pipeline"),
        help="Fixture folder used for mock pipelines",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.skip_compile:
        run_compile([ROOT / "engines", ROOT / "scripts"])
    if not args.skip_strategy:
        run_strategy_smoke()
    if not args.skip_cli:
        run_bt_run_help()
    if not args.skip_pipeline:
        run_pipeline_smoke(Path(args.pipeline_fixtures))
    print("[smoke] All requested checks completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
