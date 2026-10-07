from pathlib import Path

import pytest

from tools.execution_dispatch_ingress import (
    CANONICAL_DISPATCH_TRANSPORT,
    DispatchIngressError,
    DispatchIngressRequest,
    plan_dispatch_ingress,
    validate_dispatch_transport,
)


ROOT = Path(__file__).resolve().parents[2]


def _request(*, dispatch_transport: str = CANONICAL_DISPATCH_TRANSPORT) -> DispatchIngressRequest:
    return DispatchIngressRequest(
        issue=1389,
        execution_intent="EXECUTE_TICKET",
        authority_kind="USER_EXPLICIT",
        authority_ref="user:/派工 #1389",
        source_branch="cleanup/2d-3d-sync",
        source_sha="a" * 40,
        work_branch="work/issue-1389-dispatch-no-local",
        target_branch="cleanup/2d-3d-sync",
        target_sha="a" * 40,
        slot_id="worker.slot.1",
        created_at="2026-10-08T00:00:00+08:00",
        dispatch_transport=dispatch_transport,
    )


def test_dispatch_ready_accepts_only_github_canonical_transport():
    plan = plan_dispatch_ingress(_request())
    assert plan.record.state == "READY"
    assert plan.record.recovery_history[0]["dispatch_transport"] == "GITHUB_CANONICAL"


@pytest.mark.parametrize(
    "transport",
    [
        "REMOTE_DESKTOP_COMMANDER",
        "RC",
        "LOCAL_SHELL",
        "LOCAL_WORKSPACE",
        "LOCAL_REPO",
        "LOCAL_WORKTREE",
        "/workspace/whd",
    ],
)
def test_dispatch_ready_rejects_every_local_machine_transport(transport: str):
    with pytest.raises(DispatchIngressError, match="DISPATCH_LOCAL_MACHINE_FORBIDDEN"):
        plan_dispatch_ingress(_request(dispatch_transport=transport))


def test_noncanonical_transport_fails_closed_instead_of_falling_back():
    with pytest.raises(
        DispatchIngressError,
        match="DISPATCH_LOCAL_MACHINE_PROHIBITION_HARD_GATE_V1",
    ):
        validate_dispatch_transport("AUTO")


def test_dispatch_and_flow_skills_lock_takeover_as_the_only_rc_exception():
    dispatch_skill = (
        ROOT / ".agents/skills/engineering/派工/SKILL.md"
    ).read_text(encoding="utf-8")
    flow_skill = (
        ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
    ).read_text(encoding="utf-8")

    for text in (dispatch_skill, flow_skill):
        assert "DISPATCH_LOCAL_MACHINE_PROHIBITION_HARD_GATE_V1" in text
        assert "GITHUB_CANONICAL" in text
        assert "Remote Desktop Commander" in text
        assert "/workspace/whd" in text
        assert "/接手" in text

    assert "不得 fallback 到本機" in dispatch_skill
    assert "唯一 RC 例外" in dispatch_skill
    assert "implementation stage" in flow_skill
    assert "/派工 → 本機檢查/Preflight → GitHub READY" in flow_skill
