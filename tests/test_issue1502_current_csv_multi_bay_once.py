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
    source["receiving_layout"]=resize_receiving_bays(
        source["receiving_layout"],set_index=0,bay_count=2,
    )
    bays=source["receiving_layout"]["sets"][0]["bays"]
    assert [row["stable_id"] for row in bays]==[
        "receiving:set:1:bay:1","receiving:set:1:bay:2",
    ]
    # Real second Bay has a DIFFERENT signed CSV screw position but the
    # same physical cabinet family, sheet material and fixing EAR pitch.
    bays[1]["nfb_config"]["holes"][0]["manual_x_mm"]+=25.
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
