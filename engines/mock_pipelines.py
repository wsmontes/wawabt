"""Mock pipeline implementations for offline testing."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MockNewsCollectorPipeline:
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = Path(fixtures_dir)
        self.parquet_path = self.fixtures_dir / 'news_sample.parquet'
        self.run_count = 0

    def run(self, lookback_hours: int = 24):  # noqa: D401
        if not self.parquet_path.exists():
            logger.warning('Mock news parquet not found: %s', self.parquet_path)
            return
        self.run_count += 1
        df = pd.read_parquet(self.parquet_path)
        logger.info('[mock] Loaded %s news rows from %s', len(df), self.parquet_path)
        for _, row in df.iterrows():
            logger.info("[mock] %s | %s", row['timestamp'], row['title'])


class MockSentimentAnalysisPipeline:
    def __init__(self, fixtures_dir: Path):
        self.parquet_path = Path(fixtures_dir) / 'sentiment_sample.parquet'
        self.run_count = 0

    def run(self):  # noqa: D401
        if not self.parquet_path.exists():
            logger.warning('Mock sentiment parquet not found: %s', self.parquet_path)
            return
        self.run_count += 1
        df = pd.read_parquet(self.parquet_path)
        logger.info('[mock] Processed %s sentiment rows', len(df))


class MockRealtimeAlertManager:
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = Path(fixtures_dir)
        self.run_count = 0

    def run(self):  # noqa: D401
        self.run_count += 1
        logger.info('[mock] Evaluated alerts using fixtures in %s', self.fixtures_dir)


class MockSignalExecutionManager:
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = Path(fixtures_dir)
        self.run_count = 0

    def run(self):  # noqa: D401
        self.run_count += 1
        logger.info('[mock] Simulated trade execution using fixtures in %s', self.fixtures_dir)


class MockPerformanceTracker:
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = Path(fixtures_dir)
        self.run_count = 0

    def run(self):  # noqa: D401
        self.run_count += 1
        logger.info('[mock] Recorded performance snapshot using fixtures in %s', self.fixtures_dir)
