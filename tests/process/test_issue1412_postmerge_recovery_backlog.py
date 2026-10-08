"""#1412 post-merge recovery lane must drain terminal backlog without pivoting normal owners."""
from types import SimpleNamespace

from tools import control_transaction_production_executor as executor
from tools import production_x_post_merge_finalize as finalizer


LANE = "github.flowv2.postmerge"


def _record(issue, *, owner_kind="RECOVERY", lane=LANE, eligible=True, state="INTEGRATING"):
    return SimpleNamespace(
        issue=issue, owner_kind=owner_kind, owner_id=lane, lane_id=lane,
        state=state, execution_intent="POST_DELIVERY_RECOVERY" if eligible else "EXECUTE_TICKET",
        next_action=SimpleNamespace(kind="FINALIZE", args={"pr_number": issue + 1}),
        lease=SimpleNamespace(invocation_identity=f"prior-invocation:{issue}"),
        recovery_history=[{"schema": "WHD_FLOW_V2_POST_DELIVERY_RECOVERY_PROOF_V1"}],
    )


def test_sticky_exemption_only_for_two_verified_postmerge_finalizers(monkeypatch):
    monkeypatch.setattr(
        executor, "is_post_delivery_recovery_finalize_record",
        lambda x: x.execution_intent == "POST_DELIVERY_RECOVERY" and x.state == "INTEGRATING",
    )
    requested = _record(1412)
    blocked = _record(1397)
    assert executor._independent_post_delivery_finalizers(requested, blocked, kind="FINALIZE", lane_id=LANE)
    assert not executor._independent_post_delivery_finalizers(requested, blocked, kind="MERGE", lane_id=LANE)
    assert not executor._independent_post_delivery_finalizers(requested, _record(1397, eligible=False), kind="FINALIZE", lane_id=LANE)
    assert not executor._independent_post_delivery_finalizers(requested, _record(1397, lane="other-lane"), kind="FINALIZE", lane_id=LANE)


def test_backlog_drains_prior_closed_and_current_open_recovery_issues(monkeypatch):
    records = {1412: _record(1412), 1397: _record(1397), 1500: _record(1500, eligible=False)}
    calls = []
    monkeypatch.setattr(finalizer, "_load_state", lambda *_: ("c" * 40, "t" * 40, records))
    monkeypatch.setattr(finalizer, "is_post_delivery_recovery_finalize_record",
                        lambda r: r.execution_intent == "POST_DELIVERY_RECOVERY" and r.state == "INTEGRATING")
    monkeypatch.setattr(finalizer, "execute_one", lambda **kw: (
        calls.append(kw) or {"post_state": "DONE"}
    ))
    result = finalizer.drain_pending_post_delivery_finalizes(repo="looaeedr/whd", token="token")
    assert [r["issue"] for r in result] == [1397, 1412]
    assert all(r["status"] == "FINALIZED" for r in result)
    assert [x["invocation_identity"] for x in calls] == [
        "prior-invocation:1397", "prior-invocation:1412"
    ]
    assert all(x["kind"] == "FINALIZE" and x["lane_id"] == LANE for x in calls)


def test_backlog_fails_closed_without_exact_recovery_lease(monkeypatch):
    r = _record(1412)
    r.lease = None
    monkeypatch.setattr(finalizer, "_load_state", lambda *_: ("c" * 40, "t" * 40, {1412: r}))
    monkeypatch.setattr(finalizer, "is_post_delivery_recovery_finalize_record", lambda r: True)
    monkeypatch.setattr(finalizer, "execute_one", lambda **kw: (_ for _ in ()).throw(AssertionError("no mutation")))
    try:
        finalizer.drain_pending_post_delivery_finalizes(repo="looaeedr/whd", token="token")
    except finalizer.PostMergeFinalizeError as e:
        assert "lease" in str(e)
    else:
        raise AssertionError("must fail closed")
