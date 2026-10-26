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
# Immutable 43-source-scope signature at the 2026-10-24 audit checkpoint.
# New exact-GREEN signoffs add rows; they never retract an earlier signed AC.
HISTORICAL_SIGNED_43 = {"NFB-AC-30", "NFB-AC-17", "SWT-AC-04", "NFB-AC-10", "SWT-AC-02", "NFB-AC-25", "NFB-AC-22", "SWT-AC-15", "SWT-AC-03", "NFB-AC-48", "NFB-AC-49", "NFB-AC-50", "SWT-AC-28", "NFB-AC-06", "NFB-AC-08", "NFB-AC-26", "NFB-AC-33", "NFB-AC-37", "SWT-AC-17", "SWT-AC-25", "NFB-AC-04", "NFB-AC-19", "NFB-AC-05", "NFB-AC-27", "SWT-AC-06", "NFB-AC-54", "SWT-AC-31" , "NFB-AC-29", "SWT-AC-19", "NFB-AC-01", "SWT-AC-01", "NFB-AC-47", "NFB-AC-09", "NFB-AC-24", "NFB-AC-21", "SWT-AC-14", "NFB-AC-20", "SWT-AC-13", "NFB-AC-32", "NFB-AC-18", "NFB-AC-03", "NFB-AC-15", "SWT-AC-05"}

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
    assert rows["NFB-AC-14"]["status"] in {
        "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC",
        "ACCEPTED_AUTOMATED_CURRENT_SCOPE",
    }
    ac13 = rows["NFB-AC-13"]
    assert ac13["status"] in {
        "DEFERRED_PRODUCT_EVIDENCE", "ACCEPTED_AUTOMATED_CURRENT_SCOPE",
    }
    if ac13["accepted"]:
        assert ac13["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        proof = ac13["acceptance_evidence"]
        assert proof["current_scope_correction_applied"] is True
        assert proof["original_ac_text_unchanged"] is True
        assert len(proof["original_ac_clauses_audited"]) >= 3
        assert proof["factory_release"] is False
        assert proof["independent_pad_manufacturing_approved"] is False
        assert proof["human_windows_uat_claimed"] is False
    else:
        assert ac13["status"] == "DEFERRED_PRODUCT_EVIDENCE"
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
    assert HISTORICAL_SIGNED_43 <= {r["id"] for r in rows.values() if r["accepted"]}
    assert rows["NFB-AC-30"]["blocking_issues"] == []


def test_1502_newer_corrected_base_plate_scope_is_not_lost():
    obj = _data()
    assert obj["latest_product_scope"]["authority_issue"] == 1502
    for row in obj["records"]:
        if "current_scope_correction" in row:
            assert 1502 in row["owning_issues"]
            assert row["current_scope_correction"]["issue"] == 1502
            if row["accepted"]:
                # Only individually source-audited corrected ACs may advance:
                # the old illustrated Receiving middle plate must NEVER be
                # silently restored merely to collect a manufacturing GREEN.
                assert row["id"] in {"NFB-AC-38", "SWT-AC-21", "NFB-AC-44", "SWT-AC-32", "NFB-AC-55"}
                assert row["historical_pre_current_review"].get("accepted", False) is False
                proof = row["acceptance_evidence"]
                assert proof["original_ac_text_unchanged"] is True
                assert proof["source_sha_pins_unchanged"] is True
                assert proof["factory_release"] is False
                assert proof["unconditional_mfg2_release"] is False
                assert proof["other_ac_signoff_implied"] is False
            else:
                assert row["accepted"] is False


def test_manifest_review_summary_is_recomputed_from_records():
    obj = _data()
    counts = dict(Counter(r["status"] for r in obj["records"]))
    # The last historical deferred AC may be source-signed. The original
    # four identities stay audited, while the current live count is zero.
    counts.setdefault("DEFERRED_PRODUCT_EVIDENCE", 0)
    counts.setdefault("SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC", 0)
    counts.setdefault("EVIDENCE_CANDIDATE_ONLY", 0)
    assert sum(counts.values()) == 88
    assert obj["counts"] == counts
    # Four original deferred identities are immutable. Their *current*
    # accepted/deferred partition changes only on source-audited signoff.
    historic = {"NFB-AC-13", "NFB-AC-41", "SWT-AC-09", "SWT-AC-22"}
    by_id = {row["id"]: row for row in obj["records"]}
    assert counts["DEFERRED_PRODUCT_EVIDENCE"] == sum(
        by_id[key]["status"] == "DEFERRED_PRODUCT_EVIDENCE"
        for key in historic
    )
    assert counts["DEFERRED_PRODUCT_EVIDENCE"] + sum(
        by_id[key]["accepted"] for key in historic
    ) == len(historic) == 4
    assert counts["BLOCKED_1500_REAL_GUI"] >= 1
    assert counts.get("SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC",0) <= 14
    assert 0 < counts["BLOCKED_1500_REAL_GUI"] <= 17
    assert counts.get("EVIDENCE_CANDIDATE_ONLY",0) <= 10
    assert counts["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] >= len(HISTORICAL_SIGNED_43) == 43


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
            if item["accepted"]:
                assert witness["witness_scope"] in {
                    "FULL_AC_AUTOMATED_ASSERTIONS",
                    "FULL_AC_AUTOMATED_CURRENT_CSV_SOURCE",
                    "FULL_AC_AUTOMATED_SUPPORTED_CSV_V5_QUANTITY_PARTS",
                }, item["id"]
                # An explicitly source-scoped primary witness must retain
                # its concrete product and manufacturer/Windows limitations.
                if witness["witness_scope"] != "FULL_AC_AUTOMATED_ASSERTIONS":
                    proof=item["acceptance_evidence"]
                    assert proof["original_ac_text_unchanged"] is True, item["id"]
                    assert proof["factory_release"] is False, item["id"]
                    assert proof["human_windows_uat_claimed"] is False, item["id"]
                    assert proof["integrated_localx_claimed"] is False, item["id"]
            else:
                assert witness["witness_scope"] == "PARTIAL_AUTOMATED_ASSERTIONS_ONLY", item["id"]
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
    assert row["NFB-AC-35"]["accepted"]  # exact Tk restore/Undo source-scoped receipt



def test_one_full_ac_requires_source_specific_runtime_witness_and_ci_selection():
    obj = _data()
    assert obj["exact_test_function_witnesses_review"].startswith(
        "88/88 FUNCTION_IDENTITIES_VERIFIED; "
        + str(obj["counts"]["ACCEPTED_AUTOMATED_CURRENT_SCOPE"])
        + "/88 FULL_AC_AUTOMATED_SIGNED"
    )
    signed = {r["id"]: r for r in obj["records"] if r["accepted"]}
    assert HISTORICAL_SIGNED_43 <= set(signed)
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
    assert HISTORICAL_SIGNED_43 <= {r["id"] for r in obj["records"] if r["accepted"]}

    # The human review must not silently retain an older X-centering claim.
    text = MANIFEST.with_suffix(".md").read_text(encoding="utf-8")
    assert "箱體中心 X=0" in text
    assert "**孔距 670 mm**" in text
    assert "T2/BEND23" in text and "EAR 已不是全部未驗" in text


def test_closed_1502_is_not_an_open_gate_and_original_ac_claims_stay_unsigned():
    """Closed localX scope cannot be counted as an open blocker or as 88 passes."""
    d = _data()
    assert re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}",d["assessed_on"])
    assert d["assessed_on"] >= "2026-10-22"
    assert 1502 not in d["open_gates"]
    assert 1503 not in d["open_gates"]
    # Original #1502 closure remains immutable; subsequent AC-03 scoped
    # signoff updates only current matrix, not the 2026-10-22 audit date.
    live_counts = dict(Counter(r["status"] for r in d["records"]))
    live_counts.setdefault("DEFERRED_PRODUCT_EVIDENCE", 0)
    live_counts.setdefault("SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC", 0)
    live_counts.setdefault("EVIDENCE_CANDIDATE_ONLY", 0)
    assert d["counts"] == live_counts
    assert sum(d["counts"].values()) == 88
    assert 0 < d["counts"]["BLOCKED_1500_REAL_GUI"] <= 17
    # At the original 79-AC audit snapshot, four physical-source items
    # were deferred. The historical IDs remain immutable even after each
    # *individually* gains full source/Tk/negative manufacturing evidence.
    original_deferred = {"NFB-AC-13", "NFB-AC-41", "SWT-AC-09", "SWT-AC-22"}
    rows = {r["id"]: r for r in d["records"]}
    assert len(original_deferred) == 4
    assert d["counts"]["DEFERRED_PRODUCT_EVIDENCE"] == sum(
        rows[key]["status"] == "DEFERRED_PRODUCT_EVIDENCE"
        for key in original_deferred
    )
    for key in original_deferred:
        row = rows[key]
        if row["accepted"]:
            assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE", key
            assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED", key
            assert row["assertion_review_state"] == "FULL_AC_AUTOMATED_SIGNED", key
            proof = row["acceptance_evidence"]
            assert proof["original_ac_text_unchanged"] is True, key
            assert proof["source_sha_pins_unchanged"] is True, key
            assert proof["factory_release"] is False, key
            assert proof["unconditional_mfg2_release"] is False, key
            assert proof["human_windows_uat_claimed"] is False, key
            assert len(proof["original_ac_clauses_audited"]) >= 3, key
            assert len(proof["other_required_assertions"]) >= 2, key
        else:
            assert row["status"] == "DEFERRED_PRODUCT_EVIDENCE", key
    assert sum(rows[key]["accepted"] for key in original_deferred) + (
        d["counts"]["DEFERRED_PRODUCT_EVIDENCE"]
    ) == 4
    assert d["counts"]["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] >= len(HISTORICAL_SIGNED_43)
    scoped = tuple(r for r in d["records"] if r["status"].startswith(
        "SCOPED_LOCALX_1502_"
    ))
    assert len(scoped) == d["counts"].get("SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC",0)
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
    assert HISTORICAL_SIGNED_43 <= {r["id"] for r in d["records"] if r["accepted"]}
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
    # Historical source-only evidence must remain intact even after the
    # additional real original Tk transaction is signed for CURRENT scope.
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert path in row["regression_candidates"]
    assert len(row["identified_test_functions"]) == 1
    assert row["identified_test_functions"][0]["path"] == (
        "tests/test_issue1504_ac32_original_inner_tk_x_undo.py"
    )
    assert row["additional_partial_witnesses"] == [{
        "path": path,
        "test_name": "test_ac32_q5_q6_q7_reports_exact_layer_count_and_undo_restores_all_basis",
        "witness_scope": "PARTIAL_AUTOMATED_ASSERTIONS_ONLY",
        "accepted": False,
    }]
    proof = row["acceptance_evidence"]
    assert proof["ui_full_operator_uat_claimed"] is False
    assert proof["real_two_old_project_windows_gui_uat"] is False
    assert proof["physical_absolute_position_grant"] is False
    assert "Windows" in row["current_scope_remaining_evidence"]
    assert "actual integrated WHD inner-editor Tk" in row["current_scope_remaining_evidence"]


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
    """Verify scoped Tk/version witnesses and keep full Windows UAT separate."""
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
        "test_ac21_swt14_original_gui_brand_selector_uses_selected_version_only",
    )
    for name in required:
        assert name in functions
        assert any(isinstance(node, ast.Assert) for node in ast.walk(functions[name]))
    rows = {r["id"]:r for r in _data()["records"]}
    for key in ("NFB-AC-21","SWT-AC-14"):
        row=rows[key]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["source_gap_reproduced_20261023"] is True
        assert row["current_version_brand_gui_gap_resolved_20261023"] is True
        assert path in row["regression_candidates"]
        assert len(row["identified_test_functions"]) == 1
        assert all(w["accepted"] is False
                   for w in row["additional_partial_witnesses"])
        assert "nfb_parent_brand" in row["current_scope_remaining_evidence"]


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
        "test_all_inner_editor_gui_nfb_source_call_sites_use_same_active_mode_owner",
    ):
        assert name in funcs
        assert any(isinstance(n, ast.Assert) for n in ast.walk(funcs[name]))
    rows={r["id"]:r for r in _data()["records"]}
    for key in ("NFB-AC-21","SWT-AC-14"):
        row=rows[key]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert len(row["identified_test_functions"]) == 1
        assert "same effective_nfb_slot_brand" in row["current_scope_remaining_evidence"]
        assert all(w["accepted"] is False for w in row["additional_partial_witnesses"])


