# -*- coding: utf-8 -*-
"""#1503: actual +90° source-formed EAR machining through ORIGINAL selected DXF."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.receiving_base_fixing_plate_geometry import (
    SOURCE_DXF_SHA256, build_fixing_plate_source_render_data,
)
from ae_engine.receiving_nfb_layer_physical_parts import (
    expand_receiving_nfb_layer_parts,
)
from ae_engine.receiving_fixed_plate_formed_manufacturing import (
    save_verified_receiving_formed_fixing_plate_bundle,
)
from ae_engine.receiving_ear_side_manufacturing_marking import (
    with_verified_receiving_ear_side_markings,
)
from gui_modules.project.export_actions import _export_selected_resolved_parts
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def _real_installed(factory):
    snapshot, side_scene = _actual(factory)
    root = _source(snapshot)
    if factory is _two_tier:
        physical = expand_receiving_nfb_layer_parts(snapshot, (root,))
    else:
        installed = resolve_assembly_placement(snapshot, "base_plate")
        physical = (replace(root, offset=installed.world_offset),)
    return snapshot, replace(
        side_scene, parts=side_scene.parts + tuple(physical),
    )


def _selected(snapshot, geometry):
    full = with_verified_receiving_ear_side_markings(
        snapshot, geometry, dimensions=(800.,1600.,350.), sheet_thickness=2.,
    )
    from gui_modules.project.export_actions import _selected_resolved_geometry
    flags = dict(box_body=True, head=False, tail=False, door=False,
                 base_plate=False, indicator_box=False, indicator_door=False)
    return _selected_resolved_geometry(full, flags)


def _run(snapshot, geom, dest):
    return save_verified_receiving_formed_fixing_plate_bundle(
        snapshot, geom, _selected(snapshot, geom), dest,
        dimensions=(800.,1600.,350.), sheet_thickness=2.,
    )


@pytest.mark.parametrize("factory,count",((_assembled,2),(_two_tier,4)))
def test_source_formed_ear_is_real_production_cutting_bend_and_side_marking(
    tmp_path,factory,count,
):
    snapshot, scene = _real_installed(factory)
    receipt = _run(snapshot,scene,tmp_path)
    assert len(receipt.formed_part_ids) == count
    assert receipt.source_sha256 == SOURCE_DXF_SHA256
    assert receipt.physical_contact_area_mm2 == pytest.approx(5632.*count)
    files = dict(receipt.output_paths)
    assert set(receipt.formed_part_ids).issubset(files)
    assert len(files) == len(list(tmp_path.glob("*.dxf")))
    for ear_id in receipt.formed_part_ids:
        dxf=ezdxf.readfile(files[ear_id]).modelspace()
        cutting=[entity for entity in dxf
                 if entity.dxftype()=="LWPOLYLINE"
                 and entity.dxf.layer.upper()=="CUTTING"
                 and entity.closed]
        bend=[entity for entity in dxf if entity.dxf.layer.upper()=="BEND"]
        assert len(cutting)==5 and len(bend)==1
        assert bend[0].dxftype()=="LINE"
        assert bend[0].dxf.start.y==pytest.approx(23.)
        assert bend[0].dxf.end.y==pytest.approx(23.)
        # Existing preview remains blocked; scoped manufacturing proof
        # must not turn source data into globally certified welding.
        preview=build_fixing_plate_source_render_data(ear_id,snapshot=snapshot)
        assert preview.metadata["formed_geometry_verified"] is False
        assert preview.metadata["weld_z_verified"] is False
        assert preview.metadata["manufacturing_ready"] is False
    names=[Path(v).name for v in files.values()]
    assert any("left_side" in n for n in names)
    assert any("right_side" in n for n in names)


@pytest.mark.parametrize("factory,count",((_assembled,2),(_two_tier,4)))
def test_original_selected_export_automatically_adds_formed_ear_sheets(
    tmp_path,factory,count,
):
    snap,geom=_real_installed(factory)
    calls=[]
    class Designer:
        _phase6_input_snapshot=snap
        designer_workspace=None
        def _phase6_resolve_manufacturing_geometry(self):
            calls.append("resolve")
            return geom
    host=SimpleNamespace(fold_designer_app=Designer())
    flags=dict(box_body=True,head=False,tail=False,door=False,base_plate=False,
               indicator_box=False,indicator_door=False)
    names, errors = _export_selected_resolved_parts(host,str(tmp_path),flags)
    assert errors==[]
    assert calls==["resolve"]
    assert len(names)==len(list(tmp_path.glob("*.dxf")))
    assert len([n for n in names if "fixing_plate" in n])==count
    assert "box_body_box_body_left_side.dxf" in names
    assert "box_body_box_body_right_side.dxf" in names


def test_missing_second_installed_base_cannot_issue_partial_ear_batch(tmp_path):
    snap,geom=_real_installed(_two_tier)
    stripped=replace(geom,parts=tuple(p for p in geom.parts
        if getattr(p,"part_key","")!="base_plate:nfb_layer:1"))
    with pytest.raises(ValueError,match="ACTUAL_BASE_PART_MISSING_OR_DUPLICATED"):
        _run(snap,stripped,tmp_path/"out")
    assert not (tmp_path/"out").exists()


def test_shifted_actual_base_z_refuses_contact_claim(tmp_path):
    snap,geom=_real_installed(_assembled)
    shifted=replace(geom,parts=tuple(
        replace(part, offset=(
            part.offset[0],part.offset[1],part.offset[2]+3.0
        )) if getattr(part,"part_key",None)=="base_plate" else part
        for part in geom.parts
    ))
    with pytest.raises(ValueError,match="ACTUAL_BASE_XYZ_DRIFT"):
        _run(snap,shifted,tmp_path/"out")
    assert not (tmp_path/"out").exists()


def test_last_dxf_reopen_failure_rolls_back_every_ear_and_side(tmp_path,monkeypatch):
    import ae_engine.receiving_fixed_plate_formed_manufacturing as module
    snap,geom=_real_installed(_two_tier)
    original=module.verify_saved_part_render_data_dxf
    called={"n":0}
    def fail_one(render,path):
        called["n"]+=1
        if "fixing_plate" in str(path):
            return SimpleNamespace(ok=False)
        return original(render,path)
    monkeypatch.setattr(module,"verify_saved_part_render_data_dxf",fail_one)
    target=tmp_path/"out"
    with pytest.raises(ValueError,match="EAR_FORM_MFG_DXF_ROUNDTRIP_FAILED"):
        _run(snap,geom,target)
    assert called["n"] > 0
    assert not list(target.glob("*.dxf"))


def test_unsubmitted_and_source_identity_drift_fail_before_output(tmp_path):
    snap,geom=_real_installed(_assembled)
    stale={**snap, "nfb_config_submitted":False}
    with pytest.raises(ValueError,match="MATCHING_SUBMITTED"):
        _run(stale,geom,tmp_path/"out")
    assert not (tmp_path/"out").exists()


def test_no_new_ui_button_or_full_cabinet_global_ear_bypass():
    import inspect
    import ae_engine.manufacturing_export as sink
    import gui_modules.project.export_actions as gui
    source=inspect.getsource(gui._export_selected_resolved_parts)
    guard=inspect.getsource(sink._reject_unapproved_nfb_pad_ear_manufacturing)
    assert "save_verified_receiving_formed_fixing_plate_bundle" in source
    assert "BASE_FIXING_PLATE_MANUFACTURING_UNVERIFIED" in guard


def test_ac13_selected_nfb_depth_moves_only_own_real_base_and_ear_z_without_pad(
    tmp_path,
):
    """One submitted model swap: the Base rederives its fold; EAR contact Z is fixed.

    Current #1502 correction supersedes the older "Base never moves" wording.
    A depth change must neither move the Inner Door nor fabricate an NFB PAD.
    This exercises original physical source DXF and scoped formed-EAR output;
    it does not certify arbitrary brand, solder/weld quality or full MFG-2.
    """
    from copy import deepcopy
    from ae_engine.receiving_tier_ear_z_targets import (
        resolve_receiving_tier_base_z_targets,
        resolve_receiving_tier_ear_contact_targets,
    )
    from tests.test_issue1503_ear_side_check_only_dxf import _actual

    first = _two_tier()
    altered = deepcopy(first)
    source_holes = altered["nfb_config"]["holes"]
    assert len(source_holes) == 2
    assert source_holes[1]["model_filename"] == "125_90X155_72.dxf"
    source_holes[1]["model_filename"] = "100_75X130_68.dxf"
    altered["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        altered["nfb_config"]
    )

    before = resolve_receiving_tier_base_z_targets(first)
    after = resolve_receiving_tier_base_z_targets(altered)
    assert [r.source_depths_mm for r in before] == [(107.0,), (72.0,)]
    assert [r.source_depths_mm for r in after] == [(107.0,), (68.0,)]
    assert all(r.physical_skin_z_resolved for r in (*before, *after))
    # Only the changed second NFB tier moves; the first is unchanged.
    assert after[0].world_offset_z_mm == pytest.approx(before[0].world_offset_z_mm)
    # The selected plate may rederive its CENTER folds; the offset is not a
    # fixed four-millimeter delta. Actual back skin and brand-max EAR must mate.
    assert abs(after[1].world_offset_z_mm - before[1].world_offset_z_mm) > 1e-6
    assert after[1].base_back_skin_world_z_mm == pytest.approx(
        before[1].base_back_skin_world_z_mm
    )

    original_ears = resolve_receiving_tier_ear_contact_targets(first)
    shifted_ears = resolve_receiving_tier_ear_contact_targets(altered)
    assert len(original_ears) == len(shifted_ears) == 4
    for previous, current in zip(original_ears, shifted_ears):
        tier = current.layer_index
        assert current.parent_base_id == previous.parent_base_id
        assert current.target_ear_contact_world_z_mm == pytest.approx(
            after[tier].base_back_skin_world_z_mm
        )
        assert previous.target_ear_contact_world_z_mm == pytest.approx(
            before[tier].base_back_skin_world_z_mm
        )
        assert current.base_skin_z_source_verified is True
        assert not current.manufacturing_ready  # target alone is not release
        # Even if the selected tier's fold placement moves, every ear
        # retains the SAME brand-wide maximum depth world Z.
        assert current.target_ear_contact_world_z_mm == pytest.approx(
            previous.target_ear_contact_world_z_mm
        )

    from ae_engine.assembly_placement import resolve_assembly_placement
    assert resolve_assembly_placement(
        first, "inner_door:upper:panel"
    ).world_offset == resolve_assembly_placement(
        altered, "inner_door:upper:panel"
    ).world_offset

    # Production source route, not a hand-built ear/side SVG or DTO:
    # actual cabinet SIDE skins → two physical BaseParts → real formed
    # fixing plates → original selected partial DXF export with reopen.
    saved, side_scene = _actual(lambda: deepcopy(altered))
    root = _source(saved)
    installed = expand_receiving_nfb_layer_parts(saved, (root,))
    assert len(installed) == 2
    assert [p.part_key for p in installed] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    ]
    assert [p.offset[2] for p in installed] == pytest.approx(
        [r.world_offset_z_mm for r in after]
    )
    assert all(p.offset[0] == pytest.approx(0.0) for p in installed)
    geometry = replace(side_scene, parts=side_scene.parts + tuple(installed))
    receipt = _run(saved, geometry, tmp_path / "depth_swap_output")
    assert len(receipt.formed_part_ids) == 4
    assert receipt.physical_contact_area_mm2 == pytest.approx(4 * 5632.0)
    files = dict(receipt.output_paths)
    assert set(receipt.formed_part_ids).issubset(files)
    assert all(Path(path).is_file() for path in files.values())
    assert all("pad" not in Path(path).stem.casefold() for path in files.values())
    for file_path in files.values():
        ezdxf.readfile(file_path)


def test_ac13_current_numeric_v5_submitted_tier_moves_real_base_and_ear_with_no_pad(tmp_path):
    """CURRENT per-brand numeric CSV V5 path, not merely legacy .dxf names.

    Only selected second-tier depth changes 72 -> 68. The Base rederives its
    actual fold; both EAR contact skins stay at brand-max Z. The inner door
    remains fixed and no PAD is released.
    """
    from copy import deepcopy
    from ae_engine.receiving_nfb_model_identity import selected_numeric_spec
    from ae_engine.receiving_tier_ear_z_targets import (
        resolve_receiving_tier_base_z_targets,
        resolve_receiving_tier_ear_contact_targets,
    )
    first = _two_tier()
    before_refs = ("nfbv5:士林:2P400", "nfbv5:士林:3P125SN")
    for hole, ref in zip(first["nfb_config"]["holes"], before_refs):
        hole["model_filename"] = ref
        hole["source_brand"] = "士林"
    first["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        first["nfb_config"]
    )
    second = deepcopy(first)
    second["nfb_config"]["holes"][1]["model_filename"] = "nfbv5:士林:2P125SN"
    second["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        second["nfb_config"]
    )
    for ref, expected in (
        ("nfbv5:士林:2P400", 107.0),
        ("nfbv5:士林:3P125SN", 72.0),
        ("nfbv5:士林:2P125SN", 68.0),
    ):
        spec = selected_numeric_spec("士林", ref)
        assert spec is not None
        assert spec.depth_mm == pytest.approx(expected)

    before, after = (resolve_receiving_tier_base_z_targets(s)
                     for s in (first, second))
    assert [x.source_depths_mm for x in before] == [(107.0,), (72.0,)]
    assert [x.source_depths_mm for x in after] == [(107.0,), (68.0,)]
    assert all(x.physical_skin_z_resolved for x in (*before, *after))
    assert after[0].world_offset_z_mm == pytest.approx(before[0].world_offset_z_mm)
    # The selected plate may rederive its CENTER folds; the offset is not a
    # fixed four-millimeter delta. Actual back skin and brand-max EAR must mate.
    assert abs(after[1].world_offset_z_mm - before[1].world_offset_z_mm) > 1e-6
    assert after[1].base_back_skin_world_z_mm == pytest.approx(
        before[1].base_back_skin_world_z_mm
    )
    old_ears, new_ears = (resolve_receiving_tier_ear_contact_targets(s)
                          for s in (first, second))
    assert len(old_ears) == len(new_ears) == 4
    for old, new in zip(old_ears, new_ears):
        idx = new.layer_index
        assert old.parent_base_id == new.parent_base_id
        assert new.target_ear_contact_world_z_mm == pytest.approx(
            after[idx].base_back_skin_world_z_mm
        )
        assert new.base_skin_z_source_verified
        assert not new.manufacturing_ready
        delta = abs(new.target_ear_contact_world_z_mm -
                    old.target_ear_contact_world_z_mm)
        assert delta == pytest.approx(0.0)  # brand-max contact never follows selected NFB

    assert resolve_assembly_placement(
        first, "inner_door:upper:panel"
    ).world_offset == resolve_assembly_placement(
        second, "inner_door:upper:panel"
    ).world_offset
    saved, sides = _actual(lambda: deepcopy(second))
    root = _source(saved)
    installed = expand_receiving_nfb_layer_parts(saved, (root,))
    assert len(installed) == 2
    assert [p.offset[2] for p in installed] == pytest.approx(
        [x.world_offset_z_mm for x in after]
    )
    scene = replace(sides, parts=sides.parts + tuple(installed))
    receipt = _run(saved, scene, tmp_path / "v5_depth_swap")
    assert len(receipt.formed_part_ids) == 4
    assert receipt.physical_contact_area_mm2 == pytest.approx(4 * 5632.0)
    assert set(receipt.formed_part_ids).issubset(dict(receipt.output_paths))
    assert all("pad" not in Path(path).stem.lower()
               for _, path in receipt.output_paths)
    for _, path in receipt.output_paths:
        ezdxf.readfile(path)


def test_swt09_original_upper_lower_trace_and_current_v5_base_ear_depth_never_release_pad(tmp_path):
    """The original LOWER source cannot become a PAD; V5 rederives real Base but not EAR contact Z.

    This is source-scoped actual parser + physical assembly + normal DXF
    reopening and negative manufacturer proof, NOT a factory PAD release.
    """
    from copy import deepcopy
    from ae_engine.receiving_nfb_source_regions import (
        UPPER, LOWER, OBSERVED, DEFERRED,
    )
    from tests.test_issue1502_nfb_source_regions import _file, _read
    from ae_engine.receiving_tier_ear_z_targets import (
        resolve_receiving_tier_base_z_targets,
        resolve_receiving_tier_ear_contact_targets,
    )
    from ae_engine.receiving_nfb_model_identity import selected_numeric_spec
    from ae_engine.manufacturing_export import save_resolved_manufacturing_geometry_dxf

    # Actual native DXF entity/handle reader; UPPER/L0 and LOWER/L1 are
    # provenance, not a permission to cut a free-standing PAD sheet.
    source_path, upper, lower, digest = _file(tmp_path)
    exact_bytes = source_path.read_bytes()
    observed = _read(source_path, upper, lower, digest)
    assert observed.upper.region == UPPER
    assert observed.upper.region_status == OBSERVED
    assert observed.lower.region == LOWER
    assert observed.lower.region_status == DEFERRED
    assert observed.upper.source_sha256 == observed.lower.source_sha256 == digest
    assert observed.upper.reference_handle != observed.lower.reference_handle
    assert set(observed.upper.entity_handles).isdisjoint(observed.lower.entity_handles)
    assert not observed.manufacturing_ready
    assert not observed.lower.manufacturing_ready
    assert not hasattr(observed.lower, "render_data")
    assert not hasattr(observed.lower, "manufacturing_scene")
    assert source_path.read_bytes() == exact_bytes

    # CURRENT manufacturer numeric CSV V5, independent of old DXF regions.
    # Actual selected depth changes only the second tier; first + door hold.
    before = _two_tier()
    for hole, ref in zip(before["nfb_config"]["holes"], (
        "nfbv5:士林:2P400", "nfbv5:士林:3P125SN",
    )):
        hole["model_filename"] = ref
        hole["source_brand"] = "士林"
    before["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        before["nfb_config"]
    )
    after = deepcopy(before)
    after["nfb_config"]["holes"][1]["model_filename"] = "nfbv5:士林:2P125SN"
    after["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        after["nfb_config"]
    )
    assert selected_numeric_spec("士林", "nfbv5:士林:3P125SN").depth_mm == 72
    assert selected_numeric_spec("士林", "nfbv5:士林:2P125SN").depth_mm == 68
    prior, current = (resolve_receiving_tier_base_z_targets(s)
                      for s in (before, after))
    assert [x.source_depths_mm for x in prior] == [(107.0,), (72.0,)]
    assert [x.source_depths_mm for x in current] == [(107.0,), (68.0,)]
    assert all(x.physical_skin_z_resolved for x in (*prior, *current))
    assert current[0].world_offset_z_mm == pytest.approx(prior[0].world_offset_z_mm)
    # The selected plate may rederive its CENTER folds; the offset is not a
    # fixed four-millimeter delta. Actual back skin and brand-max EAR must mate.
    assert abs(current[1].world_offset_z_mm - prior[1].world_offset_z_mm) > 1e-6
    assert current[1].base_back_skin_world_z_mm == pytest.approx(
        prior[1].base_back_skin_world_z_mm
    )
    old_ears, new_ears = (resolve_receiving_tier_ear_contact_targets(s)
                          for s in (before, after))
    assert len(old_ears) == len(new_ears) == 4
    for old, new in zip(old_ears, new_ears):
        idx = new.layer_index
        assert new.parent_base_id == old.parent_base_id
        assert new.target_ear_contact_world_z_mm == pytest.approx(
            current[idx].base_back_skin_world_z_mm
        )
        assert abs(new.target_ear_contact_world_z_mm -
                   old.target_ear_contact_world_z_mm) == pytest.approx(
            0.0  # brand-wide maximum depth fixes all EAR contact Z
        )
        assert not new.manufacturing_ready
    assert resolve_assembly_placement(
        before, "inner_door:upper:panel"
    ).world_offset == resolve_assembly_placement(
        after, "inner_door:upper:panel"
    ).world_offset

    saved, side_scene = _actual(lambda: deepcopy(after))
    physical = expand_receiving_nfb_layer_parts(saved, (_source(saved),))
    assert [part.offset[2] for part in physical] == pytest.approx(
        [x.world_offset_z_mm for x in current]
    )
    scene = replace(side_scene, parts=side_scene.parts + tuple(physical))
    receipt = _run(saved, scene, tmp_path / "valid_ear_side_only")
    assert len(receipt.formed_part_ids) == 4
    assert set(receipt.formed_part_ids).issubset(dict(receipt.output_paths))
    for _, out_path in receipt.output_paths:
        assert "pad" not in Path(out_path).stem.lower()
        ezdxf.readfile(out_path)

    # Explicit forged unapproved PAD must fail before ANY DXF write.
    pad = SimpleNamespace(parts=(SimpleNamespace(
        part_key="nfb_pad:shim_1",
        render_data=SimpleNamespace(metadata={
            "stable_id": "nfb_pad:shim_1",
            "nfb_pad_manufacturing_ready": True,
            "nfb_pad_mfg2_release_approved": True,
        }),
    ),))
    forbidden = tmp_path / "forged_pad"
    with pytest.raises(ValueError, match="NFB_PAD_EAR_PHYSICAL_EVIDENCE_UNAPPROVED"):
        save_resolved_manufacturing_geometry_dxf(
            pad, forbidden,
            save_part_render_data_dxf=lambda *args, **kwargs: pytest.fail(
                "forged PAD may not reach the DXF writer"
            ),
            box_body_physical_piece_roles=(), part_only=True,
        )
    assert not forbidden.exists()
