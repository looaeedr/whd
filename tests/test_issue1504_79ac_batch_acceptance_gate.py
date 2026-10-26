# -*- coding: utf-8 -*-
"""One-shot #1504 audit: the *original* 79 unsigned ACs, not 79 new test runs.

The manifest and audit must remain true after adding source-scoped signoffs.
Do not mistake a selected primary witness for a complete GUI/MFG acceptance.
"""
import ast
import json
from pathlib import Path

from tools.product_ci_regression import PYTEST_PATHS

ROOT=Path(__file__).resolve().parents[1]
VERIFY=ROOT/"docs"/"superpowers"/"verification"
AUDIT=VERIFY/"issue1504_79_pending_ac_batch_source_audit.json"
MATRIX=VERIFY/"issue1504_nfb_v14_ac_traceability.json"
BATCH={"NFB-AC-48","NFB-AC-49","NFB-AC-50","SWT-AC-28"}
FOLLOWUP={"NFB-AC-06","NFB-AC-08","NFB-AC-26","NFB-AC-33","NFB-AC-37","SWT-AC-17","SWT-AC-25","NFB-AC-04","NFB-AC-19","NFB-AC-05","NFB-AC-27","SWT-AC-06","NFB-AC-54","SWT-AC-31","NFB-AC-29","SWT-AC-19","NFB-AC-01","SWT-AC-01","NFB-AC-47","NFB-AC-09","NFB-AC-24","NFB-AC-21","SWT-AC-14","NFB-AC-20","SWT-AC-13","NFB-AC-32","NFB-AC-18","NFB-AC-03","NFB-AC-15","SWT-AC-05"}
BASELINE_GROUPS={
    "EVIDENCE_CANDIDATE_ONLY":44,
    "BLOCKED_1500_REAL_GUI":17,
    "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC":14,
    "DEFERRED_PRODUCT_EVIDENCE":4,
}
AFTER_GROUPS={
    "EVIDENCE_CANDIDATE_ONLY":10,
    "BLOCKED_1500_REAL_GUI":17,
    "ACCEPTED_AUTOMATED_CURRENT_SCOPE":43,
    "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC":14,
    "DEFERRED_PRODUCT_EVIDENCE":4,
}

def _json(p):
    return json.loads(p.read_text(encoding="utf-8"))

