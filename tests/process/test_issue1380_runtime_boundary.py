"""DM8-A2 public semantic fence and production plan/effect adapter regression."""
from dataclasses import replace
from pathlib import Path
import ast
from urllib.error import HTTPError
from urllib.parse import quote

import pytest

from tools import control_transaction_production_executor as executor
from tools import control_transaction as semantic
from tools.control_transaction_runtime import (
    PRE_TRANSITION_EXTERNAL_MUTATION_PATHS, RuntimeMode, RuntimeMutationFenceError,
    RuntimePathClass, production_provider, resolve_runtime_effect,
)
from tools.execution_record import (
    ActionSpec, ClosureState, ExecutionRecord, LeaseState, MutationScopeState, QAState,
)

HEAD, TARGET, MERGED, SYNCED = (c * 40 for c in "abcd")
INV = "issue1380-test"
TARGET_BRANCH = "cleanup/2d-3d-sync"
WORK = "work/issue-1380"


def record(kind):
    current = ExecutionRecord(
        issue=1380, generation=7, execution_intent="EXECUTE_TICKET",
        owner_kind="SCHEDULER", owner_id="chatgpt.flowv2.work1",
        lane_id="chatgpt.flowv2.work1", slot_id="worker.slot.1",
        source_branch=TARGET_BRANCH, source_sha=HEAD, work_branch=WORK,
        head_sha=HEAD, target_branch=TARGET_BRANCH, target_sha=TARGET,
        state="INTEGRATING", semantic_state="QA_ACCEPTED",
        next_action=ActionSpec(kind=kind, args={
            "pr_number": 1400, "target_branch": TARGET_BRANCH,
            "target_sha": TARGET, "qa_workflow": ".github/workflows/whd-product-regression.yml",
        }, display="test"),
        lease=LeaseState(token="test", invocation_identity=INV, expires_at="2099-01-01T00:00:00Z"),
        qa=QAState(last_accepted_run=1, accepted_head_sha=HEAD),
        closure=ClosureState(merged_sha=MERGED if kind == "FINALIZE" else None),
        updated_at="2026-10-08T02:00:00Z",
    )
    if kind == "RELEASE_PATHS":
        current = replace(current, state="ACTIVE",
            semantic_state="STALE_EXECUTION_RESERVATION_RELEASED_RESTART_REQUIRED",
            next_action=ActionSpec(kind="START_BRANCH", args={}, display="restart"),
            lease=LeaseState(token="old", invocation_identity="expired", expires_at="2000-01-01T00:00:00Z"),
            qa=QAState(), mutation_scope=MutationScopeState(
                target_branch=TARGET_BRANCH, base_sha=TARGET,
                write_paths=("gui.py",), delete_paths=(), reservation_state="RELEASED"))
    return current


