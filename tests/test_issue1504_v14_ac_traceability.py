# -*- coding: utf-8 -*-
"""#1504 fail-closed machine audit of the two approved NFB v1.4 AC tables.

Only traceability is delivered by this check. A test filename is NOT proof
that an AC's specific assertion passed, and no item may claim acceptance
while #1500 real-source GUI or #1503 independent PAD work remains open.
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
        assert row["evidence_level"] == "PATH_EXISTS_NOT_ASSERTION_AUDITED"
        assert row["accepted"] is False
        assert row["status"] in NEEDS
        assert row["status"] not in ("PASS", "GREEN", "CLOSED", "READY")


def test_open_real_gui_physical_and_deferred_work_never_marked_pass():
    data = _data()
    assert set(data["open_gates"]) == {1500, 1503, 1504}
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
            assert r["blocking_issues"] == [1503]
        else:
            assert not r["blocking_issues"]


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
    assert counts["EVIDENCE_CANDIDATE_ONLY"] == 53


def test_exact_function_witnesses_are_owner_aligned_real_definitions_not_pass_flags():
    data = _data()
    assert data["exact_test_function_witnesses_count"] == 88
    assert data["assertion_witness_note"]
    found = 0
    for item in data["records"]:
        witnesses = item["identified_test_functions"]
        state = item["assertion_review_state"]
        assert witnesses, item["id"]
        assert state == "TEST_FUNCTION_IDENTITY_VERIFIED_NOT_FULL_AC"
        assert len(witnesses) == 1  # exact function identity, not full AC proof
        for witness in witnesses:
            assert witness["path"] in item["regression_candidates"]
            assert witness["accepted"] is False
            assert witness["witness_scope"] == "PARTIAL_AUTOMATED_ASSERTIONS_ONLY"
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



def test_all_function_links_are_only_partial_and_no_factory_approval_is_implied():
    obj = _data()
    assert obj["exact_test_function_witnesses_review"].startswith(
        "88/88 FUNCTION_IDENTITIES_VERIFIED; 0/88 FULL_AC_ACCEPTED;"
    )
    for row in obj["records"]:
        assert row["assertion_review_state"] == (
            "TEST_FUNCTION_IDENTITY_VERIFIED_NOT_FULL_AC"
        )
        assert row["accepted"] is False
        assert row["identified_test_functions"][0]["accepted"] is False
    assert set(obj["open_gates"]) == {1500, 1503, 1504}


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
    assert all(row["accepted"] is False for row in obj["records"])

    # The human review must not silently retain an older X-centering claim.
    text = MANIFEST.with_suffix(".md").read_text(encoding="utf-8")
    assert "箱體中心 X=0" in text
    assert "孔距 **670 mm**" in text
    assert "T2/BEND23" in text and "EAR 已不是全部未驗" in text


def test_closed_1502_is_not_an_open_gate_and_original_ac_claims_stay_unsigned():
    """Closed localX scope cannot be counted as an open blocker or as 88 passes."""
    d = _data()
    assert d["assessed_on"] == "2026-10-21"
    assert 1502 not in d["open_gates"]
    assert d["counts"] == {
        "BLOCKED_1500_REAL_GUI": 17,
        "DEFERRED_PRODUCT_EVIDENCE": 4,
        "EVIDENCE_CANDIDATE_ONLY": 53,
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
    assert not any(r["accepted"] for r in d["records"])
    # Historical original AC-13 falsely held Base Plate Z fixed; preserve
    # the original phrase for traceability and declare its current override.
    row = {r["id"]: r for r in d["records"]}
    assert "底板不因 NFB 深度變更而位移" in row["NFB-AC-13"]["requirement"]
    assert "DOES move" in notes["NFB-AC-13"]
    assert "CURRENT" in notes["SWT-AC-09"]
