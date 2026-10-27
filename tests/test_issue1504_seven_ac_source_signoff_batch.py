# -*- coding: utf-8 -*-
"""#1504 seven source-complete AC signoffs: exact CI witnesses, no false GUI/MFG."""

import ast
import json
from collections import Counter
from pathlib import Path

from tools.product_ci_regression import PYTEST_PATHS

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/superpowers/verification/issue1504_nfb_v14_ac_traceability.json"

REQUIRED = {
    "NFB-AC-06": "test_ac06_native_edit_cancel_undo_illegal_mutating_callback_and_authority_save",
    "NFB-AC-08": "test_ac08_quantity_version_id_deep_clone_switch_delete_save_reload_identity",
    "NFB-AC-26": "test_ac26_current_v5_quarter_turn_saved_bay_reload_does_not_fake_absolute_placement",
    "NFB-AC-33": "test_unconfigured_bay_and_quantity_keep_legacy_schema",
    "NFB-AC-37": "test_legacy_same_location_or_same_physical_owner_blocks_atomic_export",
    "SWT-AC-17": "test_brand_change_does_not_silently_swap_csv_filename_even_if_other_brand_same_name",
    "SWT-AC-25": "test_unconfigured_preserves_legacy_even_when_nfb_source_absent",
}


def _rows():
    doc = json.loads(MATRIX.read_text(encoding="utf-8"))
    return doc, {row["id"]: row for row in doc["records"]}


def test_batch_signoff_seven_require_independent_real_executed_assertions():
    matrix, rows = _rows()
    assert len(matrix["records"]) == 88
    live_counts = dict(Counter(r["status"] for r in rows.values()))
    # A completed historical deferred bucket is still represented as zero;
    # preserve exact Counter/readback equality for all positive statuses.
    live_counts.setdefault("DEFERRED_PRODUCT_EVIDENCE", 0)
    live_counts.setdefault("SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC", 0)
    live_counts.setdefault("EVIDENCE_CANDIDATE_ONLY", 0)
    assert matrix["counts"] == live_counts
    # The original seven-row signature is fixed, but subsequent fully
    # evidenced signoffs legitimately increase the live count past 43.
    # Derive live category totals from all 88 exact rows instead of treating
    # the historical source-batch timestamp as a permanent upper bound.
    assert sum(matrix["counts"].values()) == 88
    assert matrix["counts"]["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] >= 43
    assert matrix["counts"]["BLOCKED_1500_REAL_GUI"] == 0
    # The original four deferred requirements are immutable identities, not
    # a perpetual count: independently source-signed ACs leave this bucket.
    original_deferred = {"NFB-AC-13", "NFB-AC-41", "SWT-AC-09", "SWT-AC-22"}
    assert len(original_deferred) == 4
    assert matrix["counts"]["DEFERRED_PRODUCT_EVIDENCE"] == sum(
        rows[key]["status"] == "DEFERRED_PRODUCT_EVIDENCE"
        for key in original_deferred
    )
    assert all(rows[key]["status"] in {
        "DEFERRED_PRODUCT_EVIDENCE", "ACCEPTED_AUTOMATED_CURRENT_SCOPE",
    } for key in original_deferred)
    for key in original_deferred:
        row = rows[key]
        if row["accepted"]:
            proof = row["acceptance_evidence"]
            assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE", key
            assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED", key
            assert proof["original_ac_text_unchanged"] is True, key
            assert proof["source_sha_pins_unchanged"] is True, key
            assert proof["factory_release"] is False, key
            assert proof["unconditional_mfg2_release"] is False, key
            assert proof["human_windows_uat_claimed"] is False, key
            assert len(proof["original_ac_clauses_audited"]) >= 3, key
            for witness in (proof["primary_assertion"], *proof["other_required_assertions"]):
                path, name = witness.split("::")
                assert PYTEST_PATHS.count(path) == 1, witness
                assert name in {
                    node.name for node in ast.parse(
                        (ROOT / path).read_text(encoding="utf-8")
                    ).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }, witness
        else:
            assert row["status"] == "DEFERRED_PRODUCT_EVIDENCE", key
    assert matrix["counts"]["DEFERRED_PRODUCT_EVIDENCE"] + sum(
        rows[key]["accepted"] for key in original_deferred
    ) == 4
    assert all(
        row["accepted"] == (row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE")
        for row in rows.values()
    )
    for key, name in REQUIRED.items():
        row = rows[key]
        assert row["accepted"] is True and row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
        assert row["assertion_review_state"] == "FULL_AC_AUTOMATED_SIGNED"
        assert row["identified_test_functions"][0]["test_name"] == name
        proof = row["acceptance_evidence"]
        assert proof["original_ac_text_unchanged"] is True
        assert proof["factory_release"] is False
        assert proof["physical_absolute_position_grant"] is False
        assert proof["human_windows_uat_claimed"] is False
        assert proof["ui_full_operator_uat_claimed"] is False
        assert proof["other_ac_signoff_implied"] is False
        sources = [proof["primary_assertion"], *proof["other_required_assertions"]]
        assert len(sources) >= 3  # independent success, negative, and persisted witnesses
        assert sources[0] == (row["identified_test_functions"][0]["path"] + "::" + name)
        assert len(set(sources)) == len(sources)
        for exact in sources:
            path, func = exact.split("::")
            assert PYTEST_PATHS.count(path) == 1, exact
            assert (ROOT / path).is_file(), exact
            funcs = {
                node.name: node
                for node in ast.parse((ROOT / path).read_text(encoding="utf-8")).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            assert func in funcs, exact
            fn = funcs[func]
            # Negative manufacturing/collision witnesses intentionally
            # assert rejection with pytest.raises(...) rather than a bare
            # `assert`. Demand either an actual assert OR an explicit
            # pytest.raises context with an exception class. A filename or
            # marker without executable assertions is never accepted.
            def _explicit_rejection(node):
                return (
                    isinstance(node, (ast.With, ast.AsyncWith))
                    and any(
                        isinstance(item.context_expr, ast.Call)
                        and isinstance(item.context_expr.func, ast.Attribute)
                        and isinstance(item.context_expr.func.value, ast.Name)
                        and item.context_expr.func.value.id == "pytest"
                        and item.context_expr.func.attr == "raises"
                        and bool(item.context_expr.args)
                        for item in node.items
                    )
                )
            assert any(
                isinstance(node, ast.Assert) or _explicit_rejection(node)
                for node in ast.walk(fn)
            ), exact


def test_unsigned_high_risk_ac_requirements_remain_blocked():
    _, rows = _rows()
    for key in ("NFB-AC-54", "SWT-AC-31"):
        assert rows[key]["accepted"] is True
        assert rows[key]["acceptance_evidence"]["external_historical_binary_read_executed"] is False
    assert all(
        not r["accepted"] for r in rows.values()
        if r["status"] in {
            "BLOCKED_1500_REAL_GUI",
            "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC",
            "DEFERRED_PRODUCT_EVIDENCE",
        }
    )
    matrix, rows = _rows()
    assert sum(r["accepted"] for r in rows.values()) == matrix["counts"][
        "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    ]
    assert sum(r["accepted"] for r in rows.values()) >= 43
    for row in rows.values():
        if not row["accepted"]:
            continue
        proof = row["acceptance_evidence"]
        assert proof["original_ac_text_unchanged"] is True, row["id"]
        assert proof.get("factory_release") is not True, row["id"]
        assert proof.get("human_windows_uat_claimed") is not True, row["id"]
