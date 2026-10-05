from __future__ import annotations

import importlib
import json
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

    def fake_api(_repo, method, path, _token, payload=None):
        assert method == "GET"
        assert payload is None
        assert path == "/commits/" + "a" * 40 + "/pulls"
        return [
            {
                "number": 1282,
                "state": "closed",
                "merged": True,
                "merge_commit_sha": "a" * 40,
                "base": {"ref": "cleanup/2d-3d-sync"},
                "body": "Closes #1282",
            },
            {
                "number": 7,
                "state": "closed",
                "merged": True,
                "merge_commit_sha": "a" * 40,
                "base": {"ref": "main"},
                "body": "Closes #7",
            },
            {
                "number": 8,
                "state": "open",
                "merged": False,
                "merge_commit_sha": None,
                "base": {"ref": "cleanup/2d-3d-sync"},
                "body": "Closes #8",
            },
        ]

    monkeypatch.setattr(module, "_api", fake_api)
    rows = module.discover_exact_production_merge_prs(
        "looaeedr/whd", "token", "a" * 40
    )
    assert [row["number"] for row in rows] == [1282]


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
    workflow = (ROOT / ".github/workflows/whd-control-plane-regression.yml").read_text(
        encoding="utf-8"
    )
    assert "'tools/production_x_post_merge_finalize.py'" in workflow
    assert "'tests/process/test_issue1282_post_merge_finalize.py'" in workflow


def test_direct_cli_entrypoint_bootstraps_repository_root_before_tools_import():
    text = (ROOT / "tools/production_x_post_merge_finalize.py").read_text(encoding="utf-8")
    bootstrap = 'ROOT = Path(__file__).resolve().parents[1]'
    insert = 'sys.path.insert(0, str(ROOT))'
    tools_import = 'from tools.control_transaction_production_executor import ('
    assert bootstrap in text
    assert insert in text
    assert text.index(bootstrap) < text.index(tools_import)
    assert text.index(insert) < text.index(tools_import)
