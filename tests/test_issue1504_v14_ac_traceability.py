# -*- coding: utf-8 -*-
"""#1504 fail-closed machine audit of the two approved NFB v1.4 AC tables.

A test filename is NOT proof that an AC passed. Some independent automated
ACs may be signed only with actual multi-assertion runtime tests in mandatory
CI, while #1500 real-source GUI and full-cabinet manufacturing remain unsigned;
#1503 PART-ONLY has already closed.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/superpowers/verification/issue1504_nfb_v14_ac_traceability.json"
SCHEMA = "WHD_NFB_V14_88AC_TRACEABILITY_V1"
NEEDS = {
    "EVIDENCE_CANDIDATE_ONLY",
    "BLOCKED_1500_REAL_GUI",
    "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC",
    "DEFERRED_PRODUCT_EVIDENCE",
    "ACCEPTED_AUTOMATED_CURRENT_SCOPE",
}
ORIGINAL_SHA = {
    "WHD_受電箱_NFB_UI與開孔編輯整合規格_20261010_v1.4.md":
        "2fcf48521b913435b01639b9fa1b3ef7789ec93724033e332cedd4c85e1d0eef",
    "WHD_受電箱_開關層數_耳朵打標與內門開孔_規格書_20261010_v1.4.md":
        "f4441937f43bf70de1224cf74926b8cfe031dc6eef6f18f165bd6bf6a8a2e5e1",
}


def _data():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_exact_original_v14_ac_text_is_not_rewritten_by_trace_owners():
    rows = _data()["records"]
    canonical = "\n".join(
        "|".join((r["id"], r["requirement"], r["phase"])) for r in rows
    )
    # Digest produced from the exact two approved source docs' §7 tables,
    # not from issues, speculative machine geometries, or a newer summary.
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == (
        "46612c4295d0ee86e6f3f8e9b833b0bc50e928938ac2305789debf3b6c4addc2"
    )


def test_approved_v14_has_all_88_unique_original_acceptance_ids():
    obj = _data()
    assert obj["schema"] == SCHEMA
    rows = obj["records"]
    assert len(rows) == 88
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == 88
    assert set(ids) == {
        *(f"NFB-AC-{n:02d}" for n in range(1, 57)),
        *(f"SWT-AC-{n:02d}" for n in range(1, 33)),
    }
    assert all(r["requirement"] and r["phase"] and r["source"] for r in rows)
    assert all(len(r["requirement"]) >= 12 for r in rows)


def test_original_two_spec_sha_and_no_secondary_ac_authority():
    obj = _data()
    assert {d["name"]: d["sha256"] for d in obj["source_documents"]} == ORIGINAL_SHA
    assert obj["authority_note"].startswith("Source AC original wording.")
    assert obj["review_status"] == "INCOMPLETE_DO_NOT_CLOSE_1504_OR_1490"
    assert obj["formal_release_requires"] == "/推推"


def test_all_owner_and_candidate_paths_exist_without_claiming_tests_prove_ac():
    for row in _data()["records"]:
        assert row["owning_issues"], row["id"]
        assert all(type(x) is int and 1491 <= x <= 1504
                   for x in row["owning_issues"]), row["id"]
        candidates = row["regression_candidates"]
        assert candidates, row["id"]
        assert len(candidates) == len(set(candidates)), row["id"]
        assert all(re.fullmatch(r"tests/[a-zA-Z0-9_/-]+\.py", p)
                   for p in candidates), row["id"]
        assert all((ROOT / p).is_file() for p in candidates), row["id"]
        assert row["status"] in NEEDS
        if row["accepted"]:
            assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
            assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
            assert row["assertion_review_state"] == "FULL_AC_AUTOMATED_SIGNED"
            assert row["acceptance_evidence"]["factory_release"] is False
            assert row["acceptance_evidence"]["human_windows_uat_claimed"] is False
        else:
            assert row["evidence_level"] == "PATH_EXISTS_NOT_ASSERTION_AUDITED"
            assert row["status"] not in ("PASS", "GREEN", "CLOSED", "READY")


def test_open_real_gui_physical_and_deferred_work_never_marked_pass():
    data = _data()
    assert set(data["open_gates"]) == {1500, 1504}
    rows = {r["id"]: r for r in data["records"]}
    assert rows["NFB-AC-34"]["status"] == "BLOCKED_1500_REAL_GUI"
    assert rows["NFB-AC-14"]["status"] == "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC"
    assert rows["NFB-AC-13"]["status"] == "DEFERRED_PRODUCT_EVIDENCE"
    assert rows["SWT-AC-12"]["owning_issues"] == [1504]
    for r in rows.values():
        if r["status"] == "BLOCKED_1500_REAL_GUI":
            assert r["blocking_issues"] == [1500]
        elif r["status"] == "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC":
            assert r["blocking_issues"] == []
            assert 1502 in r["owning_issues"]
            assert r["current_delivery_scope"] == (
                "GITHUB_LOCALX_1502_SCOPED_PRODUCT_CI_GREEN_FULL_AC_NOT_YET_SIGNED"
            )
        elif r["status"] == "DEFERRED_PRODUCT_EVIDENCE":
            assert r["blocking_issues"] == []
            assert r["post_1503_close_scope"] == (
                "CLOSED_1503_PART_ONLY_DELIVERED__FULL_CABINET_OR_HISTORICAL_AC_NOT_YET_SIGNED"
            )
            assert r["accepted"] is False
        else:
            assert not r["blocking_issues"]
    assert {r["id"] for r in rows.values() if r["accepted"]} == {"NFB-AC-30", "NFB-AC-17", "SWT-AC-04", "NFB-AC-10", "SWT-AC-02", "NFB-AC-25", "NFB-AC-22", "SWT-AC-15", "SWT-AC-03", "NFB-AC-48", "NFB-AC-49", "NFB-AC-50", "SWT-AC-28", "NFB-AC-06", "NFB-AC-08", "NFB-AC-26", "NFB-AC-33", "NFB-AC-37", "SWT-AC-17", "SWT-AC-25", "NFB-AC-04", "NFB-AC-19", "NFB-AC-05", "NFB-AC-27", "SWT-AC-06", "NFB-AC-54", "SWT-AC-31" , "NFB-AC-29", "SWT-AC-19"}
    assert rows["NFB-AC-30"]["blocking_issues"] == []


def test_1502_newer_corrected_base_plate_scope_is_not_lost():
    obj = _data()
    assert obj["latest_product_scope"]["authority_issue"] == 1502
    for row in obj["records"]:
        if "current_scope_correction" in row:
            assert 1502 in row["owning_issues"]
            assert row["current_scope_correction"]["issue"] == 1502
            assert row["accepted"] is False


def test_manifest_review_summary_is_recomputed_from_records():
    obj = _data()
    counts = dict(Counter(r["status"] for r in obj["records"]))
    assert sum(counts.values()) == 88
    assert obj["counts"] == counts
    assert counts["DEFERRED_PRODUCT_EVIDENCE"] >= 3
    assert counts["BLOCKED_1500_REAL_GUI"] >= 1
    assert counts["SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC"] == 14
    assert counts["BLOCKED_1500_REAL_GUI"] == 17
    assert counts["EVIDENCE_CANDIDATE_ONLY"] == 24
    assert counts["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] == 29


def test_exact_function_witnesses_are_owner_aligned_real_definitions_not_pass_flags():
    data = _data()
    assert data["exact_test_function_witnesses_count"] == 88
    assert data["assertion_witness_note"]
    found = 0
    for item in data["records"]:
        witnesses = item["identified_test_functions"]
        state = item["assertion_review_state"]
        assert witnesses, item["id"]
        assert state == (
            "FULL_AC_AUTOMATED_SIGNED" if item["accepted"]
            else "TEST_FUNCTION_IDENTITY_VERIFIED_NOT_FULL_AC"
        )
        assert len(witnesses) == 1  # one primary per AC, not fake row counts
        for witness in witnesses:
            assert witness["path"] in item["regression_candidates"]
            assert witness["accepted"] is item["accepted"]
            assert witness["witness_scope"] == (
                "FULL_AC_AUTOMATED_ASSERTIONS" if item["accepted"]
                else "PARTIAL_AUTOMATED_ASSERTIONS_ONLY"
            )
            target = ROOT / witness["path"]
            nodes = ast.parse(target.read_text(encoding="utf-8")).body
            actual = {n.name for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            assert witness["test_name"] in actual, item["id"]
            found += 1
    assert found == 88


def test_w800_datum_old_hole_undo_and_schema_have_real_named_witnesses():
    row = {r["id"]: r for r in _data()["records"]}
    assert "x" in row["NFB-AC-49"]["identified_test_functions"][0]["test_name"]
    assert "y" in row["NFB-AC-50"]["identified_test_functions"][0]["test_name"]
    assert "legacy" in row["NFB-AC-37"]["identified_test_functions"][0]["test_name"]
    assert "undo" in row["NFB-AC-35"]["identified_test_functions"][0]["test_name"]
    assert "schema" in row["NFB-AC-54"]["identified_test_functions"][0]["test_name"]
    assert not row["NFB-AC-35"]["accepted"]



def test_one_full_ac_requires_source_specific_runtime_witness_and_ci_selection():
    obj = _data()
    assert obj["exact_test_function_witnesses_review"].startswith(
        "88/88 FUNCTION_IDENTITIES_VERIFIED; 29/88 FULL_AC_AUTOMATED_SIGNED"
    )
    signed = {r["id"]: r for r in obj["records"] if r["accepted"]}
    assert set(signed) == {"NFB-AC-30", "NFB-AC-17", "SWT-AC-04", "NFB-AC-10", "SWT-AC-02", "NFB-AC-25", "NFB-AC-22", "SWT-AC-15", "SWT-AC-03", "NFB-AC-48", "NFB-AC-49", "NFB-AC-50", "SWT-AC-28", "NFB-AC-06", "NFB-AC-08", "NFB-AC-26", "NFB-AC-33", "NFB-AC-37", "SWT-AC-17", "SWT-AC-25", "NFB-AC-04", "NFB-AC-19", "NFB-AC-05", "NFB-AC-27", "SWT-AC-06", "NFB-AC-54", "SWT-AC-31" , "NFB-AC-29", "SWT-AC-19"}
    from tools.product_ci_regression import PYTEST_PATHS
    # Do not accept a filename or an unrelated witness.  Exact path, native
    # numeric CSV fail-closed and old source-scoped MFG1 preflight are mandatory.
    a = signed["NFB-AC-30"]
    e = a["acceptance_evidence"]
    proof = "tests/test_issue1504_ac30_current_nominal_no_fake_cutting.py"
    assert e["original_ac_text_unchanged"] is True
    assert proof in PYTEST_PATHS
    assert e["primary_assertion"] == (
        proof+"::test_nfb_ac30_nominal_spacing_survives_missing_model_without_fake_cutting"
    )
    assert e["other_required_assertion"] == (
        proof+"::test_nfb_ac30_missing_numeric_csv_model_produces_no_physical_cutting"
    )
    assert e["separate_mfg1_preflight"] == (
        "tests/test_issue1497_nfb_cutting_preflight.py"
        "::test_unresolved_x_never_generates_a_fake_center_or_manufacturable_hole"
    )
    assert "tests/test_issue1497_nfb_cutting_preflight.py" in PYTEST_PATHS
    for entry in (e["primary_assertion"], e["other_required_assertion"],
                  e["separate_mfg1_preflight"]):
        filename, function = entry.split("::")
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        matches = [n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == function]
        assert len(matches) == 1
        assert any(isinstance(n, ast.Assert) for n in ast.walk(matches[0]))
    assert e["factory_release"] is False
    assert e["human_windows_uat_claimed"] is False
    assert set(obj["open_gates"]) == {1500, 1504}


def test_current_receiving_baseplate_x_datum_supersedes_old_nfb_centroid_rule():
    """#1490 owner check: later approved shop datum must win over old AC gloss."""
    obj = _data()
    scope = obj["latest_product_scope"]
    rule = scope["rule"]
    assert scope["authority_issue"] == 1502
    assert "PR #1909" in rule and "cabinet X=0" in rule
    assert "X=-335/+335 (670 mm)" in rule
    assert "X=-398/+398" in rule
    assert "ONLY the source-verified NFB screw holes move" in rule
    assert "Y=470/-30" in rule
    assert "732-mm" in rule and "Do not infer plate X" in rule
    assert "remain unapproved" in rule
    assert obj["review_status"] == "INCOMPLETE_DO_NOT_CLOSE_1504_OR_1490"
    assert {r["id"] for r in obj["records"] if r["accepted"]} == {"NFB-AC-30", "NFB-AC-17", "SWT-AC-04", "NFB-AC-10", "SWT-AC-02", "NFB-AC-25", "NFB-AC-22", "SWT-AC-15", "SWT-AC-03", "NFB-AC-48", "NFB-AC-49", "NFB-AC-50", "SWT-AC-28", "NFB-AC-06", "NFB-AC-08", "NFB-AC-26", "NFB-AC-33", "NFB-AC-37", "SWT-AC-17", "SWT-AC-25", "NFB-AC-04", "NFB-AC-19", "NFB-AC-05", "NFB-AC-27", "SWT-AC-06", "NFB-AC-54", "SWT-AC-31" , "NFB-AC-29", "SWT-AC-19"}

    # The human review must not silently retain an older X-centering claim.
    text = MANIFEST.with_suffix(".md").read_text(encoding="utf-8")
    assert "箱體中心 X=0" in text
    assert "**孔距 670 mm**" in text
    assert "T2/BEND23" in text and "EAR 已不是全部未驗" in text