class GitHubProvider:
    def __init__(self, *, readback=False):
        self.readback = readback
        self.mutations = []
        self.closed = readback
        self.merged = readback
        self.exists = True
        self.work_head = SYNCED if readback else HEAD
        self.target_head = TARGET

    def api(self, repo, method, path, token, payload=None):
        if method != "GET":
            self.mutations.append((method, path))
            if method == "PUT":
                self.merged, self.target_head = True, MERGED
                return {"merged": True, "sha": MERGED}
            if method == "POST":
                self.work_head = SYNCED
                return {"sha": SYNCED}
            if method == "PATCH":
                self.closed = True
                return {}
            if method == "DELETE":
                self.exists = False
                return None
            raise AssertionError((method, path))
        if path == "/rulesets":
            return []
        if path.startswith("/commits/"):
            return {"check_runs": [{"name": "Governance Mirror Hard Gate", "conclusion": "success"}]}
        if path.startswith("/actions/runs?event=pull_request&head_sha="):
            # Real PR run/job evidence is part of the native MERGE readback.
            workflows = [
                ".github/workflows/whd-control-plane-regression.yml",
                ".github/workflows/whd-product-regression.yml",
                ".github/workflows/whd-governance-single-authority-gate.yml",
            ]
            return {"total_count": len(workflows), "workflow_runs": [
                {"id": 6101 + i, "path": name, "event": "pull_request",
                 "head_branch": WORK, "head_sha": HEAD,
                 "status": "completed", "conclusion": "success",
                 "actor": {"login": "looaeedr", "type": "User"}, "run_attempt": 1}
                for i, name in enumerate(workflows)
            ]}
        if path.startswith("/actions/runs/") and path.endswith("/jobs?per_page=100"):
            run_id = int(path.split("/")[3])
            assert run_id in {6101, 6102, 6103}
            return {"total_count": 1, "jobs": [
                {"run_id": run_id, "status": "completed", "conclusion": "success"}
            ]}
        if path == "/pulls/1400":
            return {"number": 1400, "state": "closed" if self.merged else "open",
                "merged": self.merged, "mergeable": True, "merge_commit_sha": MERGED,
                "body": "Closes #1380", "head": {"sha": HEAD, "ref": WORK},
                "base": {"ref": TARGET_BRANCH, "sha": TARGET}}
        if path == "/issues/1380":
            return {"number": 1380, "state": "closed" if self.closed else "open",
                "state_reason": "completed" if self.closed else None,
                "closed_at": "2026-10-08T02:30:00Z" if self.closed else None}
        if path == "/git/ref/heads/" + quote(TARGET_BRANCH, safe=""):
            return {"object": {"sha": self.target_head}}
        if path == "/git/ref/heads/" + quote(WORK, safe=""):
            if not self.exists:
                raise HTTPError(path, 404, "absent", None, None)
            return {"object": {"sha": self.work_head}}
        if path.startswith("/branches/"):
            return {"protected": False, "commit": {"sha": HEAD}}
        if path.startswith("/compare/"):
            return {"merge_base_commit": {"sha": path.split("/compare/")[1].split("...")[0]}}
        raise AssertionError(path)


def installed(monkeypatch, current, provider, *, fresh=None):
    monkeypatch.setattr(executor, "_verified_sync_target_user_token", lambda repo: "verified-test-user-pat")
    monkeypatch.setattr(executor, "_api", provider.api)
    monkeypatch.setattr(executor, "_load_state",
        lambda *args: ("e" * 40, "f" * 40, {1380: fresh or current}))
    return production_provider("looaeedr/whd", "test")


@pytest.mark.parametrize("kind", sorted(PRE_TRANSITION_EXTERNAL_MUTATION_PATHS))
def test_readback_mode_blocks_each_actual_production_mutation(monkeypatch, kind):
    current = record(kind)
    provider = GitHubProvider()
    if kind == "FINALIZE":
        provider.merged = True
    runtime = installed(monkeypatch, current, provider)
    plan = semantic.prepare_transaction(current, kind=kind, transaction_id="new", invocation_identity=INV)
    with pytest.raises(RuntimeMutationFenceError, match="READBACK_ONLY"):
        resolve_runtime_effect(current, plan, RuntimeMode.READBACK_ONLY, runtime,
            {"delete_stale_work_branch": True, "reason": "stale"})
    assert provider.mutations == []


@pytest.mark.parametrize("kind", sorted(PRE_TRANSITION_EXTERNAL_MUTATION_PATHS))
def test_existing_readback_paths_remain_available_in_readback_mode(monkeypatch, kind):
    current = record(kind)
    provider = GitHubProvider(readback=True)
    if kind == "RELEASE_PATHS":
        provider.exists = False
    runtime = installed(monkeypatch, current, provider)
    plan = semantic.prepare_transaction(current, kind=kind, transaction_id="new", invocation_identity=INV)
    envelope = resolve_runtime_effect(current, plan, RuntimeMode.READBACK_ONLY, runtime, {"reason": "stale"})
    assert envelope.path_class == RuntimePathClass.READBACK_ONLY
    assert envelope.provider_mutation_performed is False
    assert provider.mutations == []
    assert current.generation == 7


