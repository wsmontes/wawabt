"""Tests for SmartDatabaseManager helper/introspection utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import duckdb
import pytest

from engines.smart_db import SmartDatabaseManager


@pytest.fixture()
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "smart_db.duckdb"


@pytest.fixture()
def smart_db(temp_db: Path) -> Iterator[SmartDatabaseManager]:
    manager = SmartDatabaseManager(db_path=str(temp_db))
    yield manager
    manager.close()


def test_navigation_map_includes_descriptions(smart_db: SmartDatabaseManager):
    navigation = smart_db.get_navigation_map()

    assert 'market_data' in navigation
    assert navigation['market_data']['description']
    assert navigation['market_data']['path_pattern'].startswith('data/market')


def test_list_tables_and_describe_table(smart_db: SmartDatabaseManager):
    smart_db.conn.execute("CREATE TABLE test_table (id INTEGER, note VARCHAR)")
    smart_db.conn.execute("INSERT INTO test_table VALUES (1, 'hello')")

    tables = smart_db.list_tables()
    assert 'test_table' in tables

    info = smart_db.describe_table('test_table', limit=10)
    assert any(column['name'] == 'id' for column in info['schema'])
    assert info['preview'][0]['note'] == 'hello'


def test_describe_table_missing_raises(smart_db: SmartDatabaseManager):
    with pytest.raises(ValueError):
        smart_db.describe_table('unknown_table')


def test_self_documentation_includes_tables(smart_db: SmartDatabaseManager):
    smart_db.conn.execute("CREATE TABLE doc_table (value INTEGER)")

    blob = smart_db.get_self_documentation(preview_limit=1)

    assert blob['db_file'].endswith('smart_db.duckdb')
    assert 'navigation' in blob
    assert any(entry['name'] == 'doc_table' for entry in blob['tables'])