def test_closed_1502_is_not_an_open_gate_and_original_ac_claims_stay_unsigned():
    """Closed localX scope cannot be counted as an open blocker or as 88 passes."""
    d = _data()
    assert d["assessed_on"] == "2026-10-22"
    assert 1502 not in d["open_gates"]
    assert 1503 not in d["open_gates"]
    assert d["counts"] == {
        "BLOCKED_1500_REAL_GUI": 17,
        "DEFERRED_PRODUCT_EVIDENCE": 4,
        "EVIDENCE_CANDIDATE_ONLY": 24,
        "ACCEPTED_AUTOMATED_CURRENT_SCOPE": 29,
        "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC": 14,
    }
    scoped = tuple(r for r in d["records"] if r["status"].startswith(
        "SCOPED_LOCALX_1502_"
    ))
    assert len(scoped) == 14
    assert all(1502 in r["owning_issues"]
               and not r["blocking_issues"]
               and "PR #2037" in r["delivery_receipt"]
               and not r["accepted"] for r in scoped)
    assert {r["id"]: r for r in d["records"]}["SWT-AC-24"][
        "blocking_issues"
    ] == [1500]
    assert all(r["status"] != "BLOCKED_1502_PHYSICAL_MFG" for r in d["records"])


def test_current_csv_ear_and_true_skin_supersessions_never_mutate_original_ac():
    d = _data()
    notes = d["current_legacy_supersessions"]
    assert len(notes) == 15
    assert set(notes).issubset({r["id"] for r in d["records"]})
    assert all(r["current_scope_correction_20261021"][
        "supersedes_original_interpretation_only"] is True
        for r in d["records"] if r["id"] in notes)
    source = d["latest_product_scope"]
    assert "committed NFBConfig" in source["current_source"]
    assert "NFB數值規格.csv" in source["current_source"]
    rule = source["rule"]
    assert "move TOGETHER in Z" in rule
    assert "signed fold" in rule and "T2 BEND23" in rule
    assert "UV side MARKING" in rule
    assert "Color150" in rule
    assert "PAD blank/material/thickness/Z/BOM" in rule
    assert "welding-workmanship certification" in source["cannot_be_inferred"]
    assert "full" not in d["review_status"].lower()
    assert {r["id"] for r in d["records"] if r["accepted"]} == {"NFB-AC-30", "NFB-AC-17", "SWT-AC-04", "NFB-AC-10", "SWT-AC-02", "NFB-AC-25", "NFB-AC-22", "SWT-AC-15", "SWT-AC-03", "NFB-AC-48", "NFB-AC-49", "NFB-AC-50", "SWT-AC-28", "NFB-AC-06", "NFB-AC-08", "NFB-AC-26", "NFB-AC-33", "NFB-AC-37", "SWT-AC-17", "SWT-AC-25", "NFB-AC-04", "NFB-AC-19", "NFB-AC-05", "NFB-AC-27", "SWT-AC-06", "NFB-AC-54", "SWT-AC-31" , "NFB-AC-29", "SWT-AC-19"}
    # Historical original AC-13 falsely held Base Plate Z fixed; preserve
    # the original phrase for traceability and declare its current override.
    row = {r["id"]: r for r in d["records"]}
    assert "底板不因 NFB 深度變更而位移" in row["NFB-AC-13"]["requirement"]
    assert "DOES move" in notes["NFB-AC-13"]
    assert "CURRENT" in notes["SWT-AC-09"]