def test_ac01_real_receiving_only_tk_entry_has_exact_selected_positive_and_negative_witnesses():
    """Do not sign a mere file/path name: demand real Tk tests + family gates."""
    from tools.product_ci_regression import PYTEST_PATHS
    path = "tests/test_issue1504_ac01_receiving_only_actual_tk_entry.py"
    assert PYTEST_PATHS.count(path) == 1
    funcs = {
        node.name: node for node in ast.parse(
            (ROOT / path).read_text(encoding="utf-8")
        ).body if isinstance(node, ast.FunctionDef)
    }
    expected = {
        "test_ac01_actual_receiving_tk_operator_nfb_selector_only_under_family",
        "test_ac01_nonreceiving_family_never_mounts_nfb_dialog_or_mutates_hole_editor",
        "test_ac01_original_generic_hole_editor_door_entry_remains_unpatched",
    }
    assert expected.issubset(funcs)
    for name in expected:
        assert any(isinstance(node, ast.Assert) for node in ast.walk(funcs[name]))
        assert any(isinstance(node, ast.Call) for node in ast.walk(funcs[name]))
    positive = funcs["test_ac01_actual_receiving_tk_operator_nfb_selector_only_under_family"]
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open_multi_settings"
        for node in ast.walk(positive)
    )
    blocked = funcs["test_ac01_nonreceiving_family_never_mounts_nfb_dialog_or_mutates_hole_editor"]
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open_receiving_multi_settings"
        for node in ast.walk(blocked)
    )
    rows = {r["id"]:r for r in _data()["records"]}
    row = rows["NFB-AC-01"]
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["identified_test_functions"] == [{
        "path":path,
        "test_name":"test_ac01_actual_receiving_tk_operator_nfb_selector_only_under_family",
        "witness_scope":"FULL_AC_AUTOMATED_ASSERTIONS",
        "accepted":True,
    }]
    evidence=row["acceptance_evidence"]
    assert evidence["real_tk_widget_created"] is True
    assert evidence["nonreceiving_canonical_family_gate_verified"] is True
    assert evidence["human_windows_uat_claimed"] is False
    assert evidence["ui_full_operator_uat_claimed"] is False
    for item in (evidence["primary_assertion"], *evidence["other_required_assertions"]):
        source, func = item.split("::")
        assert PYTEST_PATHS.count(source) == 1
        names = {
            n.name for n in ast.parse(
                (ROOT / source).read_text(encoding="utf-8")
            ).body if isinstance(n, ast.FunctionDef)
        }
        assert func in names
    # SWT-AC-01 now independently witnesses the SHARED original count,
    # not a second layer business rule: inspect its exact complementary
    # current Tk owner, retired external dropdown, and draft Undo below.
    assert rows["SWT-AC-01"]["accepted"] is True


def test_unified_inner_door_nfb_installed_tier_count_is_one_tk_owner_not_two():
    from tools.product_ci_regression import PYTEST_PATHS
    import ast as _ast
    path = "tests/test_issue1504_unified_inner_nfb_layer_count.py"
    assert PYTEST_PATHS.count(path) == 1
    funcs = {_n.name: _n for _n in _ast.parse(
        (ROOT / path).read_text(encoding="utf-8"),
    ).body if isinstance(_n, _ast.FunctionDef)}
    for name in (
        "test_single_current_layer_count_owns_both_inner_door_and_nfb_mounting_tiers",
        "test_real_tk_single_variable_reaches_original_draft_and_undo_without_second_owner",
        "test_existing_legacy_count_and_nfb_draft_no_longer_have_an_inequality_gate",
    ):
        assert name in funcs
        assert any(isinstance(node, _ast.Assert)
                   for node in _ast.walk(funcs[name]))
    rows = {r["id"]: r for r in _data()["records"]}
    row = rows["SWT-AC-01"]
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["identified_test_functions"] == [{
        "path": path,
        "test_name": "test_single_current_layer_count_owns_both_inner_door_and_nfb_mounting_tiers",
        "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS",
        "accepted": True,
    }]
    assert row["acceptance_evidence"]["human_windows_uat_claimed"] is False
    for item in (row["acceptance_evidence"]["primary_assertion"],
                 *row["acceptance_evidence"]["other_required_assertions"]):
        source, name = item.split("::")
        assert PYTEST_PATHS.count(source) == 1, item
        names = {_n.name for _n in _ast.parse(
            (ROOT / source).read_text(encoding="utf-8"),
        ).body if isinstance(_n, _ast.FunctionDef)}
        assert name in names, item
    assert path in rows["NFB-AC-18"]["regression_candidates"]

def test_ac24_required_live_per_unit_real_part_scope_and_no_saved_derived_green():
    from tools.product_ci_regression import PYTEST_PATHS
    import ast
    import json
    evidence=json.loads(MANIFEST.read_text(encoding="utf-8"))
    row=next(r for r in evidence["records"] if r["id"]=="NFB-AC-24")
    assert row["status"]=="ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["accepted"] is True
    refs=(row["acceptance_evidence"]["primary_assertion"],
          *row["acceptance_evidence"]["other_required_assertions"])
    assert len(refs)>=9
    for ref in refs:
        path,fn=ref.split("::",1)
        assert path in PYTEST_PATHS
        tree=ast.parse((ROOT/path).read_text(encoding="utf-8"))
        definitions={node.name:node for node in tree.body
                     if isinstance(node,ast.FunctionDef)}
        assert fn in definitions
        # Negative proof is a true executable pytest.raises guard, not a
        # no-op asserted marker. Test suites can use either form.
        def _is_negative_assertion(node):
            return (isinstance(node, ast.With) and any(
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Attribute)
                and isinstance(item.context_expr.func.value, ast.Name)
                and item.context_expr.func.value.id == "pytest"
                and item.context_expr.func.attr == "raises"
                for item in node.items))
        assert any(isinstance(node, ast.Assert) or _is_negative_assertion(node)
                   for node in ast.walk(definitions[fn]))
    for flag in ("factory_release","human_windows_uat_claimed",
                 "ui_full_operator_uat_claimed"):
        assert row["acceptance_evidence"][flag] is False


