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


def test_ac55_source_verified_colors_reach_real_bay_operator_warning_and_check(
    tmp_path,
):
    """Live source audit → submitted Bay warning → physical partial CHECK.

    The historical Color30/150/212 DXF is diagnostic, while a distinct typed
    verified inner-door CUTTING witness is still necessary. This does not
    fabricate a Receiving middle plate or grant whole-cabinet MFG-2.
    """
    from copy import deepcopy
    from dataclasses import replace
    from hashlib import sha256

    from ae_engine.receiving_layout import new_receiving_layout
    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
    from ae_engine.receiving_nfb_export_manifest import (
        derive_nfb_partial_export_manifest,
    )
    from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
    from ae_engine.receiving_nfb_transactions import submit_nfb_bays
    from tests.test_issue1496_nfb_source_inventory_report import _case
    from tests.test_issue1501_nfb_export_manifest import _prepared
    from tools.nfb_source_audit import build_source_coverage_report

    index, originals, pins, raw_dxf = _case(tmp_path)
    original_bytes = raw_dxf.read_bytes()
    audit = build_source_coverage_report(
        index, source_root=originals, pin_path=pins,
    )
    indexed = {(row["brand"], row["indexed_filename"]): row
               for row in audit["records"]}
    trusted = indexed[("士林", "A.dxf")]
    assert trusted["source_sha256"] == sha256(original_bytes).hexdigest()
    assert tuple(trusted[f"color_{c}_entities"] for c in (30, 150, 212)) == (
        1, 1, 1,
    )
    assert tuple(indexed[("東元", "A.dxf")][f"color_{c}_entities"]
                 for c in (30, 150, 212)) == (None, None, None)
    assert trusted["manufacturing_ready"] is False

    parsed = inspect_nfb_dxf_source(raw_dxf)
    actual_state = new_receiving_layout(width=800, height=1600, depth=350)
    set_row = actual_state["sets"][0]
    bay = set_row["bays"][0]
    physical = _prepared(tmp_path)
    configured = deepcopy(physical["saved_bay"]["nfb_config"])
    configured["holes"][0]["model_filename"] = "A.dxf"
    physical["saved_bay"] = {
        **bay, "nfb_config_submitted": True, "nfb_config": configured,
    }
    physical["scope"] = NfbPhysicalScope(
        set_row["stable_id"], bay["stable_id"], "version-1",
        True, "inner1", ("base1",), (),
    )
    physical["actual_parts"] = tuple(
        row for row in physical["actual_parts"] if row.part_id != "middle1"
    )
    physical["source_inventory"] = parsed
    physical["source_path"] = raw_dxf
    physical["verified_inner_door"] = replace(
        physical["verified_inner_door"],
        indexed_model_key=("士林", "A.dxf"),
        source_sha256=parsed.source_sha256,
    )
    manifest = derive_nfb_partial_export_manifest(**physical)
    assert manifest.actual_export_count == 5
    assert manifest.held_actual_count == 1
    assert manifest.authorized_part_ids == ("inner1", "side1")
    assert not manifest.whole_ready
    view = dict(manifest.report(), status="PARTIAL_ONLY")
    operator_lines = highlighted_nfb_manifest_lines(
        {"manifest": lambda set_index, bay_index: view}, 0, (0,),
    )
    assert any("版本 version-1" in line and bay["stable_id"] in line
               for line in operator_lines)
    assert any("可加工 5 片" in line for line in operator_lines)
    assert any("base1" in line and "受阻" in line and "1 片" in line
               for line in operator_lines)
    assert any("side1" in line and "可出" in line and "3 片" in line
               for line in operator_lines)
    assert any("部分製造清單" in line for line in operator_lines)
    assert all("middle1" not in line for line in operator_lines)

    # Actual verified Bay transaction calls the same operator preview. A
    # refused confirmation never persists a physical NFB configuration.
    observed = []
    cancelled = submit_nfb_bays(
        actual_state, set_index=0, bay_indices=(0,),
        version_id="version-1", configs={0: configured},
        evidence={0: (
            physical["scope"], parsed, physical["verified_inner_door"],
        )},
        confirm=lambda preview: observed.append(preview) or False,
    )
    assert cancelled.changed is False
    assert cancelled.layout == actual_state
    assert len(observed) == 1
    assert "base1" in observed[0].held_parts
    assert len(observed[0].operator_x_changes) == 1
    assert "nfb:bay1:slot1" in observed[0].operator_x_changes[0]
    assert "X 未配置 → 0 mm" in observed[0].operator_x_changes[0]

    # Once the original source is replaced by another manufacturer's valid
    # bytes, both source inventory and operator display must lose fake
    # authority. Never convert a missing/untrusted source into Color=0.
    raw_dxf.write_bytes((originals / "東元" / "A.dxf").read_bytes())
    revoked = build_source_coverage_report(
        index, source_root=originals, pin_path=pins,
    )
    lost = next(row for row in revoked["records"]
                if row["brand"] == "士林" and row["indexed_filename"] == "A.dxf")
    assert lost["status"] == "SOURCE_IDENTITY_MISMATCH_UNKNOWN"
    assert tuple(lost[f"color_{c}_entities"] for c in (30, 150, 212)) == (
        None, None, None,
    )
    stale = derive_nfb_partial_export_manifest(**physical)
    assert stale.authorized_part_ids == ("side1",)
    assert stale.actual_export_count == 3
    assert stale.held_actual_count == 3
    stale_lines = nfb_manifest_display_lines(
        dict(stale.report(), status="PARTIAL_ONLY")
    )
    assert any("可加工 3 片" in line for line in stale_lines)
    assert any("inner1" in line and "受阻" in line for line in stale_lines)
    assert any("base1" in line and "受阻" in line for line in stale_lines)
    assert any("side1" in line and "可出" in line for line in stale_lines)
    assert all("middle1" not in line for line in stale_lines)
    calls = []
    with pytest.raises(ValueError, match="NFB transaction blocked"):
        submit_nfb_bays(
            actual_state, set_index=0, bay_indices=(0,),
            version_id="version-1", configs={0: configured},
            evidence={0: (
                physical["scope"], None, physical["verified_inner_door"],
            )},
            confirm=lambda preview: calls.append(preview) or True,
        )
    assert not calls