def test_brand_inheritance_signed_witnesses_are_mandatory_and_source_bound():
    """Two brand-policy ACs require actual runnable assertion functions."""
    from tools.product_ci_regression import PYTEST_PATHS
    records = {r["id"]: r for r in _data()["records"]}
    proof = "tests/test_issue1504_brand_inheritance_current_csv.py"
    assert proof in PYTEST_PATHS
    required = {
        "NFB-AC-17": (
            "test_nfb_ac17_three_tier_followers_overrides_provenance_and_preview",
            "test_swt_ac04_spoofed_catalog_and_stale_csv_never_relabel_v5_source",
        ),
        "SWT-AC-04": (
            "test_swt_ac04_spoofed_catalog_and_stale_csv_never_relabel_v5_source",
            "test_swt_ac04_selected_brand_and_override_are_persisted_without_second_set_owner",
        ),
    }
    source = ast.parse((ROOT / proof).read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in source.body
        if isinstance(node, ast.FunctionDef)
    }
    for identity, (primary, extra) in required.items():
        row = records[identity]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["blocking_issues"] == []
        assert row["identified_test_functions"] == [{
            "path": proof, "test_name": primary,
            "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS", "accepted": True,
        }]
        evidence = row["acceptance_evidence"]
        assert evidence["primary_assertion"] == proof + "::" + primary
        assert evidence["other_required_assertion"] == proof + "::" + extra
        assert evidence["original_ac_text_unchanged"] is True
        assert evidence["factory_release"] is False
        assert evidence["human_windows_uat_claimed"] is False
        assert evidence["ui_full_operator_uat_claimed"] is False
        for name in (primary, extra):
            assert name in functions
            assert any(isinstance(n, ast.Assert) for n in ast.walk(functions[name]))


