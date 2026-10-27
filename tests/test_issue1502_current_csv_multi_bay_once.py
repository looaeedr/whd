# -*- coding: utf-8 -*-
"""Original selected-DXF action: all current Receiving Bays and exact sources."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.receiving_layout import (
    resize_receiving_bays, project_receiving_bay_legacy_aliases,
)
from ae_engine.receiving_csv_multibay_manufacturing import (
    export_current_receiving_multibay_dxf,
)
from tests.test_issue1502_single_button_full_csv_receiving_export import (
    _prepare,_flags,
)
from tests.test_issue1502_quantity_current_csv_full_batch import _geometry


def _multi():
    source,_=_prepare(False)
    source["active_mode"]="set_bay"
    # The _prepare fixture deliberately uses a compact in-memory source
    # alias ("S"/"B") for single-sheet tests. A true MULTI-Bay test must
    # start from the authentic canonical persisted layout with real dimensions,
    # stable IDs and adjacency joints; do not pass a fake one-Bay alias to
    # resize_receiving_bays or manufacture from it.
    from ae_engine.receiving_layout import new_receiving_layout
    single = new_receiving_layout(
        width=source["w"], height=source["h"], depth=source["d"],
    )
    single["sets"][0]["switch_brand"] = "士林"
    original = single["sets"][0]["bays"][0]
    original["nfb_config_submitted"] = True
    original["nfb_config"] = deepcopy(source["nfb_config"])
    source["receiving_layout"]=resize_receiving_bays(
        single,set_index=0,bay_count=2,
    )
    bays=source["receiving_layout"]["sets"][0]["bays"]
    assert [row["stable_id"] for row in bays]==[
        "receiving:set:1:bay:1","receiving:set:1:bay:2",
    ]
    # Appending a Bay intentionally resets copied NFB X confirmation.
    # Model an independently CONFIRMED second Bay from the same authorized
    # numeric CSV, with a different actual screw X. Never manufacture
    # the unconfirmed cloned Bay that resize_receiving_bays first creates.
    second=deepcopy(bays[0]["nfb_config"])
    second["holes"][0]["manual_x_mm"]+=25.
    bays[1]["nfb_config_submitted"]=True
    bays[1]["nfb_config"]=second
    return source


def _provider(source):
    calls=[]
    def provide(si,bi):
        calls.append((si,bi))
        snap=project_receiving_bay_legacy_aliases(
            source,set_index=si,bay_index=bi,
        )
        return _geometry(snap)
    return provide,calls


def _run(source,out,*,provider=None,flags=None):
    real, calls = _provider(source)
    outputs=export_current_receiving_multibay_dxf(
        source,physical_bay_geometry_provider=provider or real,
        flags=flags or _flags(),output_dir=out,
    )
    return outputs,calls


def test_both_distinct_bays_one_atomic_export_with_exact_source_ear_side(tmp_path):
    source=_multi()
    exported,calls=_run(source,tmp_path)
    assert calls==[(0,0),(0,1)]
    names=tuple(Path(p).name for p in exported.values())
    assert len(names)==len(set(names))==len(list(tmp_path.glob("*.dxf")))
    assert len([name for name in names if "fixing_plate" in name])==4
    assert len([name for name in names if "base_plate" in name
                and "fixing_plate" not in name])==2
    assert len([name for name in names if "inner_door" in name
                and "panel" in name])==2
    pads=[name for name in names if "nfb_pad" in name]
    assert len(pads)==2  # each real Bay contributes its own source-verified PAD
    assert len(set(pads))==2
    for name in pads:
        msp=ezdxf.readfile(tmp_path/name).modelspace()
        assert sum(e.dxf.layer=="BEND" for e in msp)==2
        assert sum(e.dxf.layer=="CUTTING" for e in msp)==5
    assert len([name for name in names if "left_side" in name])==2
    assert len([name for name in names if "right_side" in name])==2
    for name in names:
        ezdxf.readfile(tmp_path/name)
    for name in names:
        if "fixing_plate" in name:
            elements=ezdxf.readfile(tmp_path/name).modelspace()
            assert len([e for e in elements if e.dxf.layer=="BEND"])==1
            assert len([e for e in elements if e.dxftype()=="LWPOLYLINE"
                        and e.closed and e.dxf.layer=="CUTTING"])==5


def test_second_bay_may_not_borrow_first_bay_csv_finalscene(tmp_path):
    source=_multi()
    first=_geometry(project_receiving_bay_legacy_aliases(source))
    def stale(_si,_bi):
        return first
    with pytest.raises(ValueError,match="ACTUAL_FINALSCENE_SOURCE_DRIFT"):
        _run(source,tmp_path/"out",provider=stale)
    assert not (tmp_path/"out").exists()


def test_missing_second_bay_base_refuses_all_dxfs(tmp_path):
    source=_multi()
    provider,_=_provider(source)
    def absent(si,bi):
        scene=provider(si,bi)
        if bi==1:
            scene=replace(scene,parts=tuple(p for p in scene.parts
                if p.part_key!="base_plate"))
        return scene
    with pytest.raises(ValueError,match="BASE|PHYSICAL"):
        _run(source,tmp_path/"none",provider=absent)
    assert not (tmp_path/"none").exists()


def test_second_dxf_reopen_failure_rolls_back_all_bays(tmp_path,monkeypatch):
    import ae_engine.receiving_csv_multibay_manufacturing as module
    actual=module.verify_saved_part_render_data_dxf
    calls={"n":0}
    def fail_second(render,path):
        calls["n"]+=1
        if calls["n"]==2:
            return SimpleNamespace(ok=False)
        return actual(render,path)
    monkeypatch.setattr(module,"verify_saved_part_render_data_dxf",fail_second)
    with pytest.raises(ValueError,match="SAVED_DXF_ROUNDTRIP_FAILED"):
        _run(_multi(),tmp_path/"output")
    assert calls["n"]==2
    assert not list((tmp_path/"output").glob("*.dxf"))


def test_original_main_operator_action_not_extra_dxf_button():
    import inspect
    from gui_modules.project import export_actions
    source=inspect.getsource(export_actions._export_selected_resolved_parts)
    assert "export_current_receiving_multibay_dxf" in source
    assert "receiving_bay_preview_request" in source
    assert "receiving_bay_assembly_offsets" in source
    assert "save_verified_receiving_csv_selected_sheets" in source
