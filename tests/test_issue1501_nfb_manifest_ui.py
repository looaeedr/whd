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