def test_current_nominal_and_operator_y_witnesses_are_mandatory_and_source_bound():
    """Legacy nominal ACs stay source-derived, not silently the new UI default."""
    from tools.product_ci_regression import PYTEST_PATHS
    proof = "tests/test_issue1504_current_nfb_y_ac10_swt02.py"
    assert proof in PYTEST_PATHS
    tree = ast.parse((ROOT / proof).read_text(encoding="utf-8"))
    functions = {
        x.name: x for x in tree.body if isinstance(x, ast.FunctionDef)
    }
    signed = {r["id"]: r for r in _data()["records"]}
    required = {
        "NFB-AC-10": (
            "test_nfb_ac10_current_330_830_operator_y_roundtrips_real_panel",
            "test_nfb_ac10_only_approved_nominal_pitch_and_no_world_x",
        ),
        "SWT-AC-02": (
            "test_swt_ac02_legacy_nominal_and_unknown_non1100_y_never_guess",
            "test_nfb_ac10_current_330_830_operator_y_roundtrips_real_panel",
        ),
    }
    for key, (primary, other) in required.items():
        row = signed[key]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["acceptance_evidence"]["original_ac_text_unchanged"] is True
        assert row["acceptance_evidence"]["factory_release"] is False
        assert row["acceptance_evidence"]["human_windows_uat_claimed"] is False
        assert row["acceptance_evidence"]["ui_full_operator_uat_claimed"] is False
        assert row["acceptance_evidence"]["primary_assertion"] == proof + "::" + primary
        assert row["acceptance_evidence"]["other_required_assertion"] == proof + "::" + other
        assert row["acceptance_evidence"]["negative_source_matrix_assertion"] == (
            proof + "::test_nfb_ac10_outside_source_matrix_remains_unknown_not_centered"
        )
        assert row["identified_test_functions"] == [{
            "path": proof, "test_name": primary,
            "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS",
            "accepted": True,
        }]
        for name in (primary, other, "test_nfb_ac10_outside_source_matrix_remains_unknown_not_centered"):
            assert name in functions
            assert any(isinstance(n, ast.Assert) for n in ast.walk(functions[name]))


