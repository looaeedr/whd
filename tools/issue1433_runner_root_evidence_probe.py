"""Generate a non-user-local workspace receipt from real GitHub Actions checkout/tests.

Runs only AFTER the preceding trusted Actions test step succeeds, reads
the exact native coord record, and never mutates execution records or refs.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
from tools.execution_record import load_execution_record
from tools.execution_path_reservation import build_path_reservation_evidence
from tools.root_local_first_gate import (
    ENTRY_ROUTER_FRESH_READS, build_entry_router_evidence,
    build_remote_connection_authority, build_gate_evidence,
    build_git_unlock_receipt, validate_git_unlock_receipt,
)

ISSUE = 1433
EXPECTED_PR_HEAD = "35d1b19aef44a564fe6e3a6b313b18ed26c2ade8"
EXPECTED_BASE = "d30a81dbafeef0cebd534d4bc177e1bf2ef882dd"
EXACT_COMMANDS = ["python tools/control_plane_regression.py"]

def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("GITHUB_ACTIONS runtime required")
    root = Path.cwd().resolve()
    if root.name != "whd":
        raise SystemExit("Expected exact Runner whd checkout")
    # Read canonical entry documents in required order, from actual checkout.
    for path in ENTRY_ROUTER_FRESH_READS:
        if not (root / path).read_text(encoding="utf-8"):
            raise SystemExit(f"Empty entry contract: {path}")
    router = build_entry_router_evidence(fresh_reads=ENTRY_ROUTER_FRESH_READS, workspace_root=str(root))
    if git("rev-parse", "HEAD") != EXPECTED_PR_HEAD:
        raise SystemExit("Wrong PR HEAD in Runner checkout")
    live = git("ls-remote", "origin", "refs/heads/cleanup/2d-3d-sync").split()[0]
    if live != EXPECTED_BASE:
        raise SystemExit(f"Production target drifted: {live}")
    subprocess.run(["git","merge-base","--is-ancestor",EXPECTED_BASE,EXPECTED_PR_HEAD],check=True)
    diff = subprocess.check_output(["git","diff","--binary",EXPECTED_BASE,EXPECTED_PR_HEAD])
    digest = hashlib.sha256(diff).hexdigest()
    changed = sorted(git("diff","--name-only",EXPECTED_BASE,EXPECTED_PR_HEAD).splitlines())
    record_file = root.parent / "coord" / ".dispatch" / "execution" / f"issue-{ISSUE}.json"
    record = load_execution_record(record_file)
    if (record.issue != ISSUE or record.state != "ACTIVE"
        or record.owner_id != "chatgpt.flowv2.work1"
        or record.mutation_scope is None
        or record.mutation_scope.reservation_state != "ACTIVE"
        or record.mutation_scope.base_sha != EXPECTED_BASE):
        raise SystemExit("Native slot owner/reservation mismatch")
    reservation = build_path_reservation_evidence(record)
    if changed != sorted(reservation["write_paths"]) or reservation["delete_paths"]:
        raise SystemExit(f"Unreserved workspace diff: changed={changed!r}")
    test_receipt = {
        "schema": "WHD_TEST_EXECUTION_RECEIPT_V1",
        "status": "GREEN", "issue": ISSUE,
        "generation": record.generation,
        "source_sha": EXPECTED_BASE,
        "manifest_digest": digest,
        "exact_commands": EXACT_COMMANDS,
        "execution_location": "GITHUB_ACTIONS_RUNNER_WORKSPACE",
        "workflow_run_id": os.environ["GITHUB_RUN_ID"],
        "candidate_head_sha": EXPECTED_PR_HEAD,
    }
    authority = build_remote_connection_authority(
        kind="WORKSPACE_DELIVERY", target="GITHUB", user_explicit=True,
        allowed_actions=["CREATE_BRANCH", "COMMIT", "PUSH"],
    )
    # Chat-initiated execution on an independent GitHub Runner checkout.
    # Do not mislabel this as an RC or user-owned local workstation.
    evidence = build_gate_evidence(
        execution_mode="CHAT",
        repository_content_implementation=True,
        entry_router_evidence=router,
        source_evidence={"status":"EXACT_SOURCE_CURRENT","source_sha":EXPECTED_BASE},
        workspace_mutations_complete=True,
        workspace_tests_green=True,
        test_receipt=test_receipt,
        expected_test_commands=EXACT_COMMANDS,
        diff_digest=digest,
        workspace_delivery_authority=authority,
        path_reservation_evidence=reservation,
        target_drift=False,
    )
    if evidence.get("git_write_unlocked") is not True:
        raise SystemExit(f"WORKSPACE_EVIDENCE_NOT_UNLOCKED: {evidence.get('next_action')}")
    receipt = validate_git_unlock_receipt(build_git_unlock_receipt(evidence))
    bundle = {
        "schema":"WHD_GITHUB_ACTIONS_RUNNER_WORKSPACE_EVIDENCE_V1",
        "issue": ISSUE,
        "runner":"GITHUB_ACTIONS",
        "run_id":os.environ["GITHUB_RUN_ID"],
        "run_attempt":os.environ["GITHUB_RUN_ATTEMPT"],
        "source_sha":EXPECTED_BASE,
        "head_sha":EXPECTED_PR_HEAD,
        "changed_paths":changed,
        "exact_commands":EXACT_COMMANDS,
        "test_receipt":test_receipt,
        "root_evidence":evidence,
        "git_unlock_receipt":receipt,
        "native_record_generation":record.generation,
    }
    dest = Path(os.environ["RUNNER_TEMP"]) / "issue1433-root-evidence.json"
    dest.write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ROOT_EVIDENCE_GREEN issue=1433")
    print(f"source_sha={EXPECTED_BASE}")
    print(f"candidate_sha={EXPECTED_PR_HEAD}")
    print(f"manifest_sha256={digest}")
    print(f"native_generation={record.generation}")
    print(f"paths={len(changed)}")
    print(f"artifact={dest}")

if __name__ == "__main__":
    main()
