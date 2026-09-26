from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "execution_claim_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("issue686_guard", GUARD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_guard_postcommit_reconciliation_has_durable_proof_input() -> None:
    guard = _load_guard()
    params = inspect.signature(
        guard._assert_post_commit_claim_head_reconciliation
    ).parameters
    assert "local_guard_proof" in params, (
        "local Guard GREEN must have a durable proof input that post-commit "
        "reconciliation can consume"
    )


def test_cli_transports_local_guard_durable_proof() -> None:
    guard = _load_guard()
    parser = guard._build_parser()
    actions = {action.dest for action in parser._actions}
    assert "local_guard_proof" in actions
