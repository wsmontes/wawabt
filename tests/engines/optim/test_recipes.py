import json
from types import SimpleNamespace

import pytest

from engines.optim.recipes import ExperimentRecipe, ParameterSpace


def test_parameter_space_sampling_int():
    space = ParameterSpace(name="fast", kind="int", low=5, high=10, step=1)

    calls = {}

    class FakeTrial:
        def suggest_int(self, name, low, high, step=None):
            calls["args"] = (name, low, high, step)
            return low

    trial = FakeTrial()
    value = space.sample(trial)

    assert value == 5
    assert calls["args"] == ("fast", 5, 10, 1)


def test_experiment_recipe_from_dict_roundtrip(tmp_path):
    payload = {
        "name": "demo",
        "strategy_module": "strategies.sma_cross",
        "strategy_class": "SMACrossStrategy",
        "symbols": ["AAPL"],
        "parameter_space": [
            {"name": "fast_period", "kind": "int", "low": 5, "high": 15}
        ],
    }
    recipe = ExperimentRecipe.from_dict(payload)
    assert recipe.name == "demo"
    assert recipe.parameter_space[0].name == "fast_period"

    path = tmp_path / "recipe.json"
    path.write_text(recipe.to_json())
    loaded = ExperimentRecipe.from_path(str(path))
    assert loaded.strategy_class == "SMACrossStrategy"
    assert len(loaded.parameter_space) == 1


def test_recipe_timeframe_none_by_default():
    recipe = ExperimentRecipe(
        name="demo",
        strategy_module="strategies.sma_cross",
        strategy_class="SMACrossStrategy",
        symbols=["AAPL"],
    )
    frame = recipe.timeframe()
    assert frame["fromdate"] is None
    assert frame["todate"] is None


def test_parameter_space_enforces_choices():
    space = ParameterSpace(name="mode", kind="categorical", choices=["a", "b"])

    class FakeTrial:
        def suggest_categorical(self, name, choices):
            return choices[0]

    assert space.sample(FakeTrial()) == "a"

    bad_space = ParameterSpace(name="x", kind="categorical")
    with pytest.raises(ValueError):
        bad_space.sample(FakeTrial())