def test_ac25_reselection_checks_are_direct_and_mandatory_without_mfg_release():
    """Sign only source-backed relative pitch with three separate blocked checks."""
    from tools.product_ci_regression import PYTEST_PATHS
    proof = "tests/test_issue1504_ac25_reselection_nominal_x.py"
    assert proof in PYTEST_PATHS
    row = {r["id"]: r for r in _data()["records"]}["NFB-AC-25"]
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    e = row["acceptance_evidence"]
    assert e["original_ac_text_unchanged"] is True
    assert e["factory_release"] is False
    assert e["human_windows_uat_claimed"] is False
    assert e["ui_full_operator_uat_claimed"] is False
    funcs = [
        "test_nfb_ac25_reselection_preserves_approved_relative_pitch_no_fake_x_checks",
        "test_nfb_ac25_q16_explicit_zero_does_not_turn_old_x_datum_into_approval",
        "test_nfb_ac25_unknown_pitch_cannot_become_centered_or_verified",
    ]
    assert e["primary_assertion"] == proof + "::" + funcs[0]
    assert e["other_required_assertion"] == proof + "::" + funcs[1]
    assert e["negative_source_matrix_assertion"] == proof + "::" + funcs[2]
    assert e["separate_mfg1_preflight"] == (
        "tests/test_issue1497_nfb_cutting_preflight.py"
        "::test_unresolved_x_never_generates_a_fake_center_or_manufacturable_hole"
    )
    assert "tests/test_issue1497_nfb_cutting_preflight.py" in PYTEST_PATHS
    tree = ast.parse((ROOT / proof).read_text(encoding="utf-8"))
    defs = {x.name: x for x in tree.body if isinstance(x, ast.FunctionDef)}
    for name in funcs:
        assert name in defs
        assert any(isinstance(n, ast.Assert) for n in ast.walk(defs[name]))
    assert row["identified_test_functions"] == [{
        "path": proof, "test_name": funcs[0],
        "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS",
        "accepted": True,
    }]



def test_ac22_swt15_source_owned_x_and_save_reload_witnesses_are_mandatory():
    """Current V5 unknown X is saved; test names alone cannot approve it."""
    from tools.product_ci_regression import PYTEST_PATHS
    proof = "tests/test_issue1504_ac22_swt15_current_x_persistence.py"
    assert PYTEST_PATHS.count(proof) == 1
    tree = ast.parse((ROOT / proof).read_text(encoding="utf-8"))
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    required = {
        "NFB-AC-22": (
            "test_nfb_ac22_v5_bay_x_zero_none_datum_order_save_reopen_never_auto_approves",
            "test_nfb_ac22_ui_edit_zero_and_clear_have_distinct_unverified_states",
        ),
        "SWT-AC-15": (
            "test_swt_ac15_quantity_v5_x_zero_none_version_isolation_and_reopen",
            "test_current_x_persistence_rejects_fake_manufacturing_flags_and_nonfinite_x",
        ),
    }
    rows = {r["id"]: r for r in _data()["records"]}
    negative = "test_current_x_persistence_rejects_fake_manufacturing_flags_and_nonfinite_x"
    for key, (primary, extra) in required.items():
        row = rows[key]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["blocking_issues"] == []
        assert row["identified_test_functions"] == [{
            "path": proof, "test_name": primary,
            "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS", "accepted": True,
        }]
        evidence = row["acceptance_evidence"]
        assert evidence["primary_assertion"] == proof + "::" + primary
        assert evidence["other_required_assertion"] == proof + "::" + extra
        assert evidence["negative_input_assertion"] == proof + "::" + negative
        assert evidence["factory_release"] is False
        assert evidence["human_windows_uat_claimed"] is False
        assert evidence["ui_full_operator_uat_claimed"] is False
        assert evidence["original_ac_text_unchanged"] is True
        for name in (primary, extra, negative):
            assert name in functions
            assert any(isinstance(n, ast.Assert) for n in ast.walk(functions[name]))





