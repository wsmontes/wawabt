"""Integration tests for PipelineScheduler running in mock/test mode."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from engines import pipeline_scheduler
from engines.pipeline_scheduler import PipelineScheduler


pytestmark = pytest.mark.skipif(
    not pipeline_scheduler.APSCHEDULER_AVAILABLE,
    reason="APScheduler not installed",
)


def _seed_mock_fixtures(fixtures_dir: Path) -> None:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    news_df = pd.DataFrame(
        [
            {
                'timestamp': pd.Timestamp('2024-01-01T08:00:00Z'),
                'title': 'First headline',
                'content': 'Lorem ipsum',
            }
        ]
    )
    sentiment_df = pd.DataFrame(
        [
            {
                'timestamp': pd.Timestamp('2024-01-01T08:00:00Z'),
                'symbol': 'AAPL',
                'sentiment': 0.5,
            }
        ]
    )
    news_df.to_parquet(fixtures_dir / 'news_sample.parquet', index=False)
    sentiment_df.to_parquet(fixtures_dir / 'sentiment_sample.parquet', index=False)


def test_scheduler_runs_each_mock_pipeline_once(tmp_path: Path):
    fixtures_dir = tmp_path / 'pipeline_fixtures'
    _seed_mock_fixtures(fixtures_dir)

    scheduler = PipelineScheduler(
        test_mode=True,
        use_mock_pipelines=True,
        fixtures_dir=str(fixtures_dir),
    )

    try:
        scheduler.start()

        assert scheduler.news_collector.run_count == 1
        assert scheduler.sentiment_pipeline.run_count == 1
        assert scheduler.alert_manager.run_count == 1
        assert scheduler.signal_executor.run_count == 1
        assert scheduler.performance_tracker.run_count == 1

        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) >= 5
    finally:
        try:
            scheduler.stop()
        except Exception:
            pass
