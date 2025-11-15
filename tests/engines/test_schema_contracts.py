from __future__ import annotations

import pytest

from engines.schema_contracts import TABLE_CONTRACTS, get_contract


def test_contract_map_contains_market_data():
    contract = get_contract('market_data')

    assert 'timestamp' in contract.columns
    assert contract.unique_key == ['symbol', 'timestamp', 'source', 'interval']
    assert contract.fixture.endswith('sample_market_data.csv')


def test_unknown_contract_raises():
    with pytest.raises(KeyError):
        get_contract('unknown_table')


def test_table_contracts_dict_matches_helper():
    assert TABLE_CONTRACTS['news_data'] is get_contract('news_data')