def test_swt03_ui_scope_and_ac05_independent_current_v5_physical_dxfs():
    """UI-only SWT03 evidence stays distinct from AC05 physical CSV/DXF proof."""
    from tools.product_ci_regression import PYTEST_PATHS
    proof = "tests/test_issue1504_swt03_nfb05_current_unit_rotation.py"
    assert PYTEST_PATHS.count(proof) == 1
    nodes = ast.parse((ROOT / proof).read_text(encoding="utf-8")).body
    functions = {n.name: n for n in nodes if isinstance(n, ast.FunctionDef)}
    rows = {r["id"]: r for r in _data()["records"]}
    row = rows["SWT-AC-03"]
    primary = "test_swt_ac03_current_csv_units_keep_independent_identity_model_x_and_rotation"
    second = "test_swt_ac03_reorder_insert_delete_reset_only_touched_tier_and_keep_true_pitch"
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["identified_test_functions"] == [{
        "path": proof, "test_name": primary,
        "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS", "accepted": True,
    }]
    evidence = row["acceptance_evidence"]
    assert evidence["primary_assertion"] == proof + "::" + primary
    assert evidence["other_required_assertion"] == proof + "::" + second
    assert evidence["factory_release"] is False
    assert evidence["human_windows_uat_claimed"] is False
    assert evidence["ui_full_operator_uat_claimed"] is False
    for name in (primary, second):
        assert name in functions
        assert any(isinstance(x, ast.Assert) for x in ast.walk(functions[name]))
    # The original SWT-03 UI-only signoff remains unchanged; AC-05 now
    # has independent CURRENT CSV V5 physical FinalScene + saved DXF proof.
    physical = rows["NFB-AC-05"]
    assert physical["accepted"] is True
    assert physical["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    path = "tests/test_issue1504_ac05_v5_physical_rotation_dxf.py"
    assert PYTEST_PATHS.count(path) == 1
    assert physical["identified_test_functions"][0]["path"] == path
    assert physical["acceptance_evidence"]["factory_release"] is False
    assert physical["acceptance_evidence"]["human_windows_uat_claimed"] is False
    needed = [physical["acceptance_evidence"]["primary_assertion"],
              *physical["acceptance_evidence"]["other_required_assertions"]]
    assert len(needed) >= 5
    for exact in needed:
        filename, func = exact.split("::")
        assert PYTEST_PATHS.count(filename) == 1
        ast_body = ast.parse((ROOT / filename).read_text(encoding="utf-8")).body
        defs = {n.name: n for n in ast_body if isinstance(n, ast.FunctionDef)}
        assert func in defs
        assert any(isinstance(x, ast.Assert) for x in ast.walk(defs[func]))


def test_ac27_swt06_current_v5_physical_q16_source_signoff_requires_real_dxf_negative_witness():
    """Source/physical witnesses, not legacy shadow-DXF Q16 alone."""
    from tools.product_ci_regression import PYTEST_PATHS
    proof = "tests/test_issue1504_ac27_swt06_v5_physical_q16_transactions.py"
    assert PYTEST_PATHS.count(proof) == 1
    tests = {
        n.name: n for n in ast.parse(
            (ROOT / proof).read_text(encoding="utf-8")
        ).body if isinstance(n, ast.FunctionDef)
    }
    names = (
        "test_ac27_swt06_valid_q16_preserves_two_unit_identity_pitch_and_revalidates_real_v5_dxfs",
        "test_ac27_swt06_invalid_q16_actual_v5_cutting_collision_rolls_back_all_existing_dxfs",
        "test_ac27_swt06_failed_q16_session_undo_and_cancel_keep_existing_v5_manufacturing",
    )
    for name in names:
        assert name in tests
        assert any(isinstance(node, ast.Assert) for node in ast.walk(tests[name]))
        assert any(isinstance(node, ast.Call) for node in ast.walk(tests[name]))
    rows = {row["id"]: row for row in _data()["records"]}
    for key in ("NFB-AC-27", "SWT-AC-06"):
        row = rows[key]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["assertion_review_state"] == "FULL_AC_AUTOMATED_SIGNED"
        evidence = row["acceptance_evidence"]
        assert evidence["primary_assertion"] == proof + "::" + names[0]
        assert proof + "::" + names[1] in evidence["other_required_assertions"]
        assert proof + "::" + names[2] in evidence["other_required_assertions"]
        assert evidence["factory_release"] is False
        assert evidence["human_windows_uat_claimed"] is False
        assert evidence["ui_full_operator_uat_claimed"] is False
        assert evidence["original_ac_text_unchanged"] is True
        assert row["identified_test_functions"][0]["accepted"] is True


def test_ac32_visible_x_reset_undo_patch_is_not_falsely_full_gui_signed():
    from tools.product_ci_regression import PYTEST_PATHS
    import ast
    from pathlib import Path
    path = "tests/test_issue1504_ac32_nfb_x_impact_operator.py"
    assert PYTEST_PATHS.count(path) == 1
    functions = {node.name: node for node in ast.parse(
        (ROOT / path).read_text(encoding="utf-8")
    ).body if isinstance(node, ast.FunctionDef)}
    for name in (
        "test_ac32_q5_q6_q7_reports_exact_layer_count_and_undo_restores_all_basis",
        "test_ac32_manual_clear_one_selected_slot_includes_zero_and_snapshot_no_residue",
        "test_ac32_compact_original_tk_ui_exposes_affected_count_and_reachable_undo",
    ):
        assert name in functions
        assert any(isinstance(a, ast.Assert) for a in ast.walk(functions[name]))
    row = next(r for r in _data()["records"] if r["id"] == "NFB-AC-32")
    assert row["accepted"] is False
    assert row["status"] == "EVIDENCE_CANDIDATE_ONLY"
    assert path in row["regression_candidates"]
    assert len(row["identified_test_functions"]) == 1
    assert row["identified_test_functions"][0]["path"] == "tests/test_issue1493_nfb_draft_transactions.py"
    assert row["additional_partial_witnesses"] == [{
        "path": path,
        "test_name": "test_ac32_q5_q6_q7_reports_exact_layer_count_and_undo_restores_all_basis",
        "witness_scope": "PARTIAL_AUTOMATED_ASSERTIONS_ONLY",
        "accepted": False,
    }]
    assert "true integrated Receiving NFB modal" in row["current_scope_remaining_evidence"]


def test_ac54_swt31_current_v5_project_schema_exact_regression_and_no_old_binary_claim():
    """A schema filename alone is not V5 end-to-end serialization proof."""
    from tools.product_ci_regression import PYTEST_PATHS
    path = "tests/test_issue1504_ac54_swt31_current_v5_project_schema.py"
    assert PYTEST_PATHS.count(path) == 1
    source = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in source.body
        if isinstance(node, ast.FunctionDef)
    }
    names = {
        "test_ac54_swt31_current_v5_submitted_set_bay_schema_upgrades_root_and_preserves_all_operators",
        "test_ac54_swt31_current_v5_quantity_upgrades_both_schemas_and_isolates_versions",
        "test_ac54_swt31_legacy_reader_cannot_silently_drop_current_v5_submitted",
        "test_ac54_swt31_legacy_quantity_schema_with_embedded_v5_rejected_without_mutation",
        "test_ac54_swt31_current_v5_unsubmitted_retains_existing_schema_and_no_nfb_authority",
    }
    assert names.issubset(functions)
    for name in names:
        assert any(isinstance(n, ast.Assert) for n in ast.walk(functions[name]))
        assert any(isinstance(n, ast.Call) for n in ast.walk(functions[name]))
    rows = {row["id"]: row for row in _data()["records"]}
    for key in ("NFB-AC-54", "SWT-AC-31"):
        row = rows[key]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["identified_test_functions"] == [{
            "path": path,
            "test_name": "test_ac54_swt31_current_v5_submitted_set_bay_schema_upgrades_root_and_preserves_all_operators",
            "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS",
            "accepted": True,
        }]
        evidence = row["acceptance_evidence"]
        for exact in (evidence["primary_assertion"],
                      *evidence["other_required_assertions"]):
            file_name, function = exact.split("::")
            assert PYTEST_PATHS.count(file_name) == 1
            defs = {
                node.name: node for node in ast.parse(
                    (ROOT / file_name).read_text(encoding="utf-8")
                ).body if isinstance(node, ast.FunctionDef)
            }
            assert function in defs
            # Explicit rejection tests use pytest.raises, not a literal
            # 'assert'.  Require a real with-raises check rather than
            # weakening the historical-schema negative witness gate.
            body = defs[function]
            direct = any(isinstance(n, ast.Assert) for n in ast.walk(body))
            rejected = any(
                isinstance(node, ast.With)
                and any(
                    isinstance(item.context_expr, ast.Call)
                    and isinstance(item.context_expr.func, ast.Attribute)
                    and item.context_expr.func.attr == "raises"
                    and bool(item.context_expr.args)
                    for item in node.items
                )
                for node in ast.walk(body)
            )
            assert direct or rejected, exact
        assert evidence["external_historical_binary_read_executed"] is False
        assert evidence["real_two_old_project_windows_gui_uat"] is False
        assert evidence["factory_release"] is False
        assert evidence["human_windows_uat_claimed"] is False
        assert evidence["original_ac_text_unchanged"] is True


