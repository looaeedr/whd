# -*- coding: utf-8 -*-
"""#1502: Q3+Q2 variants consume independently selected current numeric CSV.

No old supplier-DXF handle; real PartRenderData/Phase6 2D/3D source,
physical fixing EARs and marked side sheets are proven per version BEFORE
geometry-equivalent quantities are grouped and saved atomically.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.contracts import ResolvedManufacturingPart
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.manufacturing_quantity import (
    ResolvedQuantityVersion, resolved_quantity_physical_demands,
)
from ae_engine.receiving_quantity_box import project_common_box
from ae_engine.receiving_layout import (
    project_receiving_bay_legacy_aliases, RECEIVING_DOOR_STATE_KEYS,
)
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.sheetmetal_drawing import LinePrimitive
from phase6_quantity_manufacturing import QuantityManufacturingBatch
from phase6_manufacturing_contracts import (
    freeze_manufacturing_value, thaw_manufacturing_value,
)
from phase6_quantity_model import QuantityModel
from ae_engine.receiving_csv_quantity_manufacturing import (
    export_current_csv_quantity_manufacturing,
)
from tests.test_issue1502_single_button_full_csv_receiving_export import (
    _prepare, _flags,
)
from tests.test_issue1050_receiving_mother_plate_marking import (
    _full_receiving_geometry,
)
from tests.test_receiving_two_tier_physical_base_parts import _source


def _geometry(snapshot):
    plain=_full_receiving_geometry(snapshot)
    baseline=_source(snapshot)
    placement=resolve_assembly_placement(snapshot,"base_plate")
    base=ResolvedManufacturingPart(
        part_key="base_plate", render_data=baseline.render_data,
        x_profile=baseline.x_profile,y_profile=baseline.y_profile,
        placement=baseline.placement,offset=placement.world_offset,
    )
    panel=next(p for p in derive_inner_door_panels(snapshot)
               if str(p.cell_key).split(":")[-1]=="0")
    door=ResolvedManufacturingPart(
        part_key=panel.stable_id,
        render_data=build_inner_door_panel_render_data(panel),
        x_profile=(),y_profile=(),placement="offset",offset=(0.,0.,0.),
    )
    actual=apply_committed_csv_v5_to_canonical_parts(snapshot,(door,base))
    return replace(plain,parts=plain.parts+actual)


def _batch():
    raw,_=_prepare(False)
    c1=deepcopy(raw["nfb_config"])
    c2=deepcopy(c1)
    c2["holes"][0]["manual_x_mm"]+=20.
    c2["holes"][1]["manual_x_mm"]-=20.
    q=QuantityModel()
    first=q.selected_version_id
    q.set_version_nfb_config(first,submitted=True,config=c1)
    q.set_piece_count(3)
    q.add_version()
    second=q.selected_version_id
    q.set_piece_count(2)
    q.set_version_nfb_config(second,submitted=True,config=c2)
    box={
        "w":raw["w"],"h":raw["h"],"d":raw["d"],
        "inner_door_layers":1,
        "door_state":{
            key:deepcopy(raw[key]) for key in RECEIVING_DOOR_STATE_KEYS if key in raw
        },
    }
    common={**raw,"active_mode":"quantity",
            "receiving_quantity_box":box}
    versions=[]
    requests=[]
    for vid in (first,second):
        version_q=QuantityModel.from_payload(q.snapshot())
        version_q.select(vid)
        snap=project_receiving_bay_legacy_aliases(project_common_box({
            **common,"quantity":version_q.snapshot()
        }))
        assert snap["nfb_config"]== (c1 if vid==first else c2)
        geom=_geometry(snap)
        count=3 if vid==first else 2
        versions.append(ResolvedQuantityVersion(vid,count,geom))
        requests.append((vid,count,SimpleNamespace(
            input_snapshot=freeze_manufacturing_value(snap),
            settings=freeze_manufacturing_value({"t":2.}),parts=(),
        )))
    demands=resolved_quantity_physical_demands(versions)
    return QuantityManufacturingBatch(
        tuple(versions),demands,tuple(requests),
    )


def _export(batch,dir,**flags):
    return export_current_csv_quantity_manufacturing(
        batch,dir,flags=_flags(**flags),
    )


def _quantity(path):
    msp=ezdxf.readfile(path).modelspace()
    entries=[x.plain_text() for x in msp.query("MTEXT")
             if x.plain_text().startswith("Q")]
    assert len(entries)==1
    return entries[0]


def test_both_actual_versions_sum_five_identical_base_and_ear_pieces(tmp_path):
    batch=_batch()
    saved=_export(batch,tmp_path)
    assert saved
    assert len(list(tmp_path.glob("*.dxf")))==len(saved)
    assert all(Path(x).is_file() for x in saved.values())
    totals=[]
    for groupfile in saved.values():
        total=int(_quantity(groupfile)[1:])
        totals.append(total)
    assert 5 in totals  # identical authentic T2 ears/ordinary unchanged parts
    assert 3 in totals and 2 in totals  # CSV X differs on actual NFB CUTTING
    assert sum(totals) == sum(
        d.quantity for d in batch.demands
        if d.source_part_id.startswith("custom:")
        or _flags().get(
            __import__("gui_modules.project.export_actions",fromlist=["_resolved_export_intention_key"])
            ._resolved_export_intention_key(d.source_part_id),False)
    )+10  # 2 authentic left/right fixing EARs per box x five cabinets


def test_each_version_uses_current_saved_csv_not_other_selected_version(tmp_path):
    batch=_batch()
    req=list(batch.requests)
    first_snapshot=thaw_manufacturing_value(req[0][2].input_snapshot)
    altered=thaw_manufacturing_value(req[1][2].input_snapshot)
    altered["nfb_config"]=deepcopy(first_snapshot["nfb_config"])
    altered["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        altered["nfb_config"]
    )
    broken=replace(batch,requests=(req[0],(req[1][0],req[1][1],
        SimpleNamespace(
            input_snapshot=freeze_manufacturing_value(altered),
            settings=freeze_manufacturing_value({"t":2.}),
            parts=(),
        ))))
    with pytest.raises(ValueError,match="SAVED_SOURCE_NOT_CURRENT"):
        _export(broken,tmp_path)
    assert not list(tmp_path.glob("*.dxf"))


def test_changed_second_version_hole_does_not_export_stale_geometry(tmp_path):
    batch=_batch()
    second=thaw_manufacturing_value(batch.requests[1][2].input_snapshot)
    second["nfb_config"]["holes"][0]["manual_x_mm"]+=15.
    second["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        second["nfb_config"]
    )
    q=QuantityModel.from_payload(second["quantity"])
    q.set_version_nfb_config(q.selected_version_id,submitted=True,
                             config=second["nfb_config"])
    second["quantity"]=q.snapshot()
    modified=replace(batch,requests=(batch.requests[0],
        (batch.requests[1][0],batch.requests[1][1],
         SimpleNamespace(
            input_snapshot=freeze_manufacturing_value(second),
            settings=freeze_manufacturing_value({"t":2.}),
            parts=(),
        ))))
    with pytest.raises(ValueError,match="SOURCE_DRIFT|CURRENT"):
        _export(modified,tmp_path)
    assert not list(tmp_path.glob("*.dxf"))


def test_per_version_q_group_last_saved_dxf_failure_rolls_back(tmp_path,monkeypatch):
    import ae_engine.receiving_csv_quantity_manufacturing as module
    verified=module.verify_saved_part_render_data_dxf
    calls={"n":0}
    def corrupted(*args,**kwargs):
        calls["n"]+=1
        if calls["n"]==2:
            return SimpleNamespace(ok=False)
        return verified(*args,**kwargs)
    monkeypatch.setattr(module,"verify_saved_part_render_data_dxf",corrupted)
    with pytest.raises(ValueError,match="SAVED_DXF_REOPEN_FAILED"):
        _export(_batch(),tmp_path)
    assert calls["n"]==2
    assert not list(tmp_path.glob("*.dxf"))


def test_original_quantity_gui_routes_to_current_csv_not_retired_supplier_dxf():
    import inspect
    from gui_modules.project import export_actions
    source=inspect.getsource(export_actions._export_selected_resolved_parts)
    assert "export_current_csv_quantity_manufacturing" in source
    assert 'mode_source.get("model") == "受電箱"' in source
    assert "_resolved_export_intention_key" in source