@pytest.mark.parametrize("kind", sorted(PRE_TRANSITION_EXTERNAL_MUTATION_PATHS))
def test_fresh_same_issue_drift_is_rejected_before_provider_mutation(monkeypatch, kind):
    current = record(kind)
    provider = GitHubProvider()
    if kind == "FINALIZE":
        provider.merged = True
    runtime = installed(monkeypatch, current, provider, fresh=replace(current, generation=8))
    plan = semantic.prepare_transaction(current, kind=kind, transaction_id="new", invocation_identity=INV)
    with pytest.raises(semantic.ControlTransactionConflict, match="generation drift"):
        resolve_runtime_effect(current, plan, RuntimeMode.MUTATION_ALLOWED, runtime, {})
    assert provider.mutations == []


def test_semantic_execution_uses_the_public_exact_plan_validator(monkeypatch):
    current = record("RELEASE_PATHS")
    plan = semantic.prepare_transaction(current, kind="RELEASE_PATHS", transaction_id="new")
    def reject(*args):
        raise semantic.ControlTransactionConflict("public validator sentinel")
    monkeypatch.setattr(semantic, "validate_exact_plan", reject)
    with pytest.raises(semantic.ControlTransactionConflict, match="public validator sentinel"):
        semantic.execute_transaction(current, plan, effect={})


def test_ingress_has_no_executor_private_imports_and_writer_paths_are_excluded():
    source = Path(executor.__file__).with_name("control_transaction_request_ingress.py")
    imports = [node for node in ast.walk(ast.parse(source.read_text()))
        if isinstance(node, ast.ImportFrom)
        and node.module == "tools.control_transaction_production_executor"]
    assert all(not item.name.startswith("_") for node in imports for item in node.names)
    assert {"START_BRANCH", "APPLY_COMMIT"}.isdisjoint(PRE_TRANSITION_EXTERNAL_MUTATION_PATHS)


@pytest.mark.parametrize("kind", sorted(PRE_TRANSITION_EXTERNAL_MUTATION_PATHS))
def test_allowed_mode_classifies_only_actual_mutation_paths(monkeypatch, kind):
    current = record(kind)
    provider = GitHubProvider()
    if kind == "FINALIZE":
        provider.merged = True
    runtime = installed(monkeypatch, current, provider)
    plan = semantic.prepare_transaction(current, kind=kind, transaction_id="new", invocation_identity=INV)
    envelope = resolve_runtime_effect(current, plan, RuntimeMode.MUTATION_ALLOWED, runtime,
        {"delete_stale_work_branch": True, "reason": "stale"})
    assert envelope.path_class == RuntimePathClass.PRE_TRANSITION_EXTERNAL_MUTATION
    assert envelope.provider_mutation_performed is True
    assert len(provider.mutations) == 1
    with pytest.raises(TypeError):
        envelope.effect["tampered"] = True


@pytest.mark.parametrize("kind", ["MERGE", "SYNC_TARGET", "FINALIZE"])
def test_plan_invocation_is_the_only_live_effect_owner(monkeypatch, kind):
    current = record(kind)
    provider = GitHubProvider()
    runtime = installed(monkeypatch, current, provider)
    plan = semantic.prepare_transaction(current, kind=kind, transaction_id="new", invocation_identity="foreign")
    with pytest.raises(semantic.ControlTransactionConflict, match="different invocation"):
        resolve_runtime_effect(current, plan, RuntimeMode.MUTATION_ALLOWED, runtime, {})
    assert provider.mutations == []


def test_executor_readback_mode_cannot_publish_a_mutating_transition(monkeypatch):
    current = record("MERGE")
    provider = GitHubProvider()
    installed(monkeypatch, current, provider)
    def forbidden_write(*args, **kwargs):
        raise AssertionError("fenced provider effect cannot publish a coord transition")
    monkeypatch.setattr(executor, "_write_state", forbidden_write)
    with pytest.raises(RuntimeMutationFenceError):
        executor.execute_one(repo="looaeedr/whd", token="test", coord_branch="coord/execution-v2",
            issue=1380, kind="MERGE", lane_id="chatgpt.flowv2.work1", invocation_identity=INV,
            supplied_effect={"runtime_mode": "READBACK_ONLY"})
    assert provider.mutations == []
