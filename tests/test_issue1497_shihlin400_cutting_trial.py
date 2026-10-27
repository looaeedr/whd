# -*- coding: utf-8 -*-
"""#1497: Shihlin 400 exemplar plus generic data-only source expansion."""
from dataclasses import replace
from pathlib import Path

import pytest

from ae_engine.inner_door_panels import derive_inner_door_panel
from ae_engine.receiving_nfb_cutting_preflight import (
    NfbExistingCuttingClaim, NfbUpperOpeningRequest,
)
from ae_engine.receiving_nfb_cutting_manufacturing import (
    TRIAL_ONLY, read_nfb_upper_source_profiles, trial_nfb_upper_cutting_on_inner_door,
)
from ae_engine.receiving_nfb_dxf_source import NfbSourceEntity, NfbSourceInventory
from ae_engine.receiving_nfb_index_sources import unique_nfb_dxfs_from_switch_index
from ae_engine.manufacturing_api import build_inner_door_panel_render_data, save_part_render_data_dxf
from ae_engine.sheetmetal_drawing import PolylinePrimitive

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "tests/fixtures/receiving_nfb_upper_source_profiles.json"
SHA = "8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3"
CENTER = (3771.967234, 2608.809181)


def _panel():
    return derive_inner_door_panel(
        "upper", cell_key="0:0", width=689, height=1041, thickness=2,
        fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
    )


def _inventory():
    x, y = CENTER
    verts = ((x-28.5, y-48), (x+28.5, y-48),
             (x+28.5, y+48), (x-28.5, y+48))
    entity = NfbSourceEntity(
        source_id=f"{SHA}:585", source_hash=SHA,
        source_path="400_140X257_107(1).dxf",
        group_id="modelspace", dxf_type="LWPOLYLINE", layer="0",
        layer_color_aci=7, entity_color_aci=150, effective_color_aci=150,
        color_authority="ENTITY", handle_path="585",
        vertices_xy=verts, bulges=(0., 0., 0., 0.), closed=True,
    )
    return NfbSourceInventory(
        source_path=entity.source_path, source_sha256=SHA,
        source_id=f"NFB-DXF:{SHA}", status="SOURCE_OBSERVED_UNCERTIFIED",
        entities=(entity,), diagnostics=(), process_aci_entity_counts=((150,1),),
        unresolved_color_entities=0, grouped_entity_counts=(("modelspace",1),),
    )


