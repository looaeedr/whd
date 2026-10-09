"""Regression: production X must never advance without exact /推推 proof."""
from types import SimpleNamespace

import pytest

from tools.localx_publish_gate import (
    INTEGRATION_BRANCH, PRODUCTION_X, PUBLISH_MARKER,
    LocalXPublishDenied, require_publish_approval,
)
from tools import control_transaction_production_executor as ex
from tools.flow_v2_merge_precheck import READY_TO_MERGE


HEAD = "a" * 40
BASE = "b" * 40
PR = 789


def _pr(branch=INTEGRATION_BRANCH, head=HEAD, base=BASE):
    return {
        "head": {"ref": branch, "sha": head},
        "base": {"ref": PRODUCTION_X, "sha": base},
    }


def _proof(head=HEAD, base=BASE, pr=PR, user="looaeedr", role="User"):
    fields = [
        "/推推", PUBLISH_MARKER, "repo=looaeedr/whd",
        f"pr={pr}", "source=localX", f"head={head}",
        "target=cleanup/2d-3d-sync", f"base={base}",
    ]
    return {"user": {"login": user, "type": role}, "body": "\n".join(fields)}


def _check(pr=None, comments=None):
    return require_publish_approval(
        repo="looaeedr/whd", pr_number=PR, pr=pr or _pr(),
        head_sha=HEAD, target_sha=BASE, comments=comments or [],
    )


@pytest.mark.parametrize("proof", [
    None,
    _proof(user="github-actions[bot]", role="Bot"),
    _proof(user="someone-else"),
    _proof(head="c" * 40),
    _proof(base="c" * 40),
    _proof(pr=PR + 1),
    {"user": {"login": "looaeedr", "type": "User"}, "body": "please /推推"},
])
def test_missing_forged_or_stale_approval_fails_closed(proof):
    with pytest.raises(LocalXPublishDenied):
        _check(comments=[proof] if proof else [])


def test_exact_owner_approval_is_accepted():
    _check(comments=[_proof()])


def test_work_branch_cannot_impersonate_localx():
    with pytest.raises(LocalXPublishDenied, match="EXACT_LOCALX"):
        _check(pr=_pr(branch="work/issue-999"), comments=[_proof()])


def test_duplicate_fields_cannot_bypass():
    proof = _proof()
    proof["body"] += "\nhead=" + HEAD
    with pytest.raises(LocalXPublishDenied):
        _check(comments=[proof])


def _record():
    return SimpleNamespace(
        next_action=SimpleNamespace(kind="MERGE", args={"pr_number": PR}),
        head_sha=HEAD, target_sha=BASE, target_branch=PRODUCTION_X,
    )


def _install_merge_stubs(monkeypatch, comments, *, branch="localX"):
    calls = []
    pr = _pr(branch=branch)
    monkeypatch.setattr(ex, "_require_current_invocation_lease", lambda *a, **k: None)
    monkeypatch.setattr(
        ex, "_merge_precheck_readback",
        lambda *a, **k: (pr, SimpleNamespace(classification=READY_TO_MERGE)),
    )
    monkeypatch.setattr(ex, "_read_branch_head", lambda *a, **k: BASE)
    monkeypatch.setattr(ex, "_trusted_merge_anchor_fields", lambda *a, **k: {"merged_sha": "c" * 40})

    def api(repo, method, path, token, payload=None):
        calls.append((method, path))
        if method == "GET" and path.startswith(f"/issues/{PR}/comments?"):
            return comments
        if method == "PUT" and path == f"/pulls/{PR}/merge":
            return {"merged": True}
        if method == "GET" and path == f"/pulls/{PR}":
            return {"merged": True}
        raise AssertionError(f"unexpected GitHub API call {method} {path}")

    monkeypatch.setattr(ex, "_api", api)
    return calls


def test_trusted_merge_cannot_mutate_without_user_command(monkeypatch):
    calls = _install_merge_stubs(monkeypatch, [])
    with pytest.raises(LocalXPublishDenied, match="REQUIRES_EXPLICIT_USER"):
        ex._trusted_merge_effect("looaeedr/whd", "token", record=_record(),
                                 invocation_identity="test", supplied={"approved": True})
    assert all(method == "GET" for method, path in calls)


def test_trusted_merge_rejects_other_work_branch_even_with_proof(monkeypatch):
    calls = _install_merge_stubs(monkeypatch, [_proof()], branch="work/issue-999")
    with pytest.raises(LocalXPublishDenied, match="EXACT_LOCALX"):
        ex._trusted_merge_effect("looaeedr/whd", "token", record=_record(),
                                 invocation_identity="test", supplied={})
    assert all(method == "GET" for method, path in calls)


def test_trusted_merge_passes_only_with_exact_proof(monkeypatch):
    calls = _install_merge_stubs(monkeypatch, [_proof()])
    result = ex._trusted_merge_effect("looaeedr/whd", "token", record=_record(),
                                      invocation_identity="test", supplied={})
    assert result["semantic_state"] == "MERGED"
    assert ("PUT", f"/pulls/{PR}/merge") in calls


def test_comment_readback_unavailable_is_not_authorization(monkeypatch):
    calls = _install_merge_stubs(monkeypatch, [])
    def no_comments(repo, method, path, token, payload=None):
        calls.append((method, path))
        return {"invalid": "not GitHub comments"}
    monkeypatch.setattr(ex, "_api", no_comments)
    with pytest.raises(ex.ProductionExecutorError, match="COMMENT_READBACK_INVALID"):
        ex._trusted_merge_effect("looaeedr/whd", "token", record=_record(),
                                 invocation_identity="test", supplied={})
    assert all(method == "GET" for method, path in calls)
