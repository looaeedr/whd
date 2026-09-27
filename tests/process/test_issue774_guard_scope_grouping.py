from __future__ import annotations
from datetime import datetime
from pathlib import Path

import tools.execution_claim_guard as guard

ISSUE=772
WORKER="chatgpt.issue772.20260927a"
BRANCH="trusted/issue772-deploy-guard-consume-hardening-20260927"
H="3"*40
BLOB="d"*40
CLAIM=f".dispatch/claims/issue-{ISSUE}.json"
CP=f".dispatch/checkpoints/issue-{ISSUE}.json"

def receipt(run_id: int, files, *, action="write"):
    return {
        "schema":"WHD_REMOTE_GUARD_RECEIPT_V1","result":"GREEN",
        "reason":"EXECUTION_CLAIM_GUARD_GREEN","request_comment_id":run_id+100,
        "run_id":run_id,"issue":ISSUE,"worker":WORKER,"executor_source":"chat",
        "action":action,"branch":BRANCH,"base_sha":"b"*40,"head_sha":H,
        "claim_blob_sha":BLOB,"guard_authority_sha":"a"*40,
        "tested_target_sha":H,"changed_files":list(files),
        "issued_at":"2026-09-26T22:50:00Z","expires_at":"2026-09-26T23:30:00Z",
    }

def classify(receipts, expected, *, expected_action="write"):
    return guard.classify_guard_transaction(
        receipts=receipts,current_issue=ISSUE,current_worker=WORKER,
        current_executor_source="chat",current_branch=BRANCH,
        current_claim_head_sha=H,live_branch_head_sha=H,
        current_claim_blob_sha=BLOB,
        now=datetime.fromisoformat("2026-09-26T23:00:00+00:00"),
        expected_changed_files=expected,
        expected_action=expected_action,
    )

def test_issue774_different_historical_scope_does_not_contaminate_current_pair():
    old_checkpoint=receipt(1,(CP,))
    current_pair=receipt(2,(CLAIM,CP))
    decision=classify([old_checkpoint,current_pair],(CLAIM,CP))
    assert decision.state is guard.GuardTransactionState.PENDING
    assert decision.guard_run_ids == (2,)

def test_issue774_checkpoint_scope_can_select_checkpoint_transaction():
    checkpoint=receipt(3,(CP,))
    pair=receipt(4,(CLAIM,CP))
    decision=classify([checkpoint,pair],(CP,))
    assert decision.state is guard.GuardTransactionState.PENDING
    assert decision.guard_run_ids == (3,)

def test_issue774_different_action_same_scope_does_not_contaminate_current_write():
    a=receipt(5,(CLAIM,CP),action="write")
    b=receipt(6,(CLAIM,CP),action="commit")
    decision=classify([a,b],(CLAIM,CP),expected_action="write")
    assert decision.state is guard.GuardTransactionState.PENDING
    assert decision.guard_run_ids == (5,)

def test_issue774_trusted_workflow_passes_current_changed_file_scope():
    text=(Path(__file__).resolve().parents[2]/".github/workflows/whd-remote-execution-guard.yml").read_text(encoding="utf-8")
    assert 'Path("/tmp/remote-guard-changed-files.txt")' in text
    assert "expected_changed_files=requested_changed_files" in text

def test_issue774_different_historical_action_does_not_contaminate_current_write():
    old_pr=receipt(7,(),action="pr-write")
    current_pair=receipt(8,(CLAIM,CP),action="write")
    decision=classify([old_pr,current_pair],(CLAIM,CP),expected_action="write")
    assert decision.state is guard.GuardTransactionState.PENDING
    assert decision.guard_run_ids == (8,)

def test_issue774_only_historical_other_action_allows_fresh_current_action():
    old_pr=receipt(9,(),action="pr-write")
    decision=classify([old_pr],(CLAIM,CP),expected_action="write")
    assert decision.state is guard.GuardTransactionState.NONE

def test_issue774_same_action_scope_mismatch_still_fails_closed():
    old_write=receipt(10,(CP,),action="write")
    decision=classify([old_write],(CLAIM,CP),expected_action="write")
    assert decision.state is guard.GuardTransactionState.AMBIGUOUS

def test_issue774_trusted_workflow_passes_current_action():
    text=(Path(__file__).resolve().parents[2]/".github/workflows/whd-remote-execution-guard.yml").read_text(encoding="utf-8")
    assert 'expected_action=os.environ["RG_ACTION"]' in text

def _readback(receipt, *, reconciled=True):
    return {
        "guard_run_id": receipt["run_id"],
        "request_comment_id": receipt["request_comment_id"],
        "action": receipt["action"],
        "branch": receipt["branch"],
        "head_sha": receipt["head_sha"],
        "tested_target_sha": receipt["tested_target_sha"],
        "changed_files": receipt["changed_files"],
        "coord_commit_sha": str(receipt["run_id"]).zfill(40)[-40:],
        "committed_at": "2026-09-26T23:55:00Z",
        "mutation_applied": True,
        "target_changed": True,
        "reconciled": reconciled,
    }

def test_issue774_consumed_same_action_different_scope_does_not_block_new_scope():
    old_a=receipt(11,(CP,),action="write")
    old_b=receipt(12,(CP,),action="write")
    decision=guard.classify_guard_transaction(
        receipts=[old_a,old_b],
        current_issue=ISSUE,current_worker=WORKER,current_executor_source="chat",
        current_branch=BRANCH,current_claim_head_sha=H,live_branch_head_sha=H,
        current_claim_blob_sha=BLOB,
        now=datetime.fromisoformat("2026-09-26T23:56:00+00:00"),
        durable_readbacks=[_readback(old_a),_readback(old_b)],
        expected_changed_files=(CLAIM,CP),
        expected_action="write",
    )
    assert decision.state is guard.GuardTransactionState.NONE

def test_issue774_unconsumed_same_action_different_scope_still_fails_closed():
    old=receipt(13,(CP,),action="write")
    decision=guard.classify_guard_transaction(
        receipts=[old],
        current_issue=ISSUE,current_worker=WORKER,current_executor_source="chat",
        current_branch=BRANCH,current_claim_head_sha=H,live_branch_head_sha=H,
        current_claim_blob_sha=BLOB,
        now=datetime.fromisoformat("2026-09-26T23:56:00+00:00"),
        durable_readbacks=[],
        expected_changed_files=(CLAIM,CP),
        expected_action="write",
    )
    assert decision.state is guard.GuardTransactionState.AMBIGUOUS