def test_ac21_swt14_real_native_tk_v3_brand_scoped_signoff_never_implies_windows_or_factory():
    """Require genuine operator Tk and independent CSV/persistence/negative tests."""
    from tools.product_ci_regression import PYTEST_PATHS
    rows = {r["id"]: r for r in _data()["records"]}
    expected = {
        "NFB-AC-21": "test_ac21_swt14_real_tk_single_brand_selector_scopes_two_versions",
        "SWT-AC-14": "test_ac21_swt14_quantity_selected_version_parent_brand_is_single_owner",
    }
    for key, fn in expected.items():
        row = rows[key]
        proof = row["acceptance_evidence"]
        witness = row["identified_test_functions"][0]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert witness["accepted"] is True and witness["test_name"] == fn
        assert proof["primary_assertion"] == witness["path"] + "::" + fn
        for field in ("factory_release", "human_windows_uat_claimed",
                      "ui_full_operator_uat_claimed", "real_two_old_project_windows_gui_uat",
                      "physical_absolute_position_grant", "other_ac_signoff_implied"):
            assert proof[field] is False, (key, field)
        assert proof["original_ac_text_unchanged"] is True
        assert proof["source_sha_pins_unchanged"] is True
        assert row["current_version_brand_gui_gap_resolved_20261023"] is True
        proofs = [proof["primary_assertion"], *proof["other_required_assertions"]]
        assert len(proofs) >= 5 and len(set(proofs)) == len(proofs)
        for item in proofs:
            file_path, test_name = item.split("::")
            assert PYTEST_PATHS.count(file_path) == 1, item
            tree = ast.parse((ROOT / file_path).read_text(encoding="utf-8"))
            funcs = [n for n in tree.body
                     if isinstance(n, ast.FunctionDef) and n.name == test_name]
            assert len(funcs) == 1, item
            assert any(isinstance(n, ast.Assert) for n in ast.walk(funcs[0])), item
        assert "tests/test_issue1504_ac21_swt14_quantity_brand_scoping.py::test_ac21_swt14_real_tk_single_brand_selector_scopes_two_versions" in proofs
        assert "tests/test_issue1504_ac21_swt14_quantity_brand_scoping.py::test_ac21_swt14_changed_quantity_parent_marks_inherited_v5_model_reselect" in proofs


def test_ac20_swt13_scoped_signoff_requires_original_native_tk_cancel_undo_and_current_csv_provenance():
    """Demand actual GUI acceptance and source guards, not just a green counter."""
    from tools.product_ci_regression import PYTEST_PATHS
    import ast
    rows = {r["id"]: r for r in _data()["records"]}
    expected = {
        "NFB-AC-20": "test_ac20_original_inner_tk_layer_brand_cancel_confirm_undo",
        "SWT-AC-13": "test_swt13_original_inner_tk_unit_cancel_and_same_brand_override",
    }
    required_native = {
        "tests/test_issue1504_ac20_swt13_native_inner_brand_gui.py"
        "::test_ac20_original_inner_tk_layer_brand_cancel_confirm_undo",
        "tests/test_issue1504_ac20_swt13_native_inner_brand_gui.py"
        "::test_swt13_original_inner_tk_unit_cancel_and_same_brand_override",
    }
    for ac_id, primary in expected.items():
        row = rows[ac_id]
        witness = row["identified_test_functions"][0]
        evidence = row["acceptance_evidence"]
        assert row["accepted"] is True
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
        assert row["brand_preview_transaction_gui_scope_completed_20261023"] is True
        assert witness["test_name"] == primary and witness["accepted"] is True
        assert evidence["primary_assertion"] == witness["path"] + "::" + primary
        assert evidence["original_ac_text_unchanged"] is True
        assert evidence["source_sha_pins_unchanged"] is True
        assert evidence["factory_release"] is False
        assert evidence["human_windows_uat_claimed"] is False
        assert evidence["real_two_old_project_windows_gui_uat"] is False
        assert evidence["physical_absolute_position_grant"] is False
        assertions = [evidence["primary_assertion"], *evidence["other_required_assertions"]]
        assert len(assertions) >= 6 and len(set(assertions)) == len(assertions)
        assert required_native.issubset(assertions)
        for exact in assertions:
            path, function = exact.split("::")
            assert PYTEST_PATHS.count(path) == 1, exact
            node = ast.parse((ROOT / path).read_text(encoding="utf-8"))
            funcs = [f for f in node.body if isinstance(f, ast.FunctionDef)
                     and f.name == function]
            assert len(funcs) == 1, exact
            assert any(isinstance(a, ast.Assert) for a in ast.walk(funcs[0])), exact
        assert "CSV V5" in row["current_scope_remaining_evidence"]
        assert "Windows" in row["current_scope_remaining_evidence"]


def test_ac32_scoped_signoff_requires_real_original_tk_x_reset_and_undo_proof():
    """Seed old UI1A draft datum, but require real original Tk removal and Undo."""
    import ast
    from tools.product_ci_regression import PYTEST_PATHS
    row = {r["id"]: r for r in _data()["records"]}["NFB-AC-32"]
    evidence = row["acceptance_evidence"]
    witness = row["identified_test_functions"][0]
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    assert witness["accepted"] is True
    assert evidence["primary_assertion"] == witness["path"] + "::" + witness["test_name"]
    assert evidence["original_ac_text_unchanged"] is True
    assert evidence["source_sha_pins_unchanged"] is True
    assert evidence["factory_release"] is False
    assert evidence["human_windows_uat_claimed"] is False
    assert evidence["real_two_old_project_windows_gui_uat"] is False
    assert evidence["ui_full_operator_uat_claimed"] is False
    assert evidence["physical_absolute_position_grant"] is False
    assert "seeded" in evidence["scope"]
    refs = [evidence["primary_assertion"], *evidence["other_required_assertions"]]
    assert len(refs) >= 6 and len(set(refs)) == len(refs)
    assert refs[0] == (
        "tests/test_issue1504_ac32_original_inner_tk_x_undo.py"
        "::test_ac32_original_inner_tk_remove_reports_two_real_x_resets_and_undo_restores"
    )
    assert (
        "tests/test_issue1504_ac32_original_inner_tk_x_undo.py"
        "::test_ac32_original_inner_cancel_after_pending_x_change_never_writes_candidate"
    ) in refs
    for name in refs:
        path, test = name.split("::")
        assert PYTEST_PATHS.count(path) == 1, name
        functions = [
            n for n in ast.parse((ROOT / path).read_text(encoding="utf-8")).body
            if isinstance(n, ast.FunctionDef) and n.name == test
        ]
        assert len(functions) == 1, name
        assert any(isinstance(x, ast.Assert) for x in ast.walk(functions[0])), name
    assert "Windows" in row["current_scope_remaining_evidence"]


def test_ac18_original_tk_one_tier_and_unapproved_xy_are_scoped_not_factory_signed():
    """Guard the *real* Tk event and its nonmanufacturing datum evidence."""
    import ast
    from tools.product_ci_regression import PYTEST_PATHS
    row = {r["id"]: r for r in _data()["records"]}["NFB-AC-18"]
    proof = row["acceptance_evidence"]
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    assert row["identified_test_functions"][0]["accepted"] is True
    assert row["identified_test_functions"][0]["path"] == (
        "tests/test_issue1504_ac18_original_tk_datum.py"
    )
    assert proof["factory_release"] is False
    assert proof["human_windows_uat_claimed"] is False
    assert proof["ui_full_operator_uat_claimed"] is False
    assert proof["real_two_old_project_windows_gui_uat"] is False
    assert proof["physical_absolute_position_grant"] is False
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    refs = [proof["primary_assertion"], *proof["other_required_assertions"]]
    assert len(refs) >= 6 and len(set(refs)) == len(refs)
    assert refs[0].endswith("::test_ac18_original_tk_single_layer_count_changes_only_real_draft_and_undo")
    assert any("::test_ac18_real_tk_nominal_pitch_not_world_x_and_non1100_y_shows_unknown" in r for r in refs)
    for exact in refs:
        path,fn = exact.split("::")
        assert PYTEST_PATHS.count(path) == 1, exact
        nodes = [v for v in ast.parse((ROOT/path).read_text(encoding="utf-8")).body
                 if isinstance(v, ast.FunctionDef) and v.name == fn]
        assert len(nodes) == 1, exact
        assert any(isinstance(v, ast.Assert) for v in ast.walk(nodes[0])), exact
    assert "Windows" in row["current_scope_remaining_evidence"]


def test_ac03_native_csv_preview_signoff_requires_real_tk_and_legacy_source_negative_tests():
    """One current-scope AC; no permission for world-X/Y or full factory NC."""
    from tools.product_ci_regression import PYTEST_PATHS
    import ast
    row = {r["id"]: r for r in _data()["records"]}["NFB-AC-03"]
    evidence = row["acceptance_evidence"]
    primary = "tests/test_issue1504_ac03_ac15_native_source_panel.py::test_ac03_original_inner_tk_preview_visible_with_zoom_pan_reset_and_no_write"
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["accepted"] is True
    assert evidence["primary_assertion"] == primary
    assert evidence["original_ac_text_unchanged"] is True
    assert evidence["source_sha_pins_unchanged"] is True
    assert row["current_scope_correction_20261021"]["supersedes_original_interpretation_only"] is True
    assert evidence["current_csv_v5_primary_model_authority"] is True
    assert len(evidence["other_required_assertions"]) >= 4
    for field in ("factory_release", "human_windows_uat_claimed",
                  "ui_full_operator_uat_claimed", "real_two_old_project_windows_gui_uat",
                  "physical_absolute_position_grant", "other_ac_signoff_implied",
                  "integrated_localx_claimed"):
        assert evidence[field] is False
    for witness in [primary, *evidence["other_required_assertions"]]:
        path, name = witness.split("::", 1)
        assert path in PYTEST_PATHS
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        assert len(matches) == 1
        assert any(isinstance(n, ast.Assert) for n in ast.walk(matches[0]))
    assert row["identified_test_functions"] == [{
        "path": primary.split("::", 1)[0],
        "test_name": primary.split("::", 1)[1],
        "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS",
        "accepted": True,
    }]


