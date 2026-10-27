# -*- coding: utf-8 -*-
"""#1501 GUI display must not fabricate readiness or count blocked pieces."""
import pytest

from gui_modules.application.receiving_nfb_manifest_view import (
    nfb_manifest_display_lines, highlighted_nfb_manifest_lines,
)


def test_unconfigured_and_reloaded_without_original_are_not_marked_ready():
    assert nfb_manifest_display_lines({
        "status":"LEGACY","reason":"",
    })==("未配置 NFB｜依原有加工流程",)
    blocked=nfb_manifest_display_lines({
        "status":"BLOCKED","reason":"已提交但尚未重新驗證原始 DXF",
        "actual_export_count":0,
    })
    assert "尚不可匯出" in blocked[0]
    assert "未重新驗證" in blocked[0]


def test_shihlin_partial_count_lists_each_actual_piece_and_missing_dependency():
    preview={
        "status":"PARTIAL_ONLY","actual_export_count":2,
        "rows":[
            {"part_id":"inner:0","role":"INNER_DOOR","status":"READY",
             "actual_count":2,"may_export":True,"reasons":[]},
            {"part_id":"middle:0","role":"MIDDLE_PLATE","status":"BLOCKED",
             "actual_count":1,"may_export":False,
             "reasons":["MIDDLE_PLATE_NFB_COLOR150_UNVERIFIED"]},
        ],
        "unresolved_dependencies":["BASE_PLATE_PHYSICAL_ID_UNRESOLVED"],
    }
    lines=nfb_manifest_display_lines(preview)
    assert "可加工 2 片" in lines[0]
    assert "內門" not in lines[1]  # physical ID, not a made-up translated owner
    assert "inner:0" in lines[1] and "可出" in lines[1]
    assert "middle:0" in lines[2] and "受阻" in lines[2]
    assert "BASE_PLATE_PHYSICAL_ID_UNRESOLVED" in lines[3]
    assert "部分製造清單" in lines[-1]


def test_invalid_or_unverified_result_does_not_display_green():
    with pytest.raises(ValueError,match="unsupported"):
        nfb_manifest_display_lines({"status":"SYNTHETIC_READY"})
    with pytest.raises(TypeError):
        nfb_manifest_display_lines([])
    with pytest.raises(ValueError,match="row"):
        nfb_manifest_display_lines({
            "status":"PARTIAL_ONLY","actual_export_count":0,
            "rows":["fake-ready"],
        })


def test_manifest_display_rejects_forged_or_stale_piece_total():
    live={"status":"PARTIAL_ONLY","actual_export_count":2,
          "rows":[
              {"part_id":"door","role":"INNER_DOOR","status":"READY",
               "actual_count":2,"may_export":True,"reasons":[]},
              {"part_id":"middle","role":"MIDDLE_PLATE","status":"BLOCKED",
               "actual_count":1,"may_export":False,"reasons":["MFG2_BLOCKED"]},
          ]}
    assert "可加工 2 片" in nfb_manifest_display_lines(live)[0]
    with pytest.raises(ValueError,match="displayed count"):
        nfb_manifest_display_lines(dict(live,actual_export_count=3))
    with pytest.raises(ValueError,match="display count"):
        nfb_manifest_display_lines(dict(live,actual_export_count="2"))


def test_manifest_display_rejects_row_count_and_status_spoofing():
    original={"part_id":"door","role":"INNER_DOOR","status":"READY",
              "actual_count":2,"may_export":True,"reasons":[]}
    for changes,match in (
        ({"actual_count":True},"row count"),
        ({"actual_count":0},"row count"),
        ({"status":"BLOCKED"},"status/export mismatch"),
        ({"may_export":False},"status/export mismatch"),
        ({"status":"FORGED_READY"},"status not recognized"),
        ({"may_export":1},"export decision"),
    ):
        bad=dict(original,**changes)
        with pytest.raises(ValueError,match=match):
            nfb_manifest_display_lines({
                "status":"PARTIAL_ONLY","actual_export_count":2,
                "rows":[bad],
            })


