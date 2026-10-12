# -*- coding: utf-8 -*-
"""#1501 actual DXF export protected by LIVE original and saved physical proof."""
from hashlib import sha256

import ezdxf
import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_manufacturing_release import NfbConfiguredInnerDoorHole
from ae_engine.receiving_nfb_export_manifest import (
    NfbActualPart,INNER_DOOR,MIDDLE_PLATE,
)
from ae_engine.receiving_nfb_partial_export_writer import (
    export_current_nfb_inner_door_partial_dxf,
)
from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope


def _case(tmp_path):
    snapshot=apply_family_defaults({
        "model":"受電箱","w":800.,"h":1600.,"d":350.,
        "t":2.,"fw":29.,"door_gap_w":3.5,"door_gap_h":3.5,
    })
    snapshot.update({
        "multi_door_enabled":True,
        "door_layout_scope":"receiving-main",
        "door_layout_columns":[[800.,[1100.,500.]]],
        "inner_doors":[{
            "stable_id":"upper","cell_key":"0:0",
            "included_frame_sides":["top","left","right"],
        }],
    })
    inner=next(p for p in cabinet_family_policy.derive_inner_door_panels(snapshot)
               if p.inner_door_id=="upper")
    index=tmp_path/"開關索引.csv"
    index.write_text(
        "圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "SH400,400_140X257_107.dxf,107,無對應檔案,,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    source=tmp_path/"400_140X257_107(1).dxf"
    d=ezdxf.new("R2010")
    entity=d.modelspace().add_lwpolyline(
        [(0.,0.),(57.,0.),(57.,96.),(0.,96.)],
        close=True,dxfattribs={"color":150},
    )
    d.saveas(source)
    profile=NfbUpperSourceProfile(
        "士林","400_140X257_107.dxf",sha256(source.read_bytes()).hexdigest(),
        entity.dxf.handle,(57.,96.),"SOURCE_ALIAS_SHA256_IDENTICAL","v2",
    )
    hole=NfbConfiguredInnerDoorHole("nfb:bay-a:hole-1",0.,1,0,90)
    bay={
        "stable_id":"bay-a",
        "nfb_config_submitted":True,
        "nfb_config":{"holes":[{
            "physical_hole_id":hole.physical_hole_id,
            "model_filename":profile.indexed_filename,
            "manual_x_mm":hole.world_x_mm,
            "manual_x_state":"CONFIRMED",
            "datum_revision":"operator-world-X-rev1",
            "datum_snapshot":{"w":800,"panel_id":inner.stable_id},
            "layer_count":1,"slot_index":0,"rotation_deg":90,
        }]},
    }
    scope=NfbPhysicalScope(
        "set-a","bay-a","v1",True,inner.stable_id,
        middle_plate_part_ids=("middle-a",),
    )
    args=dict(
        snapshot=snapshot,inner_door_id="upper",
        output_path=tmp_path/"inner_verified.dxf",
        saved_bay=bay,set_brand="士林",physical_scope=scope,
        actual_parts=(
            NfbActualPart(inner.stable_id,INNER_DOOR,2),
            NfbActualPart("middle-a",MIDDLE_PLATE,1),
        ),
        holes=(hole,),index_path=index,source_path=source,profile=profile,
    )
    return args


def test_actual_dxf_writer_emits_only_verified_inner_cutting_and_reports_partial(tmp_path):
    opts=_case(tmp_path)
    path,manifest=export_current_nfb_inner_door_partial_dxf(**opts)
    assert str(opts["output_path"])==str(path)
    assert opts["output_path"].exists()
    assert manifest.partial_only
    assert manifest.authorized_part_ids==(opts["physical_scope"].inner_door_part_id,)
    assert manifest.actual_export_count==2
    assert manifest.held_actual_count==1
    assert manifest.held_rows[0].part_id=="middle-a"
    model=ezdxf.readfile(path).modelspace()
    contours=[e for e in model if e.dxftype()=="LWPOLYLINE"
              and e.dxf.layer=="CUTTING" and e.closed]
    assert len(contours)==2
    assert contours[-1].dxf.color==3
    with pytest.raises((OSError,FileExistsError,ValueError)):
        export_current_nfb_inner_door_partial_dxf(**opts)


def test_changed_original_bytes_stops_before_any_output(tmp_path):
    opts=_case(tmp_path)
    source=opts["source_path"]
    source.write_bytes(source.read_bytes()+b"outdated")
    with pytest.raises(ValueError,match="SHA"):
        export_current_nfb_inner_door_partial_dxf(**opts)
    assert not opts["output_path"].exists()


@pytest.mark.parametrize("change,value",[
    ("manual_x_mm",20.),
    ("rotation_deg",0),
    ("slot_index",1),
    ("model_filename","unrelated.dxf"),
])
def test_saved_nfb_config_mismatch_rejects_export(tmp_path,change,value):
    opts=_case(tmp_path)
    opts["saved_bay"]["nfb_config"]["holes"][0][change]=value
    with pytest.raises(ValueError,match="BLOCKED"):
        export_current_nfb_inner_door_partial_dxf(**opts)
    assert not opts["output_path"].exists()


def test_bad_part_scope_and_missing_physical_part_never_write(tmp_path):
    opts=_case(tmp_path)
    opts["actual_parts"]=(NfbActualPart("unverified-inner",INNER_DOOR),)
    with pytest.raises(ValueError,match="absent/ambiguous"):
        export_current_nfb_inner_door_partial_dxf(**opts)
    assert not opts["output_path"].exists()


def test_unsubmitted_or_cross_bay_evidence_never_write(tmp_path):
    opts=_case(tmp_path)
    scope=opts["physical_scope"]
    opts["saved_bay"]["stable_id"]="wrong"
    with pytest.raises(ValueError,match="Bay stable ID"):
        export_current_nfb_inner_door_partial_dxf(**opts)
    assert not opts["output_path"].exists()
    from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
    opts["physical_scope"]=NfbPhysicalScope(
        scope.set_id,scope.bay_id,scope.version_id,False,scope.inner_door_part_id,
    )
    with pytest.raises(ValueError,match="submitted"):
        export_current_nfb_inner_door_partial_dxf(**opts)


def _quantity_source_case(tmp_path):
    from copy import deepcopy
    from types import SimpleNamespace
    from ae_engine.manufacturing_quantity import PhysicalPartDemand
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data
    from ae_engine.receiving_nfb_manufacturing_release import X_REVISION
    from phase6_quantity_model import QuantityModel
    from phase6_manufacturing_contracts import freeze_manufacturing_value

    opts = _case(tmp_path)
    panel = next(p for p in cabinet_family_policy.derive_inner_door_panels(opts["snapshot"])
                 if p.inner_door_id == "upper")
    config = deepcopy(opts["saved_bay"]["nfb_config"])
    for hole in config["holes"]:
        hole["source_brand"] = "士林"
        hole["datum_revision"] = X_REVISION
        hole["datum_snapshot"] = {
            "w": 800., "h": 1600., "t": 2.,
            "part_id": panel.stable_id, "inner_door_id": panel.inner_door_id,
            "cell_key": panel.cell_key, "profile_revision": opts["profile"].revision,
        }
    model = QuantityModel()
    model.set_piece_count(6)
    v2 = model.add_version()
    model.set_piece_count(4)
    model.set_version_nfb_config("quantity-v1", submitted=True, config=config)
    model.set_version_nfb_config(v2, submitted=True, config=config)
    v3 = model.add_version()
    model.set_piece_count(3)
    model.set_version_nfb_config(v3, submitted=False)
    source = tmp_path / opts["profile"].indexed_filename
    source.write_bytes(opts["source_path"].read_bytes())
    profile = opts["profile"]
    profile_csv = tmp_path / "來源輪廓索引.csv"
    profile_csv.write_text(
        "brand,indexed_filename,source_sha256,upper_handle,upper_width_mm,"
        "upper_height_mm,source_alias_status,revision\n"
        f"{profile.brand},{profile.indexed_filename},{profile.source_sha256},"
        f"{profile.upper_handle},57,96,{profile.source_alias_status},{profile.revision}\n",
        encoding="utf-8-sig",
    )
    base = build_inner_door_panel_render_data(panel)
    requests = []
    demands = []
    for row in model.snapshot()["versions"]:
        vid, count = row["version_id"], row["piece_count"]
        request = SimpleNamespace(input_snapshot=freeze_manufacturing_value(opts["snapshot"]),
                                  settings=freeze_manufacturing_value({"t": 2.}), parts=())
        requests.append((vid, count, request))
        for key in ("inner_door:upper", "base_plate", "box_body:left_side"):
            demands.append(PhysicalPartDemand(vid, key, key, count, 1, base))
    from phase6_quantity_manufacturing import QuantityManufacturingBatch
    from ae_engine.manufacturing_quantity import ResolvedQuantityVersion
    batch = QuantityManufacturingBatch(
        tuple(ResolvedQuantityVersion(vid, count, SimpleNamespace(parts=()))
              for vid, count, _request in requests),
        tuple(demands), tuple(requests),
    )
    return opts, model, batch, source, profile_csv


def test_quantity_main_selection_uses_live_source_and_keeps_other_versions(tmp_path):
    from functools import partial
    from dataclasses import replace
    from gui_modules.application.receiving_nfb_quantity_partial import (
        select_quantity_nfb_partial, verify_quantity_nfb_inner_door,
    )
    opts, model, batch, source, profiles = _quantity_source_case(tmp_path)
    # The fixture side/base sheets must retain independent physical topology.
    batch = replace(batch, demands=tuple(replace(d, render_data=replace(d.render_data, unfolded_topology=None))
                          if d.source_part_id != "inner_door:upper" else d
                          for d in batch.demands))
    selection = select_quantity_nfb_partial(
        batch, {"quantity": model.snapshot()},
        verifier=partial(verify_quantity_nfb_inner_door,
                         index_path=opts["index_path"], profile_path=profiles),
    )
    ready = [r for r in selection.rows if r["status"] == "READY"]
    assert [r["actual_count"] for r in ready] == [6, 4]
    assert selection.exported_piece_count == 29  # 10 inner + 10 side + 9 legacy
    assert selection.held_piece_count == 10
    assert not selection.report()["whole_cabinet_complete"]
    original = next(d.render_data for d in batch.demands if d.source_part_id == "inner_door:upper")
    actual = next(d.render_data for d in selection.demands if d.version_id == "quantity-v1"
                  and d.source_part_id == "inner_door:upper")
    assert len(actual.scene.primitives) > len(original.scene.primitives)
    source.write_bytes(source.read_bytes() + b"stale")
    stale = select_quantity_nfb_partial(
        batch, {"quantity": model.snapshot()},
        verifier=partial(verify_quantity_nfb_inner_door,
                         index_path=opts["index_path"], profile_path=profiles),
    )
    assert stale.exported_piece_count == 19  # unaffected sides + whole legacy version
    assert stale.held_piece_count == 20
    assert all(r["status"] != "READY" for r in stale.rows)


@pytest.mark.parametrize("change", ["datum", "reconfirm", "existing_cutting", "count"])
def test_quantity_partial_rejects_changed_datum_and_preserves_existing_machining(tmp_path, change):
    from functools import partial
    from dataclasses import replace
    from gui_modules.application.receiving_nfb_quantity_partial import (
        select_quantity_nfb_partial, verify_quantity_nfb_inner_door,
    )
    opts, model, batch, source, profiles = _quantity_source_case(tmp_path)
    batch = replace(batch, demands=tuple(replace(d, render_data=replace(d.render_data, unfolded_topology=None))
                          if d.source_part_id != "inner_door:upper" else d
                          for d in batch.demands))
    if change in ("datum", "reconfirm"):
        config = model.nfb_config_for_version("quantity-v1")["nfb_config"]
        if change == "datum":
            config["holes"][0]["datum_snapshot"]["w"] = 900
        else:
            config["holes"][0]["manual_x_state"] = "RECONFIRM_REQUIRED"
        model.set_version_nfb_config("quantity-v1", submitted=True, config=config)
    elif change == "existing_cutting":
        # Extra legacy machining must never be discarded to substitute NFB.
        first = batch.demands[0]
        from copy import deepcopy
        render = deepcopy(first.render_data)
        render.scene.add_circle((200, 200), 2, layer="CUTTING")
        batch = replace(batch, demands=(replace(first, render_data=render), *batch.demands[1:]))
    else:
        batch = replace(batch, demands=(replace(batch.demands[0], piece_count=7), *batch.demands[1:]))
    kwargs = dict(verifier=partial(verify_quantity_nfb_inner_door,
                                  index_path=opts["index_path"], profile_path=profiles))
    if change == "count":
        with pytest.raises(ValueError, match="identity/count"):
            select_quantity_nfb_partial(batch, {"quantity": model.snapshot()}, **kwargs)
        return
    result = select_quantity_nfb_partial(batch, {"quantity": model.snapshot()}, **kwargs)
    row = next(r for r in result.rows if r["version_id"] == "quantity-v1"
               and r["source_part_id"] == "inner_door:upper")
    assert row["status"] == "BLOCKED" and row["reason"]
    assert any(r["version_id"] == "quantity-v2" and r["status"] == "READY"
               for r in result.rows)


def test_primary_quantity_export_writes_real_nfb_cutting_check_and_partial_manifest(tmp_path, monkeypatch):
    import json
    import re
    from copy import deepcopy
    from dataclasses import replace
    from functools import partial
    from types import SimpleNamespace
    import phase6_manufacturing_adapter as adapter
    import phase6_quantity_manufacturing as quantity
    from gui_modules.project import export_actions
    from gui_modules.application import receiving_nfb_quantity_partial as partial_action

    opts, model, batch, source, profiles = _quantity_source_case(tmp_path)
    batch = replace(batch, demands=tuple(replace(d, render_data=replace(d.render_data, unfolded_topology=None))
                          if d.source_part_id != "inner_door:upper" else d
                          for d in batch.demands))
    config = model.nfb_config_for_version("quantity-v2")["nfb_config"]
    config["holes"][0]["manual_x_mm"] = 60.
    model.set_version_nfb_config("quantity-v2", submitted=True, config=config)
    snapshot = deepcopy(opts["snapshot"])
    snapshot.update(active_mode="quantity", quantity=model.snapshot())
    designer = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        designer_workspace=SimpleNamespace(snapshot=lambda: deepcopy(snapshot)),
        _phase6_resolve_manufacturing_geometry=lambda: None,
        _scene_query_callback=lambda *_: None,
        _part_spec_query_callback=lambda *_: None,
    )
    app = SimpleNamespace(fold_designer_app=designer)
    monkeypatch.setattr(adapter, "build_manufacturing_request", lambda *_a, **_k: batch.requests[0][2])
    monkeypatch.setattr(quantity, "resolve_quantity_manufacturing", lambda *_: batch)
    monkeypatch.setattr(partial_action, "verify_quantity_nfb_inner_door",
                        partial(partial_action.verify_quantity_nfb_inner_door,
                                index_path=opts["index_path"], profile_path=profiles))
    output = tmp_path / "output"
    output.mkdir()
    exported, errors = export_actions._export_selected_parts(
        app, str(output), {}, {"door": True, "base_plate": True, "box_body": True}, False,
    )
    assert not errors
    assert "nfb_partial_manifest.json" in exported
    report = json.loads((output / "nfb_partial_manifest.json").read_text())
    assert report["actual_export_count"] == 29 and report["held_actual_count"] == 10
    assert report["whole_cabinet_complete"] is False
    assert report["deferred_assembly"] == ["PAD", "EAR_ATTACHMENT"]
    assert all(row["version_id"] in {"quantity-v1", "quantity-v2", "quantity-v3"}
               and row["physical_part_id"] for row in report["rows"])
    labels = []
    for path in output.glob("*.dxf"):
        entities = ezdxf.readfile(path).modelspace()
        labels.extend(row.plain_text() for row in entities.query("MTEXT")
                      if re.fullmatch(r"Q[0-9]+", row.plain_text()))
    assert sorted(labels) == ["Q19", "Q4", "Q6"]
    assert sum(int(q[1:]) for q in labels) == report["actual_export_count"]
    # Stale bytes hold both inner doors, not the untouched version/side parts.
    source.write_bytes(source.read_bytes() + b"invalidated")
    next_output = tmp_path / "stale-output"
    next_output.mkdir()
    files, errors = export_actions._export_selected_parts(
        app, str(next_output), {}, {"door": True, "base_plate": True, "box_body": True}, False,
    )
    assert files and not errors
    stale = json.loads((next_output / "nfb_partial_manifest.json").read_text())
    assert stale["actual_export_count"] == 19 and stale["held_actual_count"] == 20
    assert not any(row["status"] == "READY" for row in stale["rows"])


