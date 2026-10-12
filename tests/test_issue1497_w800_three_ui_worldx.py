# -*- coding: utf-8 -*-
"""#1497 W800x3 GUI uses actual WHD manufactured X without re-entering it."""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.receiving_nfb_ui1a import (
    add_nfb_draft_slot, new_nfb_ui1a_draft, set_nfb_draft_layer_count,
)
from ae_engine.receiving_nfb_ui1a_edits import editable_nfb_draft
from ae_engine.receiving_nfb_ui1b_runtime import (
    derive_w800_three_world_x_by_unit, verify_current_nfb_ui_draft,
)
from ae_engine.receiving_nfb_x_projection import W800_THREE_DATUM_REVISION
import ae_engine.receiving_nfb_ui1b_runtime as runtime


def _snapshot(neighbor=None):
    width=800.0+(neighbor or 0.0)
    state=apply_family_defaults({
        "model":"受電箱","w":width,"h":1600.,"d":350.,
        "t":2.,"fw":29.,"door_gap_w":3.5,"door_gap_h":3.5,
    })
    cols=([[800.,[1100.,500.]]] if neighbor is None
          else [[neighbor,[1100.,500.]],[800.,[1100.,500.]]])
    state.update({
        "w":width,"multi_door_enabled":True,
        "door_layout_scope":"receiving-main",
        "door_layout_columns":cols,
        "inner_doors":[{
            "stable_id":"upper",
            "cell_key":"0:0" if neighbor is None else "1:0",
            "included_frame_sides":["top","left","right"],
        }],
    })
    return state


def _draft(layer_count=1):
    draft=new_nfb_ui1a_draft(set_brand="士林")
    if layer_count==2:
        draft=set_nfb_draft_layer_count(draft,2)
    for layer in range(layer_count):
        for j in range(3):
            draft=add_nfb_draft_slot(
                draft,layer,filename="400_140X257_107.dxf",
                source_brand="士林",
            )
    return editable_nfb_draft(draft)


@pytest.mark.parametrize("neighbor,world", [
    (None,(-180.,0.,180.)),
    (400.,(20.,200.,380.)),
])
def test_canonical_gui_x_uses_actual_w800_723_blank_not_dxf_bbox(neighbor,world):
    draft=_draft()
    state=_snapshot(neighbor)
    before=deepcopy(draft),deepcopy(state)
    out=derive_w800_three_world_x_by_unit(draft,snapshot=state)
    ids=[s["unit_id"] for s in draft["layers"][0]["slots"]]
    assert list(out)==ids
    assert tuple(out.values())==pytest.approx(world)
    assert (draft,state)==before


def test_two_layers_map_identical_horizontal_x_per_layer():
    draft=_draft(2)
    out=derive_w800_three_world_x_by_unit(draft,snapshot=_snapshot())
    ids=[s["unit_id"] for layer in draft["layers"]
         for s in layer["slots"]]
    assert list(out)==ids
    assert tuple(out.values())==pytest.approx((-180.,0.,180.)*2)


def test_unknown_width_one_or_two_slots_and_half_config_do_not_guess():
    draft=_draft()
    state=_snapshot()
    for mismatch in (
        editable_nfb_draft(new_nfb_ui1a_draft(set_brand="士林")),
        editable_nfb_draft(add_nfb_draft_slot(
            new_nfb_ui1a_draft(set_brand="士林"),0,
            filename="400_140X257_107.dxf",source_brand="士林",
        )),
    ):
        with pytest.raises(ValueError,match="exactly three"):
            derive_w800_three_world_x_by_unit(mismatch,snapshot=state)
    for change in ({"w":750.},{"t":3.},{"door_gap_w":4.},
                   {"multi_door_enabled":False}):
        modified=deepcopy(state);modified.update(change)
        with pytest.raises(ValueError,match="OPEN-X-W800x3"):
            derive_w800_three_world_x_by_unit(draft,snapshot=modified)
    ambiguous=deepcopy(state)
    ambiguous["inner_doors"].append({
        "stable_id":"upper2","cell_key":"1:0",
        "included_frame_sides":["top","left","right"],
    })
    with pytest.raises(ValueError,match="ambiguous"):
        derive_w800_three_world_x_by_unit(draft,snapshot=ambiguous)


def test_runtime_fixes_canonical_x_and_records_datum_revision(tmp_path,monkeypatch):
    state=_snapshot(400.)
    draft=_draft()
    root=tmp_path/"基準檔"/"開孔"/"NFB"
    root.mkdir(parents=True)
    index=root/"開關索引.csv"
    index.write_text(
        "圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "SH400,400_140X257_107.dxf,107,無對應檔案,,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    (root/"來源輪廓索引.csv").write_text(
        "brand,indexed_filename,source_sha256,upper_handle,upper_width_mm,"
        "upper_height_mm,source_alias_status,revision\n"
        "士林,400_140X257_107.dxf,"+"a"*64+
        ",585,57,96,SOURCE_ALIAS_UNCERTIFIED,TEST-REV\n",
        encoding="utf-8-sig",
    )
    source=root/"士林"/"400_140X257_107.dxf"
    source.parent.mkdir()
    source.write_bytes(b"runtime-router-only; actual production verifier checks SHA")
    layout={"sets":[{"stable_id":"set-1","switch_brand":"士林",
                     "bays":[{"stable_id":"bay-1"}]}]}
    coords=derive_w800_three_world_x_by_unit(draft,snapshot=state)
    calls=[]
    def verified(*args,**kwargs):
        calls.append((args,kwargs))
        return "ROUTED_TO_REAL_MANUFACTURING_VERIFIER"
    monkeypatch.setattr(runtime,"verify_nfb_ui1a_for_submit",verified)
    arguments=dict(
        draft=draft,layout=layout,set_index=0,bay_index=0,
        version_id="v1",projected_snapshot=state,
        world_x_by_unit=coords,canonical_w800_three=True,
        index_path=index,
    )
    assert verify_current_nfb_ui_draft(**arguments)==(
        "ROUTED_TO_REAL_MANUFACTURING_VERIFIER"
    )
    assert len(calls)==1
    routed=calls[0][1]
    assert routed["world_x_by_unit"]==coords
    assert routed["datum_revision"]==W800_THREE_DATUM_REVISION
    assert routed["datum_snapshot"]["whd_canonical_x_revision"]==(
        W800_THREE_DATUM_REVISION
    )
    assert routed["datum_snapshot"]["whd_canonical_world_x_by_unit"]==coords
    assert routed["physical_scope"].inner_door_part_id=="inner_door:upper:panel"
    assert routed["source_path"]==source

    for changes in (
        {"world_x_by_unit":{**coords,next(iter(coords)):0.0}},
        {"world_x_by_unit":dict(list(coords.items())[:2])},
        {"world_x_by_unit":{**coords,"foreign":30.0}},
    ):
        with pytest.raises(ValueError,match="differs from actual canonical"):
            verify_current_nfb_ui_draft(**{**arguments,**changes})
        assert len(calls)==1


def test_legacy_manual_x_path_remains_intact_for_other_modes(tmp_path,monkeypatch):
    # The dedicated W800x3 route must not silently replace an operator's
    # explicit X for a single NFB or some unrelated source topology.
    draft=editable_nfb_draft(add_nfb_draft_slot(
        new_nfb_ui1a_draft(set_brand="士林"),0,
        filename="400_140X257_107.dxf",source_brand="士林",
    ))
    with pytest.raises(ValueError,match="exactly three"):
        derive_w800_three_world_x_by_unit(draft,snapshot=_snapshot())
