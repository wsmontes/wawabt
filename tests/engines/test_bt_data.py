"""Unit tests for AutoFetchData dataframe preparation helpers."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from engines.bt_data import AutoFetchData

FIXTURE_CSV = Path(__file__).resolve().parents[1] / "fixtures" / "sample_market_data.csv"


@pytest.fixture()
def sample_dataframe() -> pd.DataFrame:
    df = pd.read_csv(FIXTURE_CSV)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def test_prepare_dataframe_filters_and_shapes(sample_dataframe: pd.DataFrame):
    prepared = AutoFetchData._prepare_dataframe(
        sample_dataframe,
        fromdate=datetime(2024, 1, 3),
        todate=datetime(2024, 1, 5),
    )

    assert prepared is not None
    assert list(prepared.columns) == ['open', 'high', 'low', 'close', 'volume', 'vwap', 'trades']
    assert len(prepared) == 3
    assert prepared.index.min().date().isoformat() == '2024-01-03'
    assert prepared.index.max().date().isoformat() == '2024-01-05'
    assert prepared.index.is_monotonic_increasing
    assert prepared.index.tz is None


def test_prepare_dataframe_handles_optional_columns(sample_dataframe: pd.DataFrame):
    trimmed = sample_dataframe.drop(columns=['vwap', 'trades'])
    prepared = AutoFetchData._prepare_dataframe(
        trimmed,
        fromdate=datetime(2024, 1, 2),
        todate=datetime(2024, 1, 6),
    )

    assert prepared is not None
    assert list(prepared.columns) == ['open', 'high', 'low', 'close', 'volume']


def test_prepare_dataframe_drops_timezone(sample_dataframe: pd.DataFrame):
    tz_df = sample_dataframe.copy()
    tz_df['timestamp'] = tz_df['timestamp'].dt.tz_localize('UTC')

    prepared = AutoFetchData._prepare_dataframe(
        tz_df,
        fromdate=datetime(2024, 1, 2),
        todate=datetime(2024, 1, 6),
    )

    assert prepared is not None
    assert prepared.index.tz is None
    assert len(prepared) == len(tz_df)


def test_prepare_dataframe_missing_required_column(sample_dataframe: pd.DataFrame):
    broken = sample_dataframe.drop(columns=['volume'])

    result = AutoFetchData._prepare_dataframe(
        broken,
        fromdate=datetime(2024, 1, 2),
        todate=datetime(2024, 1, 6),
    )

    assert result is None