def test_quantity_partial_main_refuses_divergent_submitted_version_owners(tmp_path, monkeypatch):
    from copy import deepcopy
    from types import SimpleNamespace
    import phase6_manufacturing_adapter as adapter
    from gui_modules.project import export_actions
    opts, model, batch, source, profiles = _quantity_source_case(tmp_path)
    source_snapshot = deepcopy(opts["snapshot"])
    source_snapshot.update(active_mode="quantity", quantity=model.snapshot())
    workspace_snapshot = deepcopy(source_snapshot)
    workspace_snapshot["quantity"]["versions"][0]["nfb_config"]["holes"][0]["manual_x_mm"] = 88.
    designer = SimpleNamespace(
        _phase6_input_snapshot=source_snapshot,
        designer_workspace=SimpleNamespace(snapshot=lambda: workspace_snapshot),
        _phase6_resolve_manufacturing_geometry=lambda: None,
        _scene_query_callback=lambda *_: None, _part_spec_query_callback=lambda *_: None,
    )
    monkeypatch.setattr(adapter, "build_manufacturing_request", lambda *_a, **_k: batch.requests[0][2])
    app = SimpleNamespace(fold_designer_app=designer)
    output = tmp_path / "output"
    output.mkdir()
    exported, errors = export_actions._export_selected_parts(
        app, str(output), {}, {"door": True}, False,
    )
    assert not exported and errors and not list(output.iterdir())