def _catalog(tmp_path):
    index = tmp_path / "開關索引.csv"
    index.write_text(
        "圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "S400,400_140X257_107.dxf,107,無對應檔案,,無對應檔案,\n"
        "S400b,400_140X257_107.dxf,107,無對應檔案,,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    catalog = unique_nfb_dxfs_from_switch_index(index)
    assert len(catalog.sources) == 1
    assert len(catalog.sources[0].links) == 2
    return catalog


def _req(**kwargs):
    request = NfbUpperOpeningRequest(
        physical_hole_id="nfb:upper:layer:1:unit:1",
        target_part_id="inner_door:upper:panel",
        source_sha256=SHA, source_handle="585",
        source_region="UPPER", source_aci=150,
        source_outline_xy=(), source_center_xy=CENTER,
        source_profile_closed=True, source_bulges=(),
        rotation_deg=0, uv_center_x=361.5, uv_center_y=563.5,
        x_rule_revision="SHADOW_ONLY_NOT_CERTIFIED",
        y_rule_revision="WHD-RECEIVING-NFB-Y-1100-V1",
        model_filename="400_140X257_107.dxf",
    )
    return replace(request, **kwargs)


def _trial(tmp_path, *requests, inventory=None, profile=None, claims=()):
    return trial_nfb_upper_cutting_on_inner_door(
        _panel(), requests or (_req(),),
        catalog=_catalog(tmp_path),
        inventory=inventory or _inventory(),
        profile=profile or read_nfb_upper_source_profiles(PROFILE)[0],
        existing_claims=claims,
    )


@pytest.mark.parametrize("angle,dimensions", [
    (0, (57, 96)), (90, (96, 57)),
    (180, (57, 96)), (270, (96, 57)),
])
def test_real_upper_color150_trial_contour_is_added_to_canonical_finalscene(
        tmp_path, angle, dimensions):
    panel = _panel()
    original = build_inner_door_panel_render_data(panel)
    result = _trial(tmp_path, _req(rotation_deg=angle))
    assert result.status == TRIAL_ONLY
    assert result.manufacturing_ready is False
    assert result.render_data.metadata["nfb_trial_export_approved"] is False
    cutting = [p for p in result.render_data.scene.primitives
               if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING" and p.closed]
    assert len(cutting) == 2  # existing full blank + ONE actual upper contour
    hole = cutting[-1]
    assert hole.color == 3
    xs = [p.x for p in hole.points]
    ys = [p.y for p in hole.points]
    assert (max(xs)-min(xs), max(ys)-min(ys)) == pytest.approx(dimensions)
    assert ((max(xs)+min(xs))/2, (max(ys)+min(ys))/2) == pytest.approx((361.5, 563.5))
    # A trial must leave legacy FinalScene and the physical panel unchanged.
    assert build_inner_door_panel_render_data(panel).scene.primitives == original.scene.primitives
    assert result.render_data.unfolded_topology == original.unfolded_topology


def test_trial_is_actual_dxf_cutting_geometry_but_explicitly_not_production(tmp_path):
    import ezdxf
    result = _trial(tmp_path)
    outfile = tmp_path / "shihlin400_TRIAL_NOT_FOR_MANUFACTURING.dxf"
    save_part_render_data_dxf(result.render_data, outfile)
    msp = ezdxf.readfile(outfile).modelspace()
    cut = [e for e in msp if e.dxftype() == "LWPOLYLINE"
           and e.dxf.layer == "CUTTING" and e.closed]
    assert len(cut) == 2
    assert cut[-1].dxf.color == 3
    assert len(list(cut[-1].get_points("xy"))) == 4


def test_bad_or_missing_source_and_unknown_model_fail_closed(tmp_path):
    profile = read_nfb_upper_source_profiles(PROFILE)[0]
    with pytest.raises(ValueError, match="source SHA"):
        _trial(tmp_path, inventory=replace(_inventory(), source_sha256="0"*64))
    with pytest.raises(ValueError, match="source identity"):
        _trial(tmp_path, _req(source_handle="585X"))
    with pytest.raises(ValueError, match="source not present"):
        _trial(tmp_path, profile=replace(profile, indexed_filename="unindexed.dxf"))
    with pytest.raises(ValueError, match="contour differs"):
        _trial(tmp_path, profile=replace(profile, upper_size_mm=(58.,96.)))
    with pytest.raises(ValueError, match="blocked"):
        _trial(tmp_path, _req(uv_center_x=None))


def test_duplicate_legacy_and_colliding_q16_batch_is_atomic(tmp_path):
    one = _req()
    two = replace(one, physical_hole_id="nfb:upper:layer:2:unit:1", uv_center_x=600.)
    result = _trial(tmp_path, one, two)
    assert len(result.physical_hole_ids) == 2
    with pytest.raises(ValueError, match="blocked"):
        _trial(tmp_path, one, replace(two, uv_center_x=361.5))
    with pytest.raises(ValueError, match="blocked"):
        _trial(tmp_path, one, replace(two, physical_hole_id=one.physical_hole_id))
    legacy = NfbExistingCuttingClaim(
        physical_hole_id=one.physical_hole_id, part_id=_panel().stable_id,
        outline_uv_xy=((335,520),(390,520),(390,600),(335,600)),
    )
    with pytest.raises(ValueError, match="blocked"):
        _trial(tmp_path, one, claims=(legacy,))


def test_other_brand_models_are_only_a_new_source_profile_not_hardcoded_branch(tmp_path):
    # One shared adapter; simply adding a source record is sufficient to
    # enter source verification (not to claim production approval).
    profiles = read_nfb_upper_source_profiles(PROFILE)
    assert len(profiles) == 1
    assert profiles[0].indexed_filename == "400_140X257_107.dxf"
    assert profiles[0].source_alias_status == "SOURCE_ALIAS_SHA256_IDENTICAL"


@pytest.mark.parametrize("bad_width", (
    float("nan"), float("inf"), float("-inf"), 10 ** 400,
    True, "57", None,
))
@pytest.mark.parametrize("position", (0, 1))
def test_1504_legacy_color150_profile_rejects_nonfinite_or_coerced_mm(
    tmp_path, bad_width, position,
):
    """The old JSON profile is no more trusted than current V5 source CSV.

    A malformed profile must fail before any world-X/pivot or physical
    manufacturing step. No new manufacturing dimensions are inferred.
    """
    import json

    original = read_nfb_upper_source_profiles(PROFILE)
    assert len(original) == 1
    assert original[0].upper_size_mm == (57.0, 96.0)
    document = json.loads(PROFILE.read_text(encoding="utf-8"))
    document["profiles"][0]["upper_size_mm"][position] = bad_width
    forged = tmp_path / "untrusted_upper_profile.json"
    forged.write_text(
        json.dumps(document, ensure_ascii=False), encoding="utf-8",
    )
    with pytest.raises(ValueError, match="NFB upper Color150 dimensions invalid"):
        read_nfb_upper_source_profiles(forged)
