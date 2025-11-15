PYTHON ?= python
PIP ?= $(PYTHON) -m pip

.PHONY: install install-core install-pipeline install-dev lint test tests smoke smoke-fast sentiment-help

install:
	$(PIP) install -r requirements.txt

install-core:
	$(PIP) install -r requirements-core.txt

install-pipeline:
	$(PIP) install -r requirements-pipeline.txt

install-dev:
	$(PIP) install -r requirements-dev.txt

lint:
	$(PYTHON) -m compileall engines scripts

# Fast deterministic test that uses local fixtures only
test:
	pytest \
		tests/engines/test_bt_data.py \
		tests/engines/test_smart_db.py \
		tests/pipelines/test_mock_pipelines.py \
		tests/integration/test_pipeline_scheduler.py

# Full test suite (can be slow)
tests:
	pytest tests

# Offline smoke checks (compile + sample strategy + CLI help)
smoke:
	$(PYTHON) tools/smoke_check.py

# Skip the strategy run for CI environments without matplotlib display
smoke-fast:
	$(PYTHON) tools/smoke_check.py --skip-strategy

sentiment-help:
	$(PYTHON) scripts/sentiment_champion_strategy.py --help || true