def test_all_79_pre_batch_unsignatures_reconciled_to_one_canonical_witness():
    audit,matrix=_json(AUDIT),_json(MATRIX)
    rows={r["id"]:r for r in matrix["records"]}
    entries=audit["entries"]
    assert audit["invariant_total_ac"]==len(rows)==88
    assert audit["already_signed_before_batch"]==9
    assert audit["source_pending_before_batch"]==len(entries)==79
    assert len({e["id"] for e in entries})==79
    assert audit["batch_signed_candidate_ids"]==sorted(BATCH)
    # This audit is an immutable snapshot of the 79 unsigned ACs when
    # the batch started. Later evidence-backed signoffs do not remove IDs
    # from that historical snapshot or require a continually edited allowlist.
    historical_unsigned={e["id"] for e in entries}
    assert historical_unsigned.issubset(rows)
    assert len(set(rows)-historical_unsigned)==audit["already_signed_before_batch"]==9
    assert sum(len(v) for v in audit["grouped_ids"].values())==79
    assert {k:len(v) for k,v in audit["grouped_ids"].items()}==BASELINE_GROUPS
    live_counts={status:sum(row["status"]==status for row in rows.values())
                 for status in AFTER_GROUPS}
    assert matrix["counts"]==live_counts
    assert sum(live_counts.values())==sum(AFTER_GROUPS.values())==88
    assert live_counts["ACCEPTED_AUTOMATED_CURRENT_SCOPE"]>=AFTER_GROUPS[
        "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    ]
    assert 0 < live_counts["BLOCKED_1500_REAL_GUI"] <= BASELINE_GROUPS["BLOCKED_1500_REAL_GUI"]
    # Historical 79-AC baseline retains four deferred IDs; later exact-AC
    # runtime signoffs may retire individual items, never silently erase them.
    historical_deferred=set(audit["grouped_ids"]["DEFERRED_PRODUCT_EVIDENCE"])
    live_deferred={k for k in historical_deferred
                   if rows[k]["status"]=="DEFERRED_PRODUCT_EVIDENCE"}
    newly_signed=historical_deferred-live_deferred
    assert len(historical_deferred)==BASELINE_GROUPS["DEFERRED_PRODUCT_EVIDENCE"]==4
    assert len(live_deferred)+len(newly_signed)==4
    for key in newly_signed:
        row=rows[key]
        assert row["accepted"] is True, key
        assert row["status"]=="ACCEPTED_AUTOMATED_CURRENT_SCOPE", key
        assert row["evidence_level"]=="FULL_AC_ASSERTION_AUDITED", key
        proof=row["acceptance_evidence"]
        assert proof["original_ac_text_unchanged"] is True, key
        assert proof["factory_release"] is False, key
        assert proof["unconditional_mfg2_release"] is False, key
        assert proof["human_windows_uat_claimed"] is False, key
        assert len(proof["original_ac_clauses_audited"])>=3, key
        assert len(proof["other_required_assertions"])>=2, key
        for ref in (proof["primary_assertion"], *proof["other_required_assertions"]):
            path,name=ref.split("::")
            assert path in PYTEST_PATHS, ref
            body=ast.parse((ROOT/path).read_text(encoding="utf-8")).body
            assert name in {n.name for n in body if isinstance(n,
                         (ast.FunctionDef,ast.AsyncFunctionDef))}, ref
    assert len({e["primary_witness"]["file"] for e in entries})==23
    assert audit["primary_file_selected_count"]==79
    assert "DOES_NOT_IMPLY_FULL_AC" in audit["signoff_boundary"]

    for entry in entries:
        key=entry["id"]
        row=rows[key]
        assert entry["requirements_original_unchanged"]
        assert row["requirement"]  # original requirement remains intact
        witness=entry["primary_witness"]
        assert witness["full_ac_proven"] is False  # baseline, not retroactive signoff
        assert witness["source_is_in_canonical_pr_ci"]
        assert PYTEST_PATHS.count(witness["file"])==1, key
        path=ROOT/witness["file"]
        assert path.is_file(), key
        body=ast.parse(path.read_text(encoding="utf-8")).body
        tests={n.name:n for n in body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        assert witness["function"] in tests, key
        fn=tests[witness["function"]]
        assert any(isinstance(n,(ast.Assert,ast.With,ast.For,ast.If))
                   for n in ast.walk(fn)), key
        if key in BATCH:
            assert row["accepted"] is True
            assert entry["signed_by_current_batch_candidate"] is True
        elif key in FOLLOWUP:
            # The 79-AC audit is an immutable snapshot of the earlier state;
            # later directly witnessed signoffs do not alter that history.
            assert row["accepted"] is True
            assert entry["signed_by_current_batch_candidate"] is False
            assert entry["previous_status"] == "EVIDENCE_CANDIDATE_ONLY"
            assert row["acceptance_evidence"]["original_ac_text_unchanged"] is True
        else:
            assert entry["signed_by_current_batch_candidate"] is False
            assert entry["unverified_scope"], key
            if row["accepted"]:
                # A later source-scoped signoff must be independently audited
                # and must not silently grant factory/Windows/UAT authority.
                assert entry["previous_status"] in {
                    "EVIDENCE_CANDIDATE_ONLY",
                    "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC",
                    "DEFERRED_PRODUCT_EVIDENCE",  # Only after witnessed scope audit above.
                    "BLOCKED_1500_REAL_GUI",  # User cancelled A+B, not functional evidence.
                }, key
                if entry["previous_status"] == "BLOCKED_1500_REAL_GUI":
                    # Require an independently auditable real native GUI test.
                    proof = row["acceptance_evidence"]
                    assert row["historical_pre_current_review"]["status"] == "BLOCKED_1500_REAL_GUI", key
                    assert proof["user_cancelled_second_legacy_project_prerequisite"] is True, key
                    assert len(proof["requirement_witnesses"]) >= 2, key
                    filename, fn = proof["primary_assertion"].split("::")
                    assert filename in PYTEST_PATHS, key
                    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
                    assert any(isinstance(n, ast.FunctionDef) and n.name == fn
                               and any(isinstance(c, ast.Assert) for c in ast.walk(n))
                               for n in tree.body), key
                assert row["status"]=="ACCEPTED_AUTOMATED_CURRENT_SCOPE", key
                assert row["evidence_level"]=="FULL_AC_ASSERTION_AUDITED", key
                assert row["assertion_review_state"]=="FULL_AC_AUTOMATED_SIGNED", key
                evidence=row["acceptance_evidence"]
                assert evidence["original_ac_text_unchanged"] is True, key
                assert evidence.get("factory_release") is False, key
                assert evidence.get("human_windows_uat_claimed") is False, key
                assert evidence.get("integrated_localx_claimed") is False, key
            else:
                assert entry["previous_status"]==row["status"], key

def test_four_source_signoffs_require_real_exact_primary_and_negative_tests():
    rows={r["id"]:r for r in _json(MATRIX)["records"]}
    for key in BATCH:
        row=rows[key]
        assert row["accepted"] is True
        assert row["status"]=="ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        proof=row["acceptance_evidence"]
        assert proof["original_ac_text_unchanged"] is True
        assert proof["factory_release"] is False
        assert proof["physical_absolute_position_grant"] is False
        assert proof["human_windows_uat_claimed"] is False
        assert proof["ui_full_operator_uat_claimed"] is False
        refs=[proof["primary_assertion"],*proof["other_required_assertions"]]
        assert len(refs)>=2
        assert refs[0].split("::")[1]==row["identified_test_functions"][0]["test_name"]
        for item in refs:
            path,name=item.split("::")
            assert PYTEST_PATHS.count(path)==1, item
            funcs={n.name:n for n in ast.parse(
                (ROOT/path).read_text(encoding="utf-8")
            ).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
            assert name in funcs, item
            assert any(isinstance(n,(ast.Assert,ast.With,ast.For,ast.If))
                       for n in ast.walk(funcs[name])), item
    for key in ("NFB-AC-54","SWT-AC-31"):
        row=rows[key]
        assert row["accepted"] is True
        assert row["acceptance_evidence"]["external_historical_binary_read_executed"] is False
    live_blocked = sum(r["status"]=="BLOCKED_1500_REAL_GUI" for r in rows.values())
    assert live_blocked == _json(MATRIX)["counts"]["BLOCKED_1500_REAL_GUI"]
    assert 0 < live_blocked <= BASELINE_GROUPS["BLOCKED_1500_REAL_GUI"]
    # Do not confuse the immutable four-item *historical* snapshot with
    # current evidence-backed per-AC signoffs. Every retired deferred AC
    # must satisfy the full runtime/source clauses audited above.
    historical=set(_json(AUDIT)["grouped_ids"]["DEFERRED_PRODUCT_EVIDENCE"])
    assert len(historical)==4
    assert all(rows[key]["status"] in (
        "DEFERRED_PRODUCT_EVIDENCE", "ACCEPTED_AUTOMATED_CURRENT_SCOPE",
    ) for key in historical)
    assert sum(rows[key]["status"]=="DEFERRED_PRODUCT_EVIDENCE"
               for key in historical)+sum(rows[key]["accepted"]
               for key in historical)==4