def test_manifest_display_never_claims_whole_ready_when_held_or_unresolved():
    ready={"part_id":"inner","role":"INNER_DOOR","status":"READY",
           "actual_count":1,"may_export":True,"reasons":[]}
    held={"part_id":"base","role":"BASE_PLATE","status":"BLOCKED",
          "actual_count":1,"may_export":False,"reasons":["MFG2"]}
    for rows,unresolved in (
        ((ready,held),()),
        ((ready,),("PAD_ATTACHMENT_UNKNOWN",)),
    ):
        with pytest.raises(ValueError,match="full-ready display"):
            nfb_manifest_display_lines({
                "status":"WHOLE_READY","actual_export_count":1,
                "rows":rows,"unresolved_dependencies":unresolved,
            })


def _live_manifest_state(*, status="READY", version="v1"):
    if status=="LEGACY":
        return {"status":"LEGACY","reason":"unconfigured"}
    if status=="BLOCKED":
        return {"status":"BLOCKED","reason":"原始 DXF／Color150 已過期"}
    return {
        "status":"PARTIAL_ONLY","set_id":"set-A","bay_id":"bay-A",
        "version_id":version,"nfb_config_submitted":True,
        "actual_export_count":1,
        "rows":[
            {"part_id":"inner-physical","role":"INNER_DOOR",
             "status":"READY","actual_count":1,"may_export":True,"reasons":[]},
            {"part_id":"middle-physical","role":"MIDDLE_PLATE",
             "status":"BLOCKED","actual_count":1,"may_export":False,
             "reasons":["MIDDLE_PLATE_NFB_COLOR150_UNVERIFIED"]},
        ],
        "unresolved_dependencies":["PAD_EAR_DEFERRED"],
    }


def test_live_highlighted_manifest_discloses_real_scope_parts_and_blocked_reason():
    calls=[]
    def manifest(si,bi):
        calls.append((si,bi))
        return _live_manifest_state(
            status={0:"READY",1:"BLOCKED",2:"LEGACY"}[bi],
        )
    lines=highlighted_nfb_manifest_lines(
        {"manifest":manifest},0,(0,1,2),
    )
    assert calls==[(0,0),(0,1),(0,2)]
    assert any("第1套／第1連" in line and "版本 v1" in line
               and "Set set-A" in line and "Bay bay-A" in line
               for line in lines)
    assert any("inner-physical" in line and "可出" in line for line in lines)
    assert any("middle-physical" in line and "受阻" in line for line in lines)
    assert any("COLOR150_UNVERIFIED" in line for line in lines)
    assert any("第1套／第2連" in line and "尚不可匯出" in line for line in lines)
    assert any("第1套／第3連" in line and "未配置" in line for line in lines)
    assert any("部分製造清單" in line for line in lines)


def test_unconfigured_highlights_do_not_create_extra_nfb_operator_widgets():
    ports={"manifest":lambda si,bi: _live_manifest_state(status="LEGACY")}
    assert highlighted_nfb_manifest_lines(ports,0,(0,1))==()


def test_invalid_highlights_or_stale_physical_manifest_fail_closed():
    valid={"manifest":lambda si,bi:_live_manifest_state()}
    for selection in ((),(0,0),(True,),(-1,)):
        with pytest.raises(ValueError,match="Bay selection"):
            highlighted_nfb_manifest_lines(valid,0,selection)
    with pytest.raises(ValueError,match="Set index"):
        highlighted_nfb_manifest_lines(valid,True,(0,))
    for row in (
        {"status":"PARTIAL_ONLY","actual_export_count":1,
         "rows":[],"set_id":"set-A","bay_id":"bay-A","version_id":"v1"},
        dict(_live_manifest_state(),version_id=""),
        dict(_live_manifest_state(),actual_export_count=4),
    ):
        with pytest.raises(ValueError):
            highlighted_nfb_manifest_lines(
                {"manifest":lambda si,bi,record=row:record},0,(0,),
            )


def test_missing_source_status_never_becomes_approved_manufacturing_count():
    lines=highlighted_nfb_manifest_lines(
        {"manifest":lambda si,bi:{
            "status":"BLOCKED","reason":"SOURCE_REVALIDATION_REQUIRED",
        }},
        1,(3,),
    )
    assert len(lines)==1
    assert "第2套／第4連" in lines[0]
    assert "SOURCE_REVALIDATION_REQUIRED" in lines[0]
    assert "可加工" not in lines[0]


