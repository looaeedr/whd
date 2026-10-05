from __future__ import annotations

import importlib
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_module(monkeypatch):
    stub = types.ModuleType("tools.control_transaction_production_executor")
    stub._api = lambda *args, **kwargs: None
    stub._load_state = lambda *args, **kwargs: ("c" * 40, "t" * 40, {})
    stub._pr_body_closing_issues = lambda body: ()
    stub.execute_one = lambda **kwargs: {}
    stub.recover_post_delivery_missing_record = lambda **kwargs: {}
    monkeypatch.setitem(sys.modules, "tools.control_transaction_production_executor", stub)
    sys.modules.pop("tools.production_x_post_merge_finalize", None)
    return importlib.import_module("tools.production_x_post_merge_finalize")


def test_discovers_only_exact_production_merge_prs(monkeypatch):
    module = _load_module(monkeypatch)
    head = "a" * 40

    def fake_api(_repo, method, path, _token, payload=None):
        assert method == "GET"
        assert payload is None
        if path == f"/commits/{head}/pulls":
            return [{"number": 1282}, {"number": 7}, {"number": 8}]
        if path == "/pulls/1282":
            return {
                "number": 1282,
                "state": "closed",
                "merged": True,
                "merge_commit_sha": head,
                "base": {"ref": "cleanup/2d-3d-sync"},
                "body": "Closes #1282",
            }
        if path == "/pulls/7":
            return {
                "number": 7,
                "state": "closed",
                "merged": True,
                "merge_commit_sha": head,
                "base": {"ref": "main"},
                "body": "Closes #7",
            }
        if path == "/pulls/8":
            return {
                "number": 8,
                "state": "open",
                "merged": False,
                "merge_commit_sha": None,
                "base": {"ref": "cleanup/2d-3d-sync"},
                "body": "Closes #8",
            }
        raise AssertionError(path)

    monkeypatch.setattr(module, "_api", fake_api)
    rows = module.discover_exact_production_merge_prs(
        "looaeedr/whd", "token", head
    )
    assert [row["number"] for row in rows] == [1282]


def test_merge_commit_message_recovers_pr_when_commit_association_is_empty(monkeypatch):
    module = _load_module(monkeypatch)
    head = "b" * 40

    def fake_api(_repo, method, path, _token, payload=None):
        assert method == "GET"
        assert payload is None
        if path == f"/commits/{head}/pulls":
            return []
        if path == f"/git/commits/{head}":
            return {
                "message": (
                    "Merge pull request #1287 from looaeedr/fix\n\n"
                    "#1282 Repair production-X post-merge finalizer entrypoint"
                )
            }
        if path == "/pulls/1287":
            return {
                "number": 1287,
                "state": "closed",
                "merged": True,
                "merge_commit_sha": head,
                "base": {"ref": "cleanup/2d-3d-sync"},
                "body": "Closes #1282",
            }
        raise AssertionError(path)

    monkeypatch.setattr(module, "_api", fake_api)
    rows = module.discover_exact_production_merge_prs(
        "looaeedr/whd", "token", head
    )
    assert [row["number"] for row in rows] == [1287]


def test_closed_production_pr_fallback_recovers_nonstandard_merge_message(monkeypatch):
    module = _load_module(monkeypatch)
    head = "c" * 40

    def fake_api(_repo, method, path, _token, payload=None):
        assert method == "GET"
        assert payload is None
        if path == f"/commits/{head}/pulls":
            return []
        if path == f"/git/commits/{head}":
            return {"message": "nonstandard merge message"}
        if path.startswith("/pulls?state=closed&base=cleanup%2F2d-3d-sync"):
            return [
                {"number": 1288, "merge_commit_sha": head},
                {"number": 1000, "merge_commit_sha": "d" * 40},
            ]
        if path == "/pulls/1288":
            return {
                "number": 1288,
                "state": "closed",
                "merged": True,
                "merge_commit_sha": head,
                "base": {"ref": "cleanup/2d-3d-sync"},
                "body": "Closes #1282",
            }
        raise AssertionError(path)

    monkeypatch.setattr(module, "_api", fake_api)
    rows = module.discover_exact_production_merge_prs(
        "looaeedr/whd", "token", head
    )
    assert [row["number"] for row in rows] == [1288]