@pytest.mark.parametrize("confirmed", [False, True])
def test_operator_partial_confirmation_controls_atomic_delivery(tmp_path, monkeypatch, confirmed):
    import json
    from types import SimpleNamespace
    from gui_modules.project import export_actions
    report = {
        "actual_export_count": 6, "held_actual_count": 4,
        "whole_cabinet_complete": False, "rows": [{
            "version_id": "quantity-v1", "part_id": "inner_door:upper",
            "status": "READY", "actual_count": 6, "reason": "",
        }],
    }
    app = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        _phase6_current_existing_parts=lambda: (),
        _has_any_indicator_box=lambda: False,
        get_float_values=lambda: {},
        draw_stock_var=SimpleNamespace(get=lambda: False),
    )
    notices = []
    questions = []
    monkeypatch.setattr(export_actions, "_selected_export_flags", lambda *_: {"door": True})
    monkeypatch.setattr(export_actions, "_validate_selected_indicator_exports", lambda *_: None)
    monkeypatch.setattr(export_actions.filedialog, "askdirectory", lambda **_: str(tmp_path))
    def write_stage(owner, folder, *_):
        from pathlib import Path
        owner._phase6_nfb_partial_export_report = report
        Path(folder, "inner.dxf").write_bytes(b"staged authorized file")
        Path(folder, "nfb_partial_manifest.json").write_text(json.dumps(report))
        return ["inner.dxf", "nfb_partial_manifest.json"], []
    def confirm(title, text):
        questions.append((title, text))
        return confirmed
    monkeypatch.setattr(export_actions, "_export_selected_parts", write_stage)
    monkeypatch.setattr(export_actions.messagebox, "askyesno", confirm)
    monkeypatch.setattr(export_actions.messagebox, "showinfo", lambda *a: notices.append(a))
    monkeypatch.setattr(export_actions.messagebox, "showerror",
                        lambda *a: pytest.fail(str(a)))
    export_actions.export_selected_dxf(app)
    assert len(questions) == 1
    assert "不是整套完成" in questions[0][1] and "受阻 4 片" in questions[0][1]
    assert (tmp_path / "inner.dxf").exists() is confirmed
    assert bool(notices) is confirmed
    if confirmed:
        assert notices[0][0] == "NFB 部分匯出完成"
    else:
        assert not list(tmp_path.iterdir())
    assert not list(tmp_path.glob(".whd-export-stage-*"))
