"""Regression: stale READY/ExecutionRecord never authorizes ACQUIRE of CLOSED Issue."""
from __future__ import annotations

import pytest

from tools import control_transaction_production_executor as executor


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"number": 1080, "state": "closed"}, "ACQUIRE_ISSUE_NOT_OPEN"),
        ({"number": 1081, "state": "open"}, "ACQUIRE_ISSUE_IDENTITY_MISMATCH"),
        ({"number": 1080, "state": "open", "pull_request": {"url": "pr"}}, "ACQUIRE_ISSUE_IDENTITY_MISMATCH"),
        ({}, "ACQUIRE_ISSUE_IDENTITY_MISMATCH"),
        ({"number": 1080, "state": "unknown"}, "ACQUIRE_ISSUE_NOT_OPEN"),
    ],
)
def test_trusted_acquire_fail_closed_on_stale_issue(monkeypatch, payload, expected):
    monkeypatch.setattr(executor, "_api", lambda *_args, **_kwargs: payload)
    with pytest.raises(executor.ProductionExecutorError, match=expected):
        executor._assert_owning_issue_open_for_acquire("looaeedr/whd", "test-token", 1080)


def test_trusted_acquire_allows_fresh_open_issue(monkeypatch):
    seen = []
    def fresh_get(repo, method, url, token):
        seen.append((repo, method, url))
        return {"number": 1080, "state": "open"}
    monkeypatch.setattr(executor, "_api", fresh_get)
    assert executor._assert_owning_issue_open_for_acquire(
        "looaeedr/whd", "test-token", 1080
    ) is None
    assert seen == [("looaeedr/whd", "GET", "/issues/1080")]


def test_guard_is_called_before_acquire_transaction_write():
    from pathlib import Path
    source = Path(executor.__file__).read_text(encoding="utf-8")
    start = source.index("def _execute_one_attempt(")
    body = source[start:]
    assert 'if kind == "ACQUIRE":\n        _assert_owning_issue_open_for_acquire(repo, token, issue)' in body
    assert body.index('_assert_owning_issue_open_for_acquire(repo, token, issue)') < body.index('plan = prepare_transaction(')
