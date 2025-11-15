from types import SimpleNamespace

from engines.schema_contracts import TableContract
from scripts import health_check


def test_collect_contract_stats_counts_files(tmp_path):
    base = tmp_path / "news" / "daily"
    base.mkdir(parents=True)
    file_path = base / "sample.parquet"
    file_path.write_text("dummy")

    contracts = {
        "news_daily": TableContract(
            description="test contract",
            storage_pattern=str(base / "{symbol}.parquet"),
            unique_key=["symbol"],
            columns={"symbol": "TEXT"},
            fixture="tests/fixtures/news_daily.json",
        )
    }

    stats = health_check.collect_contract_stats(contracts=contracts, root=tmp_path)
    assert stats[0]["file_count"] == 1
    assert stats[0]["path_exists"] is True


def test_check_tables_marks_missing():
    class FakeDB:
        def describe_table(self, table, limit=1):  # pylint: disable=unused-argument
            if table == "existing":
                return {"schema": [{"name": "id"}, {"name": "value"}]}
            raise ValueError("Table not found")

    db = FakeDB()
    results = health_check.check_tables(db, ["existing", "missing"])

    assert results[0]["status"] == "ok"
    assert results[1]["status"] == "missing"


def test_check_alert_freshness_reports_counts():
    class FakeCursor:
        def fetchone(self):
            return (2,)

    class FakeConn:
        def __init__(self):
            self.executed = []

        def execute(self, query):
            self.executed.append(query)
            return FakeCursor()

    db = SimpleNamespace(conn=FakeConn())
    stats = health_check.check_alert_freshness(db, max_stale_hours=4)

    assert stats["status"] == "ok"
    assert stats["stale_active"] == 2
    assert stats["max_age_hours"] == 4