def test_committed_current_csv_manifest_is_scope_recheck_not_fake_mfg_green():
    """A verified CSV identity is not an old-DXF failure or factory approval."""
    receipt = {
        "status": "CSV_SOURCE_RECHECK_ONLY",
        "reason": "現行 CSV 已提交；內門＋底板部分 DXF 須於出圖時重新驗證",
        "actual_export_count": None,
        "rows": (),
        "unresolved_dependencies": (
            "WHOLE_CABINET_MANUFACTURING_NOT_APPROVED",
        ),
    }
    lines = nfb_manifest_display_lines(receipt)
    assert len(lines) == 1 and "現行 CSV NFB 已提交" in lines[0]
    assert "部分 DXF" in lines[0] and "再驗證" in lines[0]
    assert "不代表整箱可製造" in lines[0]
    assert "可加工 1 片" not in lines[0] and "已驗證板件" not in lines[0]
    combined = highlighted_nfb_manifest_lines(
        {"manifest": lambda si, bi: receipt}, 0, (1,),
    )
    assert len(combined) == 1
    assert "第1套／第2連" in combined[0]
    assert combined[0].endswith(lines[0])


@pytest.mark.parametrize("fake", (
    {"actual_export_count": 2},
    {"actual_export_count": 0},
    {"rows": [{"part_id": "fake", "may_export": True}]},
))
def test_current_csv_scope_recheck_rejects_fake_green_piece_counts(fake):
    receipt = {"status": "CSV_SOURCE_RECHECK_ONLY",
               "actual_export_count": None, "rows": ()}
    receipt.update(fake)
    with pytest.raises(ValueError, match="cannot claim manufactured parts"):
        nfb_manifest_display_lines(receipt)
    with pytest.raises(ValueError, match="cannot claim manufactured parts"):
        highlighted_nfb_manifest_lines(
            {"manifest": lambda *_: receipt}, 0, (0,),
        )


def test_manifest_ear_current_source_does_not_revert_to_obsolete_all_deferred():
    record = {
        "status": "WHOLE_READY", "actual_export_count": 1,
        "rows": [{
            "part_id": "inner", "role": "INNER_DOOR",
            "status": "READY", "actual_count": 1,
            "may_export": True, "reasons": (),
        }],
        "unresolved_dependencies": (),
    }
    text = nfb_manifest_display_lines(record)[0]
    assert "PAD" in text and "整箱製造" in text
    assert "耳朵尚未驗收" not in text


