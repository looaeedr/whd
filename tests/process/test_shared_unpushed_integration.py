import pytest

from tools.shared_unpushed_integration import (
    CONFLICT_CHECKPOINT_SCHEMA,
    CONFLICT_STATE,
    LANE_EVIDENCE_SCHEMA,
    UnpushedIntegrationError,
    assert_conflict_checkpoint_blocks_action,
    assert_push_scope,
    assert_worker_base_is_latest,
    build_conflict_checkpoint,
    build_lane_evidence,
    classify_lane,
    next_generation,
    validate_lane_evidence,
)


def test_governance_and_skills_are_docs_but_product_required_docs_are_body():
    assert classify_lane(path=".agents/skills/x/SKILL.md", ownership="skill") == "docs"
    assert classify_lane(path="AGENTS.md", ownership="agents") == "docs"
    assert classify_lane(path="docs/specs/product_contract.md", ownership="human_doc", product_required=True) == "body"


def test_later_worker_must_start_from_latest_zero_generation():
    with pytest.raises(UnpushedIntegrationError, match="STALE_0_BASE"):
        assert_worker_base_is_latest(base_generation=3, latest_generation=4)
    assert_worker_base_is_latest(base_generation=4, latest_generation=4)


def test_merge_conflict_creates_user_decision_checkpoint_and_blocks_automation():
    cp = build_conflict_checkpoint(
        lane="body",
        path="ae_engine/example.py",
        base_generation=4,
        latest_generation=5,
        base_hash="base",
        latest_hash="latest",
        worker_hash="worker",
        conflict_hunks=["@@ -10,3 +10,3 @@ both changed same semantic block"],
        worker="work1",
        issue="#1200",
    )
    assert cp["schema"] == CONFLICT_CHECKPOINT_SCHEMA
    assert cp["state"] == CONFLICT_STATE
    assert cp["requires"] == "EXPLICIT_USER_CONFLICT_DECISION"
    assert "AUTO_OURS" in cp["forbidden"]
    assert "AUTO_THEIRS" in cp["forbidden"]
    assert "RUN_PUSH" in cp["forbidden"]

    for action in ("MERGE_TO_0", "ADVANCE_GENERATION", "RUN_PUSH", "CREATE_DELIVERY_BRANCH"):
        with pytest.raises(UnpushedIntegrationError, match="BLOCKED_USER_DECISION"):
            assert_conflict_checkpoint_blocks_action(cp, action=action)

    assert_conflict_checkpoint_blocks_action(
        cp, action="MERGE_TO_0", user_decision="use worker hunk for lines 10-12"
    )


def test_conflict_never_advances_generation_automatically():
    with pytest.raises(UnpushedIntegrationError, match="MERGE_CONFLICT_BLOCKS_GENERATION_ADVANCE"):
        next_generation(latest_generation=9, has_conflict=True)
    assert next_generation(latest_generation=9, has_conflict=False) == 10


def test_push_scope_must_equal_selected_lane_manifest():
    assert_push_scope(
        selected_lane="docs",
        manifest_paths=["AGENTS.md", ".agents/skills/x/SKILL.md"],
        staged_paths=[".agents/skills/x/SKILL.md", "AGENTS.md"],
    )
    with pytest.raises(UnpushedIntegrationError, match="PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_MANIFEST"):
        assert_push_scope(
            selected_lane="docs",
            manifest_paths=["AGENTS.md"],
            staged_paths=["AGENTS.md", "ae_engine/example.py"],
        )


def test_lane_evidence_binds_lane_issue_source_generation_and_manifest_scope():
    evidence = build_lane_evidence(
        lane="docs", issue=1200, source_sha="a" * 40,
        target_branch="main", generation=7,
        write_paths=["AGENTS.md", ".agents/skills/engineering/推推/SKILL.md"],
        manifest_digest="b" * 64, state="FROZEN",
    )
    assert evidence["schema"] == LANE_EVIDENCE_SCHEMA
    assert evidence["lane"] == "docs"
    assert evidence["generation"] == 7
    assert validate_lane_evidence(evidence) == evidence

    bad = dict(evidence, write_paths=["AGENTS.md"], delete_paths=["AGENTS.md"])
    with pytest.raises(UnpushedIntegrationError, match="write/delete overlap"):
        validate_lane_evidence(bad)