def test_missing_record_routes_through_recovery_then_existing_finalize(monkeypatch):
    module = _load_module(monkeypatch)
    calls = []

    monkeypatch.setattr(module, "_pr_body_closing_issues", lambda _body: (1282,))
    monkeypatch.setattr(
        module,
        "_api",
        lambda _repo, method, path, _token, payload=None: (
            {"number": 1282, "state": "open", "state_reason": None}
            if (method, path) == ("GET", "/issues/1282")
            else (_ for _ in ()).throw(AssertionError((method, path, payload)))
        ),
    )
    monkeypatch.setattr(
        module,
        "_load_state",
        lambda _repo, _token, _coord: ("c" * 40, "t" * 40, {}),
    )

    def fake_recover(**kwargs):
        calls.append(("recover", kwargs))
        return {"coord_commit_sha": "d" * 40, "post_state": "INTEGRATING"}

    def fake_finalize(**kwargs):
        calls.append(("finalize", kwargs))
        return {"post_state": "DONE", "coord_commit_sha": "e" * 40}

    monkeypatch.setattr(module, "recover_post_delivery_missing_record", fake_recover)
    monkeypatch.setattr(module, "execute_one", fake_finalize)

    result = module.finalize_pr_closing_issues(
        repo="looaeedr/whd",
        token="token",
        pr={"number": 1300, "body": "Closes #1282"},
        run_identity="github:post-merge:1",
    )

    assert result == [
        {"issue": 1282, "status": "FINALIZED", "post_state": "DONE"}
    ]
    assert [kind for kind, _ in calls] == ["recover", "finalize"]
    assert calls[0][1]["expected_coord_head"] == "c" * 40
    assert calls[0][1]["supplied_effect"] == {"pr_number": 1300}
    assert calls[1][1]["kind"] == "FINALIZE"
    assert calls[1][1]["issue"] == 1282


def test_native_record_present_does_not_create_second_closure_path(monkeypatch):
    module = _load_module(monkeypatch)
    existing = types.SimpleNamespace(state="INTEGRATING")

    monkeypatch.setattr(module, "_pr_body_closing_issues", lambda _body: (1282,))
    monkeypatch.setattr(
        module,
        "_api",
        lambda *_args, **_kwargs: {"number": 1282, "state": "open"},
    )
    monkeypatch.setattr(
        module,
        "_load_state",
        lambda *_args, **_kwargs: ("c" * 40, "t" * 40, {1282: existing}),
    )
    monkeypatch.setattr(
        module,
        "recover_post_delivery_missing_record",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not recover")),
    )
    monkeypatch.setattr(
        module,
        "execute_one",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not finalize")),
    )

    result = module.finalize_pr_closing_issues(
        repo="looaeedr/whd",
        token="token",
        pr={"number": 1300, "body": "Closes #1282"},
        run_identity="github:post-merge:1",
    )
    assert result == [
        {"issue": 1282, "status": "NATIVE_RECORD_PRESENT", "state": "INTEGRATING"}
    ]


def test_already_closed_issue_is_noop(monkeypatch):
    module = _load_module(monkeypatch)
    monkeypatch.setattr(module, "_pr_body_closing_issues", lambda _body: (1282,))
    monkeypatch.setattr(
        module,
        "_api",
        lambda *_args, **_kwargs: {
            "number": 1282,
            "state": "closed",
            "state_reason": "completed",
        },
    )
    result = module.finalize_pr_closing_issues(
        repo="looaeedr/whd",
        token="token",
        pr={"number": 1300, "body": "Closes #1282"},
        run_identity="github:post-merge:1",
    )
    assert result == [{"issue": 1282, "status": "ALREADY_CLOSED"}]


def test_direct_cli_help_bootstraps_repository_import_path():
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/production_x_post_merge_finalize.py"),
            "--help",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--head-sha" in completed.stdout
    assert "--output" in completed.stdout


def test_workflow_is_production_x_push_only_and_calls_canonical_trigger():
    text = (ROOT / ".github/workflows/whd-post-merge-finalize.yml").read_text(
        encoding="utf-8"
    )
    assert "push:" in text
    assert "cleanup/2d-3d-sync" in text
    assert "issues: write" in text
    assert "contents: write" in text
    assert "production_x_post_merge_finalize.py" in text
    assert "pull_request_target" not in text


def test_control_plane_runner_owns_issue1282_regression():
    text = (ROOT / "tools/control_plane_regression.py").read_text(encoding="utf-8")
    assert '"tools/production_x_post_merge_finalize.py"' in text
    assert '"tests/process/test_issue1282_post_merge_finalize.py"' in text