def test_ac55_one_raw_dxf_inventory_reaches_current_bay_operator_warning_and_export_gate(
    tmp_path,
):
    """Manufacturer-pinned original observation -> per-piece CHECK -> actual UI.

    The historic raw-DXF observation is a source-specific diagnostic, NOT
    universal CSV V5 geometry authority, operator world-X approval, or MFG-2.
    The verified inner CUTTING proof is deliberately independently required.
    """
    from dataclasses import replace
    from hashlib import sha256

    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
    from ae_engine.receiving_nfb_export_manifest import derive_nfb_partial_export_manifest
    from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
    from tests.test_issue1496_nfb_source_inventory_report import _case
    from tests.test_issue1501_nfb_export_manifest import _prepared
    from tools.nfb_source_audit import build_source_coverage_report

    index, root, pins, source = _case(tmp_path)
    actual_bytes = source.read_bytes()
    coverage = build_source_coverage_report(index, source_root=root, pin_path=pins)
    observed = next(
        row for row in coverage["records"]
        if (row["brand"], row["indexed_filename"]) == ("士林", "A.dxf")
    )
    unknown_brand = next(
        row for row in coverage["records"]
        if (row["brand"], row["indexed_filename"]) == ("東元", "A.dxf")
    )
    assert observed["source_sha256"] == sha256(actual_bytes).hexdigest()
    assert observed["provenance_pin_matches"] is True
    assert tuple(observed[f"color_{v}_entities"] for v in (30, 150, 212)) == (1, 1, 1)
    assert tuple(unknown_brand[f"color_{v}_entities"] for v in (30, 150, 212)) == (
        None, None, None,
    )
    assert observed["manufacturing_ready"] is False

    original = inspect_nfb_dxf_source(source)
    options = _prepared(tmp_path)
    options["scope"] = NfbPhysicalScope(
        "setA", "bayA", "version-1", True, "inner1", ("base1",), (),
    )
    options["actual_parts"] = tuple(
        part for part in options["actual_parts"] if part.part_id != "middle1"
    )
    options["saved_bay"]["nfb_config"]["holes"][0]["model_filename"] = "A.dxf"
    options["source_path"] = source
    options["source_inventory"] = original
    options["verified_inner_door"] = replace(
        options["verified_inner_door"],
        indexed_model_key=("士林", "A.dxf"),
        source_sha256=original.source_sha256,
    )

    fresh = derive_nfb_partial_export_manifest(**options)
    assert fresh.partial_only and not fresh.whole_ready
    assert fresh.authorized_part_ids == ("inner1", "side1")
    assert fresh.actual_export_count == 5
    assert fresh.held_actual_count == 1
    assert {row.part_id for row in fresh.rows} == {"inner1", "base1", "side1"}
    assert fresh.require_export(("side1",), partial=True) == ("side1",)
    with pytest.raises(ValueError, match="BLOCKED"):
        fresh.require_export(("base1",), partial=True)
    with pytest.raises(ValueError, match="partial only"):
        fresh.require_export(("inner1", "side1"), partial=False)

    # UI reads the EXACT derived physical report, with status only projected
    # from its independent partial_only/whole_ready gate.
    def live_lines(manifest):
        assert manifest.partial_only and not manifest.whole_ready
        receipt = {**manifest.report(), "status": "PARTIAL_ONLY"}
        return highlighted_nfb_manifest_lines(
            {"manifest": lambda si, bi: receipt}, 0, (0,),
        )
    fresh_ui = live_lines(fresh)
    assert "可加工 5 片" in "｜".join(fresh_ui)
    assert any("base1｜BASE_PLATE｜受阻｜1 片" in line for line in fresh_ui)
    assert any("side1｜OTHER｜可出｜3 片" in line for line in fresh_ui)
    assert any("部分製造清單，不代表整套可交付" in line for line in fresh_ui)
    assert not any("middle1" in line for line in fresh_ui)

    # A foreign DXF under the same indexed filename invalidates the original
    # manufacturer pin; UNKNOWN remains null, never 0 or a new MFG2 grant.
    source.write_bytes((root / "東元" / "A.dxf").read_bytes())
    changed = build_source_coverage_report(index, source_root=root, pin_path=pins)
    untrusted = next(
        row for row in changed["records"]
        if (row["brand"], row["indexed_filename"]) == ("士林", "A.dxf")
    )
    assert untrusted["status"] == "SOURCE_IDENTITY_MISMATCH_UNKNOWN"
    assert tuple(untrusted[f"color_{v}_entities"] for v in (30, 150, 212)) == (
        None, None, None,
    )
    stale = derive_nfb_partial_export_manifest(**options)
    assert stale.authorized_part_ids == ("side1",)
    assert stale.actual_export_count == 3 and stale.held_actual_count == 3
    assert "ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED" in stale.unresolved_dependencies
    stale_ui = live_lines(stale)
    assert "可加工 3 片" in "｜".join(stale_ui)
    assert any("inner1｜INNER_DOOR｜受阻｜2 片" in line for line in stale_ui)
    assert any("base1｜BASE_PLATE｜受阻｜1 片" in line for line in stale_ui)
    assert any("ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED" in line for line in stale_ui)
    assert not any("可加工 5 片" in line for line in stale_ui)
    with pytest.raises(ValueError, match="BLOCKED"):
        stale.require_export(("inner1",), partial=True)
    assert stale.require_export(("side1",), partial=True) == ("side1",)

    source.unlink()
    absent = build_source_coverage_report(index, source_root=root, pin_path=pins)
    no_original = next(
        row for row in absent["records"]
        if (row["brand"], row["indexed_filename"]) == ("士林", "A.dxf")
    )
    assert no_original["status"] == "SOURCE_MISSING_UNKNOWN"
    assert tuple(no_original[f"color_{v}_entities"] for v in (30, 150, 212)) == (
        None, None, None,
    )
    assert derive_nfb_partial_export_manifest(**options).authorized_part_ids == (
        "side1",
    )