def test_ac29_swt19_current_v5_source_drift_has_real_reloaded_project_cutting_and_fail_closed_witnesses():
    """No legacy DXF/SHADOW or stale flag can stand in for changed CSV geometry."""
    from tools.product_ci_regression import PYTEST_PATHS
    path = "tests/test_issue1504_ac29_swt19_v5_reload_source_rederive.py"
    assert PYTEST_PATHS.count(path) == 1
    names = (
        "test_ac29_swt19_reload_current_v5_rederives_real_centres_and_cutting",
        "test_ac29_swt19_csv_bytes_change_requires_fresh_finalscene_and_dxf",
        "test_ac29_swt19_source_revised_collision_or_boundary_cannot_use_old_green",
        "test_ac29_swt19_original_hole_editor_csv_proof_from_before_reload_cannot_be_reused",
    )
    functions = {
        node.name: node for node in ast.parse(
            (ROOT / path).read_text(encoding="utf-8")
        ).body if isinstance(node, ast.FunctionDef)
    }
    for name in names:
        assert name in functions
        assert any(isinstance(node, ast.Assert) for node in ast.walk(functions[name]))
        assert any(isinstance(node, ast.Call) for node in ast.walk(functions[name]))
    rows = {r["id"]: r for r in _data()["records"]}
    for key in ("NFB-AC-29", "SWT-AC-19"):
        row = rows[key]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert len(row["identified_test_functions"]) == 1
        primary = row["identified_test_functions"][0]
        assert primary["path"] == path and primary["test_name"] == names[0]
        assert primary["witness_scope"] == "FULL_AC_AUTOMATED_ASSERTIONS"
        evidence = row["acceptance_evidence"]
        assert evidence["primary_assertion"] == path + "::" + names[0]
        for name in names[1:]:
            assert path + "::" + name in evidence["other_required_assertions"]
        for exact in (evidence["primary_assertion"],
                      *evidence["other_required_assertions"]):
            file_name, function = exact.split("::")
            assert PYTEST_PATHS.count(file_name) == 1
            target = {
                node.name: node for node in ast.parse(
                    (ROOT / file_name).read_text(encoding="utf-8")
                ).body if isinstance(node, ast.FunctionDef)
            }
            assert function in target
            assert any(
                isinstance(node, ast.Assert)
                or (isinstance(node, ast.With) and any(
                    isinstance(item.context_expr, ast.Call)
                    and isinstance(item.context_expr.func, ast.Attribute)
                    and item.context_expr.func.attr == "raises"
                    for item in node.items
                ))
                for node in ast.walk(target[function])
            ), exact
        assert evidence["source_dxf_historical_binary_rechecked"] is False
        assert evidence["real_two_old_project_windows_gui_uat"] is False
        assert evidence["factory_release"] is False
        assert evidence["human_windows_uat_claimed"] is False
        assert evidence["original_ac_text_unchanged"] is True