def test_ac15_scoped_source_performance_requires_real_tk_p95_and_no_3d_rebuild():
    """Current V5 source-only claim: not Windows UAT or unspecified DXF speed."""
    import ast
    from tools.product_ci_regression import PYTEST_PATHS
    row = {r["id"]: r for r in _data()["records"]}["NFB-AC-15"]
    evidence = row["acceptance_evidence"]
    native = "tests/test_issue1504_ac03_ac15_native_source_panel.py"
    name = "test_ac15_original_tk_two_model_highlight_has_bounded_latency_no_full_3d"
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    assert evidence["primary_assertion"] == native + "::" + name
    assert row["identified_test_functions"][0]["test_name"] == name
    assert row["identified_test_functions"][0]["accepted"] is True
    assert evidence["original_ac_text_unchanged"] is True
    assert evidence["source_sha_pins_unchanged"] is True
    assert evidence["source_scoped_latency_bound_ms"] == {
        "median_lt": 150, "p95_lt": 300, "sample_count": 24,
        "runner": "Linux Tk Xvfb",
    }
    assert evidence["measured_tk_global_reference_is_not_nfb_dxf_latency_proof"] is True
    assert evidence["exact_head_ci_and_tk_performance_required"] is True
    for field in ("factory_release", "human_windows_uat_claimed",
                  "ui_full_operator_uat_claimed", "real_two_old_project_windows_gui_uat",
                  "physical_absolute_position_grant", "other_ac_signoff_implied",
                  "integrated_localx_claimed"):
        assert evidence[field] is False
    proof_nodes = None
    for ref in [evidence["primary_assertion"], *evidence["other_required_assertions"]]:
        source, target = ref.split("::", 1)
        assert PYTEST_PATHS.count(source) == 1
        tree = ast.parse((ROOT / source).read_text(encoding="utf-8"))
        found = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == target]
        assert len(found) == 1
        assert any(isinstance(n, ast.Assert) for n in ast.walk(found[0]))
        if target == name:
            proof_nodes = list(ast.walk(found[0]))
    assert proof_nodes is not None
    call_names = {n.id for n in proof_nodes if isinstance(n, ast.Name)}
    assert {"perf_counter", "median", "Phase6FinalSceneRenderer",
            "Phase6FinalSceneViewAdapter"}.issubset(call_names)


