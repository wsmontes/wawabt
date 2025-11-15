"""Unit tests for offline mock pipelines."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from engines.mock_pipelines import (
    MockNewsCollectorPipeline,
    MockPerformanceTracker,
    MockRealtimeAlertManager,
    MockSentimentAnalysisPipeline,
    MockSignalExecutionManager,
)


def _write_parquet(dir_path: Path, filename: str, df: pd.DataFrame) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / filename
    df.to_parquet(path, index=False)
    return path


def test_news_pipeline_consumes_fixture(tmp_path: Path):
    df = pd.DataFrame(
        [
            {
                'timestamp': pd.Timestamp('2024-01-01T08:00:00Z'),
                'title': 'Mock headline',
                'content': 'Body',
            }
        ]
    )
    _write_parquet(tmp_path, 'news_sample.parquet', df)

    pipeline = MockNewsCollectorPipeline(tmp_path)
    pipeline.run()

    assert pipeline.run_count == 1


def test_sentiment_pipeline_handles_fixture(tmp_path: Path):
    df = pd.DataFrame(
        [
            {
                'timestamp': pd.Timestamp('2024-01-01T08:00:00Z'),
                'symbol': 'AAPL',
                'sentiment': 0.8,
            }
        ]
    )
    _write_parquet(tmp_path, 'sentiment_sample.parquet', df)

    pipeline = MockSentimentAnalysisPipeline(tmp_path)
    pipeline.run()

    assert pipeline.run_count == 1


def test_signal_alert_and_performance_pipelines_just_increment(tmp_path: Path):
    alert = MockRealtimeAlertManager(tmp_path)
    signal_executor = MockSignalExecutionManager(tmp_path)
    tracker = MockPerformanceTracker(tmp_path)

    alert.run()
    signal_executor.run()
    tracker.run()

    assert alert.run_count == 1
    assert signal_executor.run_count == 1
    assert tracker.run_count == 1