def test_ac21_swt14_current_v5_partial_witnesses_cannot_inflate_29_acceptances():
    """Source-level isolation passes; per-version GUI brand default remains a gap."""
    from tools.product_ci_regression import PYTEST_PATHS
    path = "tests/test_issue1504_ac21_swt14_quantity_brand_scoping.py"
    assert PYTEST_PATHS.count(path) == 1
    functions = {
        node.name: node for node in ast.parse(
            (ROOT / path).read_text(encoding="utf-8")
        ).body if isinstance(node, ast.FunctionDef)
    }
    required = (
        "test_ac21_swt14_current_v5_each_version_model_brand_and_operator_basis_are_independent",
        "test_ac21_swt14_three_tier_current_csv_brand_inheritance_never_rewrites_model",
        "test_ac21_swt14_invalid_cross_brand_current_v5_submission_is_atomic",
        "test_ac21_swt14_quantity_brand_ui_actual_owner_gap_remains_unsigned",
    )
    for name in required:
        assert name in functions
        assert any(isinstance(node, ast.Assert) for node in ast.walk(functions[name]))
    rows = {r["id"]:r for r in _data()["records"]}
    for key in ("NFB-AC-21","SWT-AC-14"):
        row=rows[key]
        assert row["accepted"] is False
        assert row["status"] == "EVIDENCE_CANDIDATE_ONLY"
        assert row["source_gap_reproduced_20261023"] is True
        assert path in row["regression_candidates"]
        assert len(row["identified_test_functions"]) == 1
        assert all(w["accepted"] is False
                   for w in row["additional_partial_witnesses"])
        assert "receiving_quantity_box.switch_brand" in row["current_scope_remaining_evidence"]


def test_unified_nfb_brand_rule_current_gui_entry_fix_does_not_fake_ac21_swt14_signoff():
    """Same existing brand algorithm with mode-specific INPUT owner, not 2 rules."""
    from tools.product_ci_regression import PYTEST_PATHS
    path = "tests/test_issue1504_one_nfb_brand_rule_mode_projection.py"
    assert PYTEST_PATHS.count(path) == 1
    funcs = {
        node.name: node for node in ast.parse(
            (ROOT / path).read_text(encoding="utf-8")
        ).body if isinstance(node, ast.FunctionDef)
    }
    for name in (
        "test_quantity_brand_projects_original_owner_to_same_nfb_layer_unit_rule",
        "test_quantity_brand_override_reuses_existing_three_tier_rule_exactly",
        "test_set_bay_brand_owner_unchanged_by_quantity_entry_routing",
        "test_all_three_real_gui_nfb_source_call_sites_use_same_active_mode_owner",
    ):
        assert name in funcs
        assert any(isinstance(n, ast.Assert) for n in ast.walk(funcs[name]))
    rows={r["id"]:r for r in _data()["records"]}
    for key in ("NFB-AC-21","SWT-AC-14"):
        row=rows[key]
        assert row["accepted"] is False
        assert row["status"] == "EVIDENCE_CANDIDATE_ONLY"
        assert len(row["identified_test_functions"]) == 1
        assert "same effective_nfb_slot_brand" in row["current_scope_remaining_evidence"]
        assert all(w["accepted"] is False for w in row["additional_partial_witnesses"])