def test_swt05_original_tk_csv_source_only_signoff_is_compatible_with_factory_hold():
    """Current CSV source preview/embedded transactions: never X/Y or MFG grant."""
    import ast
    from tools.product_ci_regression import PYTEST_PATHS
    r = {r["id"]: r for r in _data()["records"]}["SWT-AC-05"]
    e = r["acceptance_evidence"]
    primary = ("tests/test_issue1504_ac03_ac15_native_source_panel.py"
               "::test_swt05_embedded_original_hole_editor_cancel_then_confirm_stages_only")
    assert r["accepted"] is True
    assert r["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert r["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    assert r["identified_test_functions"][0]["test_name"] == primary.split("::")[1]
    assert r["identified_test_functions"][0]["accepted"] is True
    assert e["primary_assertion"] == primary
    assert e["original_ac_text_unchanged"] is True
    assert e["source_sha_pins_unchanged"] is True
    assert e["current_csv_v5_authority"] is True
    assert "CSV V5" in r["current_source_interpretation_20261024"]
    for key in ("factory_release", "human_windows_uat_claimed",
                "ui_full_operator_uat_claimed", "real_two_old_project_windows_gui_uat",
                "physical_absolute_position_grant", "other_ac_signoff_implied",
                "integrated_localx_claimed"):
        assert e[key] is False
    expected_tests = [primary, *e["other_required_assertions"]]
    assert len(expected_tests) >= 7 and len(set(expected_tests)) == len(expected_tests)
    for name in expected_tests:
        source, function = name.split("::", 1)
        assert PYTEST_PATHS.count(source) == 1
        definitions = [f for f in ast.parse((ROOT / source).read_text(encoding="utf-8")).body
                       if isinstance(f, ast.FunctionDef) and f.name == function]
        assert len(definitions) == 1, name
        assert any(isinstance(node, ast.Assert) for node in ast.walk(definitions[0])), name



def test_swt22_full_ac_requires_real_native_ear_side_export_and_negative_manufacturing():
    """Signed SWT-22 must execute real GUI/DXF plus real fail-closed paths.

    A source-path existence check alone is never a signed original AC.
    These product runtime witnesses must ALL be scheduled by Product CI.
    """
    row = next(r for r in _data()["records"] if r["id"] == "SWT-AC-22")
    from tools.product_ci_regression import PYTEST_PATHS

    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    proof = row["acceptance_evidence"]
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    assert proof["factory_release"] is False
    assert proof["welding_workmanship_certified"] is False
    assert proof["pad_unconditional_approved"] is False
    assert proof["human_windows_uat_claimed"] is False
    assert proof["real_two_old_project_windows_gui_uat"] is False
    assert proof["other_ac_signoff_implied"] is False

    references = (
        proof["primary_assertion"],
        *proof["other_required_assertions"],
    )
    for reference in references:
        path, test_name = reference.split("::", 1)
        assert path in PYTEST_PATHS, reference
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert test_name in {
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, reference

    # Original Tk path must consume the actual GUI export action, reread
    # produced DXF bytes, and genuinely reopen a saved .p6fold project.
    native = (ROOT / row["identified_test_functions"][0]["path"]).read_text(
        encoding="utf-8"
    )
    assert "designer.output_export_button.invoke()" in native
    assert "ezdxf.readfile(path)" in native
    assert "calc.load_phase6_project(saved_path, open_designer=True)" in native

    # A false 'approved' field must NEVER authorize PAD/EAR drawings.
    negative = (ROOT / "tests/test_issue1503_deferred_pad_ear_manufacturing.py").read_text(
        encoding="utf-8"
    )
    assert "NFB_PAD_EAR_PHYSICAL_EVIDENCE_UNAPPROVED" in negative
    assert "assert calls==[]" in negative



def test_swt10_native_one_live_config_proves_csv_holes_and_ear_side_source():
    """SWT-10 requires ONE real source-driven GUI→CUTTING/DXF→EAR/SIDE chain."""
    row = next(r for r in _data()["records"] if r["id"] == "SWT-AC-10")
    from tools.product_ci_regression import PYTEST_PATHS
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    assert row["assertion_review_state"] == "FULL_AC_AUTOMATED_SIGNED"
    assert row["historical_pre_current_review"]["status"] == (
        "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC"
    )
    proof = row["acceptance_evidence"]
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    assert proof["factory_release"] is False
    assert proof["human_windows_uat_claimed"] is False
    assert proof["welding_workmanship_certified"] is False
    assert proof["physical_absolute_position_grant"] is False
    assert proof["other_ac_signoff_implied"] is False
    assert len(proof["requirement_witnesses"]) == 2
    for witness in (proof["primary_assertion"], *proof["other_required_assertions"]):
        path, name = witness.split("::", 1)
        assert PYTEST_PATHS.count(path) == 1, witness
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert name in {
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, witness

    # Prevent accidental rollback from actual source centres and reopened
    # operator DXF to mere 'two inner doors' metadata or fake preview counts.
    original_gui = (
        ROOT / row["identified_test_functions"][0]["path"]
    ).read_text(encoding="utf-8")
    for actual_seam in (
        "designer.output_export_button.invoke()",
        "_submitted_csv_holes(current)",
        "trial_configured_nfb_v5_inner_door_render_data(",
        "source_info[\"csv_sha256\"] == source_hash",
        "actual_door = ezdxf.readfile(actual_door_file).modelspace()",
        "physical_bounds(tuple((float(x), float(y))",
        "SWT10_SOURCE_NFB_HOLE_CENTRE_OR_SIZE_NOT_IN_ORIGINAL_DXF",
        "derive_receiving_ear_side_contact_from_formed_skin",
        "RELOADED_LEFT_RIGHT_EAR_MARKING_MISSING",
    ):
        assert actual_seam in original_gui, actual_seam


def test_ac38_current_physical_dependency_signoff_requires_runtime_guards():
    """Never let a source inventory or a fake middle-only fixture sign AC38."""
    row = next(r for r in _data()["records"] if r["id"] == "NFB-AC-38")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["historical_pre_current_review"]["status"] == (
        "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC"
    )
    assert row["requirement"].startswith("已提交配置對應內門必相依")
    proof = row["acceptance_evidence"]
    for limitation in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
    ):
        assert proof[limitation] is False
    assert len(proof["requirement_witnesses"]) == 3
    from tools.product_ci_regression import PYTEST_PATHS
    for ref in (proof["primary_assertion"], *proof["other_required_assertions"]):
        path, name = ref.split("::", 1)
        assert path in PYTEST_PATHS
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert name in {
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, ref
    primary = (ROOT / row["identified_test_functions"][0]["path"]).read_text(
        encoding="utf-8"
    )
    for actual_assertion in (
        "test_ac38_current_receiving_source_guards_only_actual_parts_and_side",
        "inspect_nfb_dxf_source(source)",
        "set(decisions) == {\"inner1\", \"base1\", \"side1\"}",
        "manifest.actual_export_count == expected_count",
        "manifest.require_export((\"side1\",), partial=True)",
        "SOURCE_REPLACED",
        "stale.authorized_part_ids == (\"side1\",)",
        "ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED",
    ):
        assert actual_assertion in primary
    native = (
        ROOT / "tests/test_issue1503_single_gui_real_tier_2d3d.py"
    ).read_text(encoding="utf-8")
    assert "designer.output_export_button.invoke()" in native
    assert "derive_receiving_ear_side_contact_from_formed_skin" in native
    assert "ezdxf.readfile(path)" in native


def test_swt21_full_current_source_dependency_requires_pending_x_and_absent_source_proofs():
    """No AC21 signoff without numeric state, old datum and physical DXF gates."""
    row = next(x for x in _data()["records"] if x["id"] == "SWT-AC-21")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    assert row["historical_pre_current_review"]["status"] == (
        "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC"
    )
    proof = row["acceptance_evidence"]
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    assert len(proof["requirement_witnesses"]) == 2
    for key in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
    ):
        assert proof[key] is False
    from tools.product_ci_regression import PYTEST_PATHS
    for ref in (proof["primary_assertion"], *proof["other_required_assertions"]):
        path, name = ref.split("::", 1)
        assert path in PYTEST_PATHS
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert name in {
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, ref

    source = (ROOT / "ae_engine/receiving_nfb_export_manifest.py").read_text(
        encoding="utf-8"
    )
    assert 'normalized_config = normalize_nfb_saved_fields(saved_bay)["nfb_config"]' in source
    assert 'hole["manual_x_state"] != "CONFIRMED"' in source
    assert "_verify_hole_locations(normalized_config,verified_inner_door)" in source
    tests = (ROOT / row["identified_test_functions"][0]["path"]).read_text(
        encoding="utf-8"
    )
    for witness in (
        "test_swt21_unconfirmed_saved_world_x_never_reuses_old_manufacturing_proof",
        "RECONFIRM_REQUIRED",
        "test_swt21_saved_x_datum_drift_is_normalized_before_manufacturing",
        "test_swt21_missing_committed_source_or_slot_never_authorizes_dependent_parts",
        "manifest.authorized_part_ids == (\"side1\",)",
        "SAVED_NFBCONFIG_DIFFERS_FROM_VERIFIED_CUTTING",
    ):
        assert witness in tests


def test_ac44_source_scoped_partial_never_implies_full_or_factory_approval():
    row = next(r for r in _data()["records"] if r["id"] == "NFB-AC-44")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    assert row["historical_pre_current_review"]["status"] == (
        "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC"
    )
    proof = row["acceptance_evidence"]
    for limitation in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
    ):
        assert proof[limitation] is False
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    assert len(proof["requirement_witnesses"]) == 2
    from tools.product_ci_regression import PYTEST_PATHS
    for ref in (proof["primary_assertion"], *proof["other_required_assertions"]):
        path, test_name = ref.split("::", 1)
        assert path in PYTEST_PATHS, ref
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert test_name in {
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, ref
    source = (ROOT / row["identified_test_functions"][0]["path"]).read_text(
        encoding="utf-8"
    )
    for witness in (
        "test_ac44_live_source_partial_must_not_masquerade_as_whole_export",
        "inspect_nfb_dxf_source(source)",
        "source_missing",
        "no_upper",
        "upper_and_base",
        "unknown_aci",
        "manifest.authorized_part_ids == allowed",
        "manifest.held_actual_count == 6 - count",
        "manifest.require_export(allowed, partial=False)",
        "NOT_VALIDATED_AS_COMPLETE_NFB_ASSEMBLY",
    ):
        assert witness in source, witness
    native = (ROOT / "tests/test_issue1503_single_gui_real_tier_2d3d.py").read_text(
        encoding="utf-8"
    )
    assert "designer.output_export_button.invoke()" in native
    assert "ezdxf.readfile(path)" in native


def test_nfb_ac28_signed_only_when_actual_native_two_unit_bay_is_atomic():
    """Keep GUI source confirmation distinct from any factory MFG2 signoff."""
    row = next(x for x in _data()["records"] if x["id"] == "NFB-AC-28")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["evidence_level"] == "FULL_AC_ASSERTION_AUDITED"
    assert row["historical_pre_current_review"]["status"] == "EVIDENCE_CANDIDATE_ONLY"
    proof = row["acceptance_evidence"]
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    assert len(proof["requirement_witnesses"]) == 3
    for key in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "integrated_localx_claimed", "other_ac_signoff_implied",
        "physical_absolute_position_grant",
        "source_fixture_manufacturer_original_certified",
    ):
        assert proof[key] is False
    assert proof["source_fixture_typed_not_physical_dxf_certificate"] is True
    from tools.product_ci_regression import PYTEST_PATHS
    for ref in (proof["primary_assertion"], *proof["other_required_assertions"]):
        path, name = ref.split("::", 1)
        assert path in PYTEST_PATHS, ref
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert name in {
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, ref
    native = (
        ROOT / "tests/test_issue1500_nfb_operator_gui_transactions.py"
    ).read_text(encoding="utf-8")
    for witness in (
        'second_unit["physical_hole_id"] = "nfb:0:slot2"',
        'assert "nfb:0:slot2" in recorded[0]',
        'assert "X 未配置 → 180 mm" in recorded[0]',
        'assert adapter.layout == committed',
        'assert "受影響 NFB／X 基準差異" in recorded[0]',
    ):
        assert witness in native, witness
    atomic = (ROOT / "tests/test_issue1500_nfb_transactions.py").read_text(
        encoding="utf-8"
    )
    for witness in (
        "test_ac28_two_units_one_bay_one_invalid_cannot_batch_confirm",
        '"unverified_x", "wrong_x", "wrong_rotation", "wrong_physical_id"',
        "assert callbacks == []",
        "assert original == frozen",
    ):
        assert witness in atomic, witness
    bridge = (
        ROOT / "ae_engine/receiving_nfb_ui1b_bridge.py"
    ).read_text(encoding="utf-8")
    gui = (
        ROOT / "gui_modules/application/fold_designer_composition_receiving.py"
    ).read_text(encoding="utf-8")
    assert "return adapter.submit_nfb_to_bays(" in bridge
    assert "result=submit_live_verified_nfb(" in gui
    assert 'return {"state": state, "stage_verified": stage_verified,' in gui

def test_swt32_current_raw_dxf_to_actual_check_signoff_requires_exact_witness():
    """Historic raw DXF inventory is diagnostic; no factory or phantom plate."""
    row = next(x for x in _data()["records"] if x["id"] == "SWT-AC-32")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["historical_pre_current_review"]["status"] == (
        "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC"
    )
    assert row["requirement"].startswith("真 DXF Color 30／150")
    e = row["acceptance_evidence"]
    assert len(e["requirement_witnesses"]) == 3
    for key in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
        "integrated_localx_claimed", "formal_x_published",
    ):
        assert e[key] is False
    assert e["original_ac_text_unchanged"] is True
    assert e["source_sha_pins_unchanged"] is True
    from tools.product_ci_regression import PYTEST_PATHS
    for ref in (e["primary_assertion"], *e["other_required_assertions"]):
        file_path, test_name = ref.split("::", 1)
        assert file_path in PYTEST_PATHS
        tree = ast.parse((ROOT / file_path).read_text(encoding="utf-8"))
        assert test_name in {
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, ref
    test = (ROOT / row["identified_test_functions"][0]["path"]).read_text(
        encoding="utf-8"
    )
    for required in (
        "test_swt32_same_original_dxf_brand_pins_colors_real_part_counts_and_sha_hold",
        "build_source_coverage_report(",
        "inspect_nfb_dxf_source(source)",
        "SOURCE_IDENTITY_MISMATCH_UNKNOWN",
        "None, None, None",
        "manifest.actual_export_count == 5",
        "manifest.held_actual_count == 1",
        "stale.actual_export_count == 3",
        "stale.held_actual_count == 3",
        "ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED",
    ):
        assert required in test


def test_ac55_current_raw_dxf_source_to_operator_manifest_signoff_is_not_fake_mfg2():
    """Only source-owned physical counts and live warnings qualify, not MFG2."""
    row = next(r for r in _data()["records"] if r["id"] == "NFB-AC-55")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["historical_pre_current_review"]["status"] == (
        "SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC"
    )
    assert row["requirement"].startswith("逐型號盤點真實 NFB DXF")
    e = row["acceptance_evidence"]
    assert e["original_ac_text_unchanged"] is True
    assert e["source_sha_pins_unchanged"] is True
    assert len(e["requirement_witnesses"]) == 3
    for name in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "all_24_manufacturer_original_raw_dxfs_certified",
        "native_windows_operator_original_old_project_tested",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
        "integrated_localx_claimed", "formal_x_published",
    ):
        assert e[name] is False
    from tools.product_ci_regression import PYTEST_PATHS
    for ref in (e["primary_assertion"], *e["other_required_assertions"]):
        path, test_name = ref.split("::", 1)
        assert path in PYTEST_PATHS
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert test_name in {
            x.name for x in tree.body
            if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, ref
    body = (ROOT / "tests/test_issue1501_nfb_manifest_ui.py").read_text(
        encoding="utf-8"
    )
    for proof in (
        "test_ac55_one_raw_dxf_inventory_reaches_current_bay_operator_warning_and_export_gate",
        "build_source_coverage_report(",
        "inspect_nfb_dxf_source(source)",
        "derive_nfb_partial_export_manifest(**options)",
        "highlighted_nfb_manifest_lines(",
        "observed[\"manufacturing_ready\"] is False",
        "manifest",
        "SOURCE_IDENTITY_MISMATCH_UNKNOWN",
        "None, None, None",
        "stale.actual_export_count == 3",
        "ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED",
        "SOURCE_MISSING_UNKNOWN",
    ):
        assert proof in body


def test_swt16_current_two_unit_batch_signed_only_with_true_manufacturing_collision_proof():
    """No batch X confirmation can bypass either unit's source geometry."""
    row = next(x for x in _data()["records"] if x["id"] == "SWT-AC-16")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["historical_pre_current_review"]["status"] == "EVIDENCE_CANDIDATE_ONLY"
    proof = row["acceptance_evidence"]
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    assert len(proof["requirement_witnesses"]) == 2
    for name in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "integrated_localx_claimed", "formal_x_published",
        "source_fixture_manufacturer_original_certified",
        "all_model_width_x_certified", "original_windows_native_operator_manufacturing_tested",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
    ):
        assert proof[name] is False
    from tools.product_ci_regression import PYTEST_PATHS
    for ref in (proof["primary_assertion"], *proof["other_required_assertions"]):
        path, name = ref.split("::", 1)
        assert path in PYTEST_PATHS
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert name in {
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, ref
    source = (ROOT / "tests/test_issue1500_nfb_transactions.py").read_text(
        encoding="utf-8"
    )
    for marker in (
        "test_swt16_two_real_source_cuttings_require_independent_x_reconfirm_and_collision_gate",
        "configured_nfb_inner_door_render_data(",
        "inspect_nfb_dxf_source(source)",
        '"RECONFIRM_REQUIRED"',
        'assert consent == []',
        'assert len(review[0].operator_x_changes) == 2',
        'assert len(outlines) == 3',
        'assert undo_nfb_transaction(committed.layout, committed.receipt) == frozen',
        "save_configured_nfb_inner_door_dxf(",
        "assert not invalid_target.exists()",
    ):
        assert marker in source


def test_ac23_native_reconfirmed_reloaded_manufacturing_scope_has_real_witnesses():
    """A saved X numeral alone can never become approved MFG-1 geometry."""
    row = next(r for r in _data()["records"] if r["id"] == "NFB-AC-23")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["historical_pre_current_review"]["status"] == "EVIDENCE_CANDIDATE_ONLY"
    proof = row["acceptance_evidence"]
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    assert len(proof["requirement_witnesses"]) == 3
    for key in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "source_fixture_manufacturer_original_certified",
        "all_model_width_x_certified", "original_windows_native_operator_manufacturing_tested",
        "integrated_localx_claimed", "formal_x_published",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
    ):
        assert proof[key] is False
    from tools.product_ci_regression import PYTEST_PATHS
    for witness in (proof["primary_assertion"], *proof["other_required_assertions"]):
        path, name = witness.split("::", 1)
        assert path in PYTEST_PATHS, witness
        parsed = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        assert name in {
            n.name for n in parsed.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }, witness
    source = (ROOT / "tests/test_issue1500_nfb_operator_gui_transactions.py").read_text(
        encoding="utf-8"
    )
    for required in (
        "test_ac23_reopened_stale_world_x_native_tk_reconfirm_restores_only_source_verified_dxf",
        'stale_hole["manual_x_state"] == "RECONFIRM_REQUIRED"',
        "read_project(before_file)",
        'assert adapter.layout == before_cancel',
        'assert "確認狀態變更" in previews[0]',
        '"manual_x_state"] == "CONFIRMED"',
        "derive_nfb_partial_export_manifest(",
        "save_configured_nfb_inner_door_dxf(",
        "ezdxf.readfile(output)",
        "SOURCE_REPLACED",
        "assert revoked.authorized_part_ids ==",
    ):
        assert required in source, required


def test_all_current_nfb_v5_source_supersessions_keep_88_originals_and_legacy_scope():
    """#1504 current 2026-10-26: V5 model input is CSV, not mandatory old DXF.

    Correct historic reading across signed AND pending ACs; never convert a
    preview or a DXF-free input contract into unearned manufacturing GREEN.
    Preserve original AC text, all 88 identities and human old-project gates.
    """
    obj = _data()
    policy = obj["current_nfb_source_policy_20261026"]
    assert policy["schema"] == "WHD_NFB_CURRENT_V5_LEGACY_SOURCE_SEPARATION_V1"
    assert policy["date_taiwan"] == "2026-10-26"
    assert policy["authority_issues"] == [1502, 1504]
    assert policy["current_model_identity"] == "nfbv5:<brand>:<model>"
    assert "NFB數值規格.csv" in policy["current_model_source"]
    assert "legacy" in policy["legacy_dxf_scope"]
    assert policy["acceptance_tally_unchanged"] is True
    assert policy["legacy_backcompat_preserved"] is True
    assert policy["original_88_requirements_unchanged"] is True
    assert policy["windows_gui_gate_untouched"] is True
    assert policy["formal_x_requires"] == "/推推"
    assert len(policy["obsolete_global_prerequisites"]) >= 5
    assert any("ARC/CIRCLE" in item for item in policy["obsolete_global_prerequisites"])
    assert any("Color30/150/212" in item for item in policy["obsolete_global_prerequisites"])
    assert any("DXF" in item for item in policy["manufacturing_requirements"])
    assert any("fail closed" in item for item in policy["manufacturing_requirements"])
    rows = {row["id"]: row for row in obj["records"]}
    groups = policy["affected_ac_route_groups"]
    assert set(groups) == {
        "CURRENT_V5_SELECTION_PREVIEW",
        "CURRENT_V5_MAIN_APERTURE_PIVOT",
        "CURRENT_V5_POSITION_DATUM",
        "CURRENT_V5_PART_DEPENDENCY_EXPORT",
        "LEGACY_PROJECT_GUI_ONLY_NOT_CURRENT_V5_SOURCE_REQUIREMENT",
    }
    all_ids = [id for ids in groups.values() for id in ids]
    assert len(all_ids) == len(set(all_ids)) == 34
    assert {"NFB-AC-11", "NFB-AC-51", "SWT-AC-27", "SWT-AC-30"} <= set(all_ids)
    assert {
        "NFB-AC-03", "NFB-AC-38", "NFB-AC-55", "SWT-AC-05",
        "SWT-AC-21", "SWT-AC-32",
    } <= set(all_ids)
    assert set(all_ids) <= set(rows)
    for route_class, ids in groups.items():
        for ident in ids:
            ac = rows[ident]
            correction = ac["current_source_authority_20261026"]
            assert correction["route_class"] == route_class
            assert correction["legacy_dxf_requirement_for_current_v5"] is False
            assert correction["physical_dxfs_must_be_verified_when_exporting"] is True
            assert correction["original_requirement_text_preserved"] is True
            assert correction["original_status_preserved"] is True
            assert "NFBCONFIG" in correction["authority"]
            assert any(token in correction["scope_note"] for token in ("legacy", "Legacy", "DXF", "CSV"))
    current_runtime = "tests/test_issue1502_current_csv_original_pair_dxf.py"
    for ident in ("NFB-AC-11", "NFB-AC-51", "SWT-AC-27", "SWT-AC-30"):
        clause = rows[ident]["current_source_authority_20261026"]
        assert clause["current_v5_positive_witness"] == (
            current_runtime +
            "::test_ac11_ac51_swt27_swt30_current_v5_never_needs_legacy_model_dxf_input"
        )
        assert clause["current_v5_fail_closed_witness"] == (
            current_runtime +
            "::test_ac11_ac51_current_v5_missing_numeric_model_fails_without_legacy_fallback"
        )
        assert clause["current_v5_witness_is_not_full_ac_signoff"] is (
            ident not in ("NFB-AC-51", "SWT-AC-30")
        )
        assert current_runtime in rows[ident]["regression_candidates"]
    for ident in ("NFB-AC-11", "NFB-AC-51"):
        record = rows[ident]
        if ident == "NFB-AC-11":
            assert record["identified_test_functions"][0]["path"] == current_runtime
        else:
            assert record["identified_test_functions"][0]["path"] == (
                "tests/test_issue1504_ac03_ac15_native_source_panel.py"
            )
        assert record["historical_legacy_witness_before_20261026"]["path"].endswith(
            "test_issue1496_nfb_dxf_source.py"
        )
        if ident == "NFB-AC-11" and record["accepted"]:
            assert record["identified_test_functions"][0]["test_name"] == (
                "test_ac11_current_numeric_v5_two_models_real_pivot_and_upper_door_lower_base_dxf"
            )
            proof = record["acceptance_evidence"]
            assert proof["original_ac_text_unchanged"] is True
            assert proof["current_csv_v5_authority_explicit"] is True
            assert proof["original_legacy_dxf_optional_for_v5"] is True
            assert proof["physical_pivot_and_four_rotations_verified"] is True
            assert proof["real_two_model_door_base_output_reopened"] is True
            assert proof["factory_release"] is False
            assert proof["physical_absolute_position_grant"] is False
            assert proof["human_windows_uat_claimed"] is False
        elif ident == "NFB-AC-51" and record["accepted"]:
            proof = record["acceptance_evidence"]
            assert record["identified_test_functions"][0]["test_name"] == (
                "test_ac51_swt30_real_assigned_list_event_consumes_only_matching_export_scope"
            )
            assert proof["native_tk_assigned_callback_verified"] is True
            assert proof["physical_output_dxf_reopen_verified"] is True
            assert proof["unverified_nominal_groups_preview_only"] is True
            assert proof["factory_release"] is False
            assert proof["other_w_n_y_approved"] is False
        else:
            assert record["identified_test_functions"][0]["accepted"] is False
    if rows["NFB-AC-11"]["accepted"]:
        assert rows["NFB-AC-11"]["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert rows["NFB-AC-11"]["acceptance_evidence"][
            "other_w_n_y_approved"
        ] is False
        assert rows["NFB-AC-11"]["acceptance_evidence"][
            "other_ac_signoff_implied"
        ] is False
    # Current V5 input audit must not silently waive the remaining independent
    # positioning, source-drift, old-project GUI and production gates.
    for ident in ("NFB-AC-51", "SWT-AC-30"):
        entry = rows[ident]
        if entry["accepted"]:
            assert entry["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
            proof = entry["acceptance_evidence"]
            assert proof["native_tk_assigned_callback_verified"] is True
            assert proof["original_ac_text_unchanged"] is True
            assert proof["scope_drifts_fail_closed"] is True
            assert proof["other_w_n_y_approved"] is False
            assert proof["factory_release"] is False
            assert proof["human_windows_uat_claimed"] is False
            assert len(proof["original_ac_clauses_audited"]) >= 3
        else:
            assert entry["status"] == "EVIDENCE_CANDIDATE_ONLY"
    swt27 = rows["SWT-AC-27"]
    assert swt27["accepted"] is True
    assert swt27["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert swt27["identified_test_functions"][0]["test_name"] == (
        "test_swt27_current_v5_single_x_and_three_row_x_are_true_physical_datums"
    )
    from tools.product_ci_regression import PYTEST_PATHS
    assert current_runtime in PYTEST_PATHS
    witness = swt27["acceptance_evidence"]
    assert witness["original_ac_text_unchanged"] is True
    assert witness["current_csv_v5_authority_explicit"] is True
    assert witness["physical_single_and_row_world_x_verified"] is True
    assert witness["actual_generated_door_base_output_reopened"] is True
    assert witness["blanket_mfg1_approval"] is False
    assert witness["other_w_n_y_approved"] is False
    assert witness["factory_release"] is False
    assert witness["human_windows_uat_claimed"] is False
    assert witness["formal_x_published"] is False
    assert len(witness["original_ac_clauses_audited"]) >= 3
    assert len(witness["other_required_assertions"]) >= 5
    for full_test in (
        witness["primary_assertion"],
        *witness["other_required_assertions"],
    ):
        file, function = full_test.split("::")
        tree = ast.parse((ROOT / file).read_text(encoding="utf-8"))
        matches = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == function]
        assert len(matches) == 1 and any(
            isinstance(node, ast.Assert) for node in ast.walk(matches[0])
        )
    assert 0 < obj["counts"]["BLOCKED_1500_REAL_GUI"] <= 17
    assert obj["counts"]["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] >= 67
    assert sum(obj["counts"].values()) == 88
    assert obj["review_status"] == "INCOMPLETE_DO_NOT_CLOSE_1504_OR_1490"


def test_swt30_approved_w_n_y_model_datum_witness_is_scoped_not_all_nominal_groups():
    """Actual per-source positive and four V5 nominal negatives stay separate."""
    record = next(r for r in _data()["records"] if r["id"] == "SWT-AC-30")
    evidence = record["current_source_authority_20261026"]
    if record["accepted"]:
        assert record["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    else:
        assert record["status"] == "EVIDENCE_CANDIDATE_ONLY"
    positive = (
        "tests/test_issue1502_current_csv_original_pair_dxf.py::"
        "test_swt30_exact_committed_w_n_y_model_datum_has_real_dxf_but_cannot_leak_to_other_scope"
    )
    negative = (
        "tests/test_issue1504_ac30_current_nominal_no_fake_cutting.py::"
        "test_swt30_current_numeric_v5_four_nominal_groups_stay_preview_until_committed"
    )
    assert evidence["current_csv_scoped_part_only_witness"] == positive
    assert evidence["current_csv_nominal_preview_negative"] == negative
    assert evidence["current_v5_witness_is_not_full_ac_signoff"] is (not record["accepted"])
    if record["accepted"]:
        assert evidence["pending_full_ac_requirements"] == []
        assert len(evidence["historical_pending_full_ac_requirements_before_native_callback"]) == 2
        assert record["identified_test_functions"][0]["test_name"] == positive.split("::")[1]
        proof = record["acceptance_evidence"]
        assert proof["native_tk_assigned_callback_verified"] is True
        assert proof["exact_set_bay_model_x_y_rotation_scope_verified"] is True
        assert proof["no_permanent_model_manufacturing_registry"] is True
        assert proof["unverified_nominal_groups_preview_only"] is True
        assert proof["blanket_mfg1_approval"] is False
        assert proof["other_w_n_y_approved"] is False
    else:
        assert len(evidence["pending_full_ac_requirements"]) == 2
        assert record["identified_test_functions"][0]["test_name"] == positive.split("::")[1]
    for witness in (positive, negative):
        path, fn = witness.split("::")
        assert path in record["regression_candidates"]
        from tools.product_ci_regression import PYTEST_PATHS
        assert path in PYTEST_PATHS
        code = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        tests = {node.name: node for node in code.body
                 if isinstance(node, ast.FunctionDef)}
        assert fn in tests
        assert any(isinstance(node, ast.Assert)
                   for node in ast.walk(tests[fn]))



def test_ac51_swt30_signed_only_after_true_native_assigned_export_and_nominal_negatives():
    """Current V5 UI source scope green is not model-wide manufacturing."""
    records = {r["id"]: r for r in _data()["records"]}
    from tools.product_ci_regression import PYTEST_PATHS
    actual = (
        "tests/test_issue1504_ac03_ac15_native_source_panel.py::"
        "test_ac51_swt30_real_assigned_list_event_consumes_only_matching_export_scope"
    )
    for name in ("NFB-AC-51", "SWT-AC-30"):
        row = records[name]
        assert row["accepted"]
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["historical_pre_current_review"]["status"] == "EVIDENCE_CANDIDATE_ONLY"
        proof = row["acceptance_evidence"]
        assert actual in (proof["primary_assertion"], *proof["other_required_assertions"])
        assert proof["no_persisted_green"] and proof["scope_drifts_fail_closed"]
        assert proof["original_source_arc_circle_required_for_current_v5"] is False
        for reference in (proof["primary_assertion"], *proof["other_required_assertions"]):
            source, fn = reference.split("::")
            assert source in PYTEST_PATHS, reference
            tree = ast.parse((ROOT / source).read_text(encoding="utf-8"))
            matches = [node for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name == fn]
            assert len(matches) == 1 and any(
                isinstance(node, ast.Assert) for node in ast.walk(matches[0])
            )
    d = _data()
    assert d["counts"]["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] >= 71
    assert 0 < d["counts"]["BLOCKED_1500_REAL_GUI"] <= 17
    assert d["counts"]["EVIDENCE_CANDIDATE_ONLY"] == 0
    assert sum(d["counts"].values()) == 88


def test_cancelled_second_legacy_project_is_not_a_1500_1504_signoff_gate():
    """A missing Library 'B' is never a new condition for original §7 ACs.

    This corrects a later test-plan requirement, not the immutable v1.4 ACs.
    Passing this policy check does not sign any functional test by itself.
    """
    document = _data()
    policy = document["current_gui_acceptance_policy_20261026"]
    assert policy["schema"] == (
        "WHD_1504_GUI_FUNCTIONAL_EVIDENCE_NO_SECOND_PROJECT_GATE_V1"
    )
    assert policy["authority"] == "USER_DIRECTIVE_2026-10-26"
    assert policy["second_original_project_required"] is False
    assert policy["library_b_raw_bytes_required"] is False
    assert policy["legacy_project_count_is_acceptance_gate"] is False
    assert policy["signoff_not_implied"] is True
    assert policy["factory_release_not_implied"] is True
    assert policy["original_v14_ac_text_sha_unchanged"] is True
    assert policy["previous_71_signed_unchanged"] is True

    # Functional requirements remain: cancellation, copy/Undo, original
    # project persistence, actual views and scope-checked DXF re-opening.
    assert set(policy["functional_chain"]) == {
        "NFB_SELECT_CANCEL_CONFIRM",
        "SUBMIT_OR_REJECT_WITH_SOURCE_GUARD",
        "BAY_OR_VERSION_COPY_INDEPENDENT_AND_UNDO",
        "RESTORE_UNCONFIGURED_WITH_LEGACY_PRESERVED",
        "SAVE_RELOAD_ACTUAL_PROJECT",
        "PHYSICAL_2D_3D_SIDE_MARKING",
        "REAL_DXF_EXPORT_OR_FAIL_CLOSED_AND_REOPEN_CHECK_Q",
    }
    assert "Windows UAT" in policy["proof_rule"]
    assert "second old-project B" in document["current_gates_explanation"]["1500"]
    assert "no missing second original project" in (
        document["current_gates_explanation"]["1504"]
    )
    blocked = [r for r in document["records"]
               if r["status"] == "BLOCKED_1500_REAL_GUI"]
    assert len(blocked) == document["counts"]["BLOCKED_1500_REAL_GUI"] <= 17
    assert all(
        r["accepted"] is False
        and r["current_gui_requirement_20261026"]
        == "PER_AC_NATIVE_GUI_FUNCTIONAL_E2E_ONLY_NO_SECOND_OLD_PROJECT_B"
        for r in blocked
    )
    # No synthetic fixture may be turned into unearned human Windows approval.
    assert all(r["assertion_review_state"] ==
               "TEST_FUNCTION_IDENTITY_VERIFIED_NOT_FULL_AC" for r in blocked)

    fixture_test = (ROOT / "tests/test_issue1504_legacy_fixture_real_gui_gate_cycle.py").read_text(
        encoding="utf-8"
    )
    assert "second_library_project_executed" not in fixture_test
    assert "second Library file" not in fixture_test
    assert '"human_windows_uat_claimed": False' in fixture_test


def test_ac07_ac43_ac35_ac45_ac56_exact_native_tk_functional_signoff():
    """Only five original UI-1B ACs gain true test witnesses in this scope."""
    from tools.product_ci_regression import PYTEST_PATHS

    obj = _data()
    assert obj["counts"]["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] >= 76
    assert obj["counts"]["BLOCKED_1500_REAL_GUI"] <= 12
    expected = {
        "NFB-AC-07": "test_ac07_ac43_native_two_bay_copy_cancel_overwrite_independence_and_reopen",
        "NFB-AC-43": "test_ac07_ac43_native_two_bay_copy_cancel_overwrite_independence_and_reopen",
        "NFB-AC-35": "test_ac35_ac45_ac56_native_restore_cancel_undo_and_legacy_export_guard",
        "NFB-AC-45": "test_ac35_ac45_ac56_native_restore_cancel_undo_and_legacy_export_guard",
        "NFB-AC-56": "test_ac35_ac45_ac56_native_restore_cancel_undo_and_legacy_export_guard",
    }
    rows = {r["id"]: r for r in obj["records"]}
    primary = "tests/test_issue1500_nfb_operator_gui_transactions.py"
    assert primary in PYTEST_PATHS
    source = ast.parse((ROOT / primary).read_text(encoding="utf-8"))
    actual = {n.name: n for n in source.body if isinstance(n, ast.FunctionDef)}
    for ac, fn in expected.items():
        row = rows[ac]
        assert row["accepted"] is True and not row["blocking_issues"]
        assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
        assert row["historical_pre_current_review"]["status"] == "BLOCKED_1500_REAL_GUI"
        assert row["identified_test_functions"] == [{
            "path": primary, "test_name": fn,
            "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS",
            "accepted": True,
        }]
        proof = row["acceptance_evidence"]
        assert proof["primary_assertion"] == primary + "::" + fn
        assert len(proof["requirement_witnesses"]) >= 2
        assert len(proof["other_required_assertions"]) >= 3
        assert proof["original_ac_text_unchanged"] is True
        assert proof["source_sha_pins_unchanged"] is True
        assert proof["user_cancelled_second_legacy_project_prerequisite"] is True
        for limitation in (
            "factory_release", "unconditional_mfg2_release",
            "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
            "integrated_localx_claimed", "formal_x_published",
            "other_ac_signoff_implied", "physical_absolute_position_grant",
            "original_manufacturer_dxf_certified",
        ):
            assert proof[limitation] is False, (ac, limitation)
        assert fn in actual and any(isinstance(node, ast.Assert)
                                    for node in ast.walk(actual[fn]))
        for witness in [proof["primary_assertion"], *proof["other_required_assertions"]]:
            path, name = witness.split("::")
            assert path in PYTEST_PATHS, witness
            tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
            funcs = [node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name == name]
            assert len(funcs) == 1
            assert any(isinstance(node, ast.Assert)
                       for node in ast.walk(funcs[0]))

    remaining = [r["id"] for r in obj["records"] if not r["accepted"]]
    assert len(remaining) == obj["counts"]["BLOCKED_1500_REAL_GUI"]
    assert not any(ac in remaining for ac in expected)


def _test_function_has_assert_or_expected_exception(function):
    """Require a real Python assertion OR an explicit pytest.raises negative.

    A production fail-closed test commonly checks rejection using
    `with pytest.raises(..., match=...):` and has no bare `assert`.
    Inspect that concrete AST, rather than treating the test as assertion-free
    or replacing the exception contract with a meaningless dummy assert.
    """
    for node in ast.walk(function):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                call = item.context_expr
                if (isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "raises"
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == "pytest"
                        and call.args):
                    return True
    return False


def test_ac46_real_reopened_submitted_nfb_never_legacy_dxf_source_signoff():
    """The cancelled second project B is never a proxy for real AC-46 proof."""
    from tools.product_ci_regression import PYTEST_PATHS
    obj = _data()
    assert obj["counts"]["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] >= 77
    assert obj["counts"]["BLOCKED_1500_REAL_GUI"] <= 11
    row = next(r for r in obj["records"] if r["id"] == "NFB-AC-46")
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["accepted"] is True and not row["blocking_issues"]
    assert row["historical_pre_current_review"]["status"] == "BLOCKED_1500_REAL_GUI"
    proof = row["acceptance_evidence"]
    primary = (
        "tests/test_issue1504_legacy_fixture_real_gui_gate_cycle.py"
        "::test_ac46_saved_submitted_nfb_is_never_silently_legacy_after_gui_reload"
    )
    assert proof["primary_assertion"] == primary
    assert row["identified_test_functions"] == [{
        "path": primary.split("::")[0],
        "test_name": primary.split("::")[1],
        "witness_scope": "FULL_AC_AUTOMATED_ASSERTIONS",
        "accepted": True,
    }]
    assert proof["no_staged_transient_mfg1_proof"] is True
    assert proof["sanitized_repository_legacy_input_only"] is True
    assert proof["user_cancelled_second_legacy_project_prerequisite"] is True
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    assert len(proof["requirement_witnesses"]) >= 3
    for label in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "integrated_localx_claimed", "formal_x_published",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
        "original_manufacturer_dxf_certified",
    ):
        assert proof[label] is False, label
    for witness in [primary, *proof["other_required_assertions"]]:
        filename, fn = witness.split("::")
        assert filename in PYTEST_PATHS, filename
        nodes = ast.parse((ROOT / filename).read_text(encoding="utf-8")).body
        matches = [n for n in nodes if isinstance(n, ast.FunctionDef)
                   and n.name == fn]
        assert len(matches) == 1
        assert _test_function_has_assert_or_expected_exception(matches[0]), witness


def test_ac53_versioned_mfg1_current_capability_requires_real_native_source():
    """A versioned MFG-1 receipt cannot be replaced by a GUI enable flag."""
    from tools.product_ci_regression import PYTEST_PATHS

    manifest = _data()
    assert manifest["counts"]["ACCEPTED_AUTOMATED_CURRENT_SCOPE"] >= 78
    assert manifest["counts"]["BLOCKED_1500_REAL_GUI"] <= 10
    row = next(r for r in manifest["records"] if r["id"] == "NFB-AC-53")
    assert row["accepted"] is True
    assert row["status"] == "ACCEPTED_AUTOMATED_CURRENT_SCOPE"
    assert row["historical_pre_current_review"]["status"] == "BLOCKED_1500_REAL_GUI"
    proof = row["acceptance_evidence"]
    assert proof["primary_assertion"] == (
        "tests/test_issue1500_nfb_ui1b_bridge.py"
        "::test_ac53_real_mfg1_verified_capability_is_bound_to_exact_version_and_readiness"
    )
    assert row["identified_test_functions"][0]["test_name"] == (
        "test_ac53_real_mfg1_verified_capability_is_bound_to_exact_version_and_readiness"
    )
    assert row["identified_test_functions"][0]["accepted"] is True
    assert len(proof["requirement_witnesses"]) == 3
    assert len(proof["other_required_assertions"]) >= 5
    assert proof["current_MFG1_source_fixture_is_test_only"] is True
    assert proof["user_cancelled_second_legacy_project_prerequisite"] is True
    assert proof["original_ac_text_unchanged"] is True
    assert proof["source_sha_pins_unchanged"] is True
    for key in (
        "factory_release", "unconditional_mfg2_release",
        "human_windows_uat_claimed", "real_two_old_project_windows_gui_uat",
        "integrated_localx_claimed", "formal_x_published",
        "other_ac_signoff_implied", "physical_absolute_position_grant",
        "original_manufacturer_dxf_certified",
    ):
        assert proof[key] is False, key
    for witness in [proof["primary_assertion"], *proof["other_required_assertions"]]:
        path, fn = witness.split("::")
        assert path in PYTEST_PATHS, path
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        actual = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == fn]
        assert len(actual) == 1, witness
        assert _test_function_has_assert_or_expected_exception(actual[0]), witness
