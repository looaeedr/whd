# -*- coding: utf-8 -*-
"""#1504 fail-closed machine audit of the two approved NFB v1.4 AC tables.

Only traceability is delivered by this check. A test filename is NOT proof
that an AC's specific assertion passed, and no item may claim acceptance
while #1500 real-source GUI or #1502 true physical DXF work remains open.
"""
from __future__ import annotations

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
    "BLOCKED_1502_PHYSICAL_MFG",
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
    assert set(data["open_gates"]) >= {1500, 1502, 1503, 1504}
    rows = {r["id"]: r for r in data["records"]}
    assert rows["NFB-AC-34"]["status"] == "BLOCKED_1500_REAL_GUI"
    assert rows["NFB-AC-14"]["status"] == "BLOCKED_1502_PHYSICAL_MFG"
    assert rows["NFB-AC-13"]["status"] == "DEFERRED_PRODUCT_EVIDENCE"
    assert rows["SWT-AC-12"]["owning_issues"] == [1504]
    for r in rows.values():
        if r["status"] == "BLOCKED_1500_REAL_GUI":
            assert r["blocking_issues"] == [1500]
        elif r["status"] == "BLOCKED_1502_PHYSICAL_MFG":
            assert r["blocking_issues"] == [1502]
        elif r["status"] == "DEFERRED_PRODUCT_EVIDENCE":
            assert r["blocking_issues"] == [1503]
        else:
            assert not r["blocking_issues"]


def test_manifest_review_summary_is_recomputed_from_records():
    obj = _data()
    counts = dict(Counter(r["status"] for r in obj["records"]))
    assert sum(counts.values()) == 88
    assert obj["counts"] == counts
    assert counts["DEFERRED_PRODUCT_EVIDENCE"] >= 3
    assert counts["BLOCKED_1500_REAL_GUI"] >= 1
    assert counts["BLOCKED_1502_PHYSICAL_MFG"] >= 1
