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
INV = "issue1381-test"
TARGET_BRANCH = "cleanup/2d-3d-sync"
WORK = "localX"


def record(kind):
    current = ExecutionRecord(
        issue=1381, generation=7, execution_intent="EXECUTE_TICKET",
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
        if path.startswith("/issues/1400/comments?"):
            return [{"user": {"login": "looaeedr", "type": "User"},
                     "body": "\n".join([
                         "/推推", "WHD_LOCALX_PUBLISH_AUTH_V1", "repo=looaeedr/whd",
                         "pr=1400", "source=localX", f"head={HEAD}",
                         "target=cleanup/2d-3d-sync", f"base={TARGET}",
                     ])}]
        if path == "/rulesets":
            return []
        if path.startswith("/commits/"):
            return {"total_count": 1, "check_runs": [{"id": 777, "name": "Governance Mirror Hard Gate", "conclusion": "success"}]}
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
        if path == "/pulls/1400/files?per_page=100&page=1":
            return [{"filename": "tools/control_transaction_production_executor.py"},
                    {"filename": "tests/process/test_issue1441_real_pr_ci_gate.py"}]
        if path == "/pulls/1400":
            return {"number": 1400, "state": "closed" if self.merged else "open",
                "merged": self.merged, "mergeable": True, "merge_commit_sha": MERGED,
                "body": "Closes #1381", "head": {"sha": HEAD, "ref": WORK},
                "base": {"ref": TARGET_BRANCH, "sha": TARGET}}
        if path == "/issues/1381":
            return {"number": 1381, "state": "closed" if self.closed else "open",
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
    monkeypatch.setattr(executor, "_api", provider.api)
    monkeypatch.setattr(executor, "_load_state",
        lambda *args: ("e" * 40, "f" * 40, {1381: fresh or current}))
    return production_provider("looaeedr/whd", "test")




class CoordRace:
    def __init__(self, current, provider, *, drift=None, exhaust=False):
        self.current, self.provider = current, provider
        self.drift, self.exhaust = drift, exhaust
        self.loads, self.writes = 0, []
        self.committed = None

    def load(self, *args):
        self.loads += 1
        value = self.committed or (self.drift if self.writes and self.drift else self.current)
        return ("9" * 40 if self.committed else "e" * 40), "f" * 40, {1381: value}

    def write(self, *args, records, **kwargs):
        self.writes.append(records[1381])
        if len(self.writes) == 1 or self.exhaust:
            raise semantic.ControlTransactionConflict("coord/execution-v2 ref advanced during transaction test race")
        self.committed = records[1381]
        return "9" * 40, "8" * 40


def setup_race(monkeypatch, kind, *, readback=False, drift=None, exhaust=False):
    current = record(kind)
    provider = GitHubProvider(readback=readback)
    if kind == "FINALIZE": provider.merged = True
    if kind == "RELEASE_PATHS" and readback: provider.exists = False
    race = CoordRace(current, provider, drift=drift, exhaust=exhaust)
    monkeypatch.setattr(executor, "_verified_sync_target_user_token", lambda repo: "verified-test-user-pat")
    monkeypatch.setattr(executor, "_api", provider.api)
    monkeypatch.setattr(executor, "_load_state", race.load)
    monkeypatch.setattr(executor, "_write_state", race.write)
    monkeypatch.setattr(executor, "_publish_transaction_progress", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("monitor irrelevant")))
    return current, provider, race


def invoke(kind):
    return executor.execute_one(repo="looaeedr/whd", token="secret-token", coord_branch="coord/execution-v2",
        issue=1381, kind=kind, lane_id="chatgpt.flowv2.work1", invocation_identity=INV,
        supplied_effect={"reason": "stale cleanup", "delete_stale_work_branch": True} if kind == "RELEASE_PATHS" else {},
        _allow_terminal_drain=False)


@pytest.mark.parametrize("kind", sorted(PRE_TRANSITION_EXTERNAL_MUTATION_PATHS))
@pytest.mark.parametrize("readback", [False, True])
def test_unrelated_cas_reuses_identical_post_without_normalizing_or_preparing_again(monkeypatch, kind, readback):
    current, provider, race = setup_race(monkeypatch, kind, readback=readback)
    counts = {"prepare": 0, "normalize": 0, "resolve": 0}
    for name, key in [("prepare_transaction", "prepare"), ("_normalize_effect", "normalize"), ("resolve_runtime_effect", "resolve")]:
        original = getattr(executor, name)
        def counted(*a, _original=original, _key=key, **k):
            counts[_key] += 1
            return _original(*a, **k)
        monkeypatch.setattr(executor, name, counted)
    result = invoke(kind)
    assert result["result"] == "APPLIED"
    assert len(provider.mutations) == (0 if readback else 1)
    assert len(race.writes) == 2 and race.writes[0] is race.writes[1]
    assert counts == {"prepare": 1, "normalize": 1, "resolve": 1}


@pytest.mark.parametrize("kind", sorted(PRE_TRANSITION_EXTERNAL_MUTATION_PATHS))
def test_cas_exhaustion_is_typed_nonretryable_and_never_reenters_effect(monkeypatch, kind):
    from tools.control_transaction_runtime import RuntimePostEffectConflict
    current, provider, race = setup_race(monkeypatch, kind, exhaust=True)
    with pytest.raises(RuntimePostEffectConflict) as caught: invoke(kind)
    assert caught.value.retryable is False
    assert caught.value.conflict_class == "POST_EFFECT_COORD_CAS_EXHAUSTED"
    assert len(provider.mutations) == 1
    assert len(race.writes) == 5
    assert all(p is race.writes[0] for p in race.writes)
    assert caught.value.diagnostics["authority"] == "NON_AUTHORITY"
    assert "secret-token" not in repr(caught.value.diagnostics)


@pytest.mark.parametrize("kind", ["MERGE", "SYNC_TARGET", "FINALIZE"])
def test_same_issue_drift_uses_new_exact_plan_and_readback_only_once(monkeypatch, kind):
    drift = replace(record(kind), generation=8)
    current, provider, race = setup_race(monkeypatch, kind, drift=drift)
    plans, modes = [], []
    original = executor.resolve_runtime_effect
    def capture(r, plan, mode, *a, **k):
        plans.append(plan); modes.append(mode)
        return original(r, plan, mode, *a, **k)
    monkeypatch.setattr(executor, "resolve_runtime_effect", capture)
    result = invoke(kind)
    assert result["result"] == "APPLIED"
    assert len(provider.mutations) == 1
    assert modes == [RuntimeMode.MUTATION_ALLOWED, RuntimeMode.READBACK_ONLY]
    assert plans[0] != plans[1]
    assert race.committed.generation == 9
    assert result["readback_continuation"]["authority"] == "NON_AUTHORITY"


@pytest.mark.parametrize("kind", ["MERGE", "SYNC_TARGET", "FINALIZE"])
def test_changed_work_identity_cannot_turn_old_plan_into_continuation_authority(monkeypatch, kind):
    from tools.control_transaction_runtime import RuntimePostEffectConflict
    drift = replace(record(kind), generation=8, work_branch="work/foreign")
    current, provider, race = setup_race(monkeypatch, kind, drift=drift)
    with pytest.raises(RuntimePostEffectConflict): invoke(kind)
    assert len(provider.mutations) == 1 and len(race.writes) == 1


@pytest.mark.parametrize("observation", ["ABSENT", "PRESENT", "UNKNOWN"])
def test_stale_delete_drift_requires_fresh_exact_absence_and_never_deletes_again(monkeypatch, observation):
    from tools.control_transaction_runtime import RuntimePostEffectConflict
    drift = replace(record("RELEASE_PATHS"), generation=8)
    current, provider, race = setup_race(monkeypatch, "RELEASE_PATHS", drift=drift)
    original = race.load
    def load(*a):
        result = original(*a)
        if race.writes and observation == "PRESENT": provider.exists = True
        return result
    monkeypatch.setattr(executor, "_load_state", load)
    api = provider.api
    def uncertain(repo, method, path, token, payload=None):
        if race.writes and observation == "UNKNOWN" and method == "GET" and path == "/git/ref/heads/" + quote(WORK, safe=""):
            raise HTTPError(path, 503, "unknown", None, None)
        return api(repo, method, path, token, payload)
    monkeypatch.setattr(executor, "_api", uncertain)
    with pytest.raises(RuntimePostEffectConflict) as caught: invoke("RELEASE_PATHS")
    assert caught.value.diagnostics["work_ref_readback"] == observation
    assert caught.value.diagnostics["observed_generation"] == 8
    assert len(provider.mutations) == 1 and len(race.writes) == 1


@pytest.mark.parametrize("kind", ["MERGE", "SYNC_TARGET", "FINALIZE"])
def test_readback_continuation_fence_refuses_a_second_actual_mutation(monkeypatch, kind):
    from tools.control_transaction_runtime import RuntimePostEffectConflict
    drift = replace(record(kind), generation=8)
    current, provider, race = setup_race(monkeypatch, kind, drift=drift)
    original = race.load
    def load(*a):
        result = original(*a)
        if race.writes:
            provider.merged = kind == "FINALIZE"
            provider.closed = False
            provider.work_head = HEAD
        return result
    monkeypatch.setattr(executor, "_load_state", load)
    with pytest.raises(RuntimePostEffectConflict) as caught: invoke(kind)
    assert caught.value.conflict_class == "POST_EFFECT_READBACK_CONTINUATION_REJECTED"
    assert len(provider.mutations) == 1 and len(race.writes) == 1


@pytest.mark.parametrize("kind", sorted(PRE_TRANSITION_EXTERNAL_MUTATION_PATHS))
def test_exhausted_already_applied_path_never_mutates(monkeypatch, kind):
    from tools.control_transaction_runtime import RuntimePostEffectConflict
    current, provider, race = setup_race(monkeypatch, kind, readback=True, exhaust=True)
    with pytest.raises(RuntimePostEffectConflict): invoke(kind)
    assert provider.mutations == []
    assert len(race.writes) == 5


def test_ingress_marks_post_effect_conflict_nonretryable_without_secret_diagnostics(monkeypatch, tmp_path):
    from tools import control_transaction_request_ingress as ingress
    from tools.control_transaction_runtime import RuntimePostEffectConflict
    import json, sys
    monkeypatch.setenv("GITHUB_REPOSITORY", "looaeedr/whd")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setenv("GITHUB_REF_NAME", "coord/transaction-requests-work1")
    monkeypatch.setattr(ingress, "_load_request", lambda *a: {"request_id": "test"})
    monkeypatch.setattr(ingress, "_validate_request_branch", lambda **k: None)
    def reject(**k):
        raise RuntimePostEffectConflict("POST_EFFECT_SAME_ISSUE_DRIFT", {"issue": 1381, "pre_generation": 7, "observed_generation": 8})
    monkeypatch.setattr(ingress, "execute_request", reject)
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["ingress", "--request-file", str(tmp_path / "request.json"), "--output", str(output)])
    assert ingress.main() == 3
    result = json.loads(output.read_text())
    assert result["retryable"] is False
    assert result["retry_action"] == "FRESH_READ_READBACK_ONLY_OR_EXPLICIT_REPAIR"
    assert result["diagnostics"]["authority"] == "NON_AUTHORITY"
    assert result["provider_outcome_requires_readback"] is True
    assert "secret-token" not in output.read_text()


def test_unknown_provider_outcome_after_actual_mutation_is_nonretryable(monkeypatch):
    from tools.control_transaction_runtime import RuntimePostEffectConflict
    current, provider, race = setup_race(monkeypatch, "MERGE")
    api = provider.api
    def uncertain(repo, method, path, token, payload=None):
        result = api(repo, method, path, token, payload)
        if method == "PUT":
            raise semantic.ControlTransactionConflict("provider readback uncertain")
        return result
    monkeypatch.setattr(executor, "_api", uncertain)
    with pytest.raises(RuntimePostEffectConflict) as caught: invoke("MERGE")
    assert caught.value.conflict_class == "POST_EFFECT_PROVIDER_OUTCOME_UNPROVEN"
    assert caught.value.retryable is False
    assert len(provider.mutations) == 1 and race.writes == []
