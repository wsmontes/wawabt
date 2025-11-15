from __future__ import annotations

import types

import pytest

from engines import retry_utils
from engines.retry_utils import retry_decorator, run_with_retry


def test_run_with_retry_success_after_failures(monkeypatch):
    monkeypatch.setattr(retry_utils, "_sleep", lambda _delay: None)

    calls = {"count": 0}

    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("transient")
        return "ok"

    result = run_with_retry(flaky, attempts=5, base_delay=0, max_delay=0, jitter=0)

    assert result == "ok"
    assert calls["count"] == 3


def test_retry_decorator_bubbles_after_exhaustion(monkeypatch):
    monkeypatch.setattr(retry_utils, "_sleep", lambda _delay: None)

    calls = {"count": 0}

    @retry_decorator(attempts=2, base_delay=0, max_delay=0, jitter=0)
    def always_fail():
        calls["count"] += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        always_fail()

    assert calls["count"] == 2
