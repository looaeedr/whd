# -*- coding: utf-8 -*-
"""#1502 current NFB CSV is canonical source of normal 2D/3D/assembly screws."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.manufacturing_api import build_part_render_data
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_layer_physical_parts import (
    expand_receiving_nfb_layer_parts,
)
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from phase6_final_scene_contracts import AssemblyScenePart
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_source_derived_center_base import _spec
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def _make(snap):
    spec = _spec(snap)
    placement = resolve_assembly_placement(snap, "base_plate")
    return AssemblyScenePart(
        part_key="base_plate", render_data=build_part_render_data(spec),
        x_profile=(), y_profile=(), placement="offset",
        offset=placement.world_offset,
    )


def _screws(part):
    return tuple(x for x in part.render_data.scene.primitives
                 if isinstance(x, CirclePrimitive)
                 and x.source_type == "NFB_V5_NUMERIC_BASE_TRIAL")


def _ears(part):
    return tuple(x for x in part.render_data.scene.primitives
                 if isinstance(x, PolylinePrimitive)
                 and x.layer == "CUTTING" and x.closed)


def test_committed_single_csv_is_automatically_cut_in_normal_source_scene():
    snap = _current()
    assert "receiving_base_plate" not in snap
    original = _make(snap)
    other = SimpleNamespace(part_key="box_body", render_data=object())
    changed = apply_committed_csv_v5_to_canonical_parts(snap, (original, other))
    assert len(changed) == 2 and changed[1] is other
    base = changed[0]
    assert base.part_key == original.part_key
    assert base.offset == original.offset
    assert len(_ears(base)) == len(_ears(original)) == 5
    assert len(_screws(base)) == 8
    assert base.render_data.material.area < original.render_data.material.area
    assert base.render_data.unfolded_topology == original.render_data.unfolded_topology
    assert base.render_data.metadata["nfb_trial_export_approved"] is False
    assert base.render_data.metadata["nfb_v5_source_models"] == (
        ("士林", "2P400"), ("士林", "3P125SN"),
    )


def test_committed_two_tiers_share_one_csv_datum_and_get_own_screw_sets():
    snap = _two_tier()
    for index, row in enumerate(snap["nfb_config"]["holes"]):
        row.update({
            "model_filename": ("nfbv5:士林:2P400", "nfbv5:士林:3P125SN")[index],
            "source_brand": "士林",
            "manual_x_state": "CONFIRMED",
            "manual_x_mm": (-100. if index == 0 else 100.),
            "datum_revision": "CURRENT_CSV_X",
            "datum_snapshot": {"w": 800., "inner_door": "upper"},
        })
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    blanks = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    assert len(blanks) == 2
    processed = apply_committed_csv_v5_to_canonical_parts(snap, blanks)
    assert tuple(v.part_key for v in processed) == (
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    )
    assert [len(_screws(p)) for p in processed] == [4, 4]
    assert [_ears(p) for p in processed] == [_ears(p) for p in blanks]
    assert [p.offset for p in processed] == [p.offset for p in blanks]
    assert set(v.source_id for v in _screws(processed[0])).isdisjoint(
        v.source_id for v in _screws(processed[1])
    )


def test_unconfirmed_csv_keeps_existing_editable_sheet_without_made_up_x():
    snap = _current()
    original = _make(snap)
    snap["nfb_config"]["holes"][0]["manual_x_state"] = "UNVERIFIED_BASIS"
    snap["nfb_config"]["holes"][0]["manual_x_mm"] = None
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    assert apply_committed_csv_v5_to_canonical_parts(snap, (original,)) == (original,)


def test_legacy_native_dxf_project_keeps_old_scene_not_violated_by_csv_projection():
    snap = _two_tier()
    blanks = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    assert apply_committed_csv_v5_to_canonical_parts(snap, blanks) == blanks


def test_wrong_bay_identity_or_tampered_normal_base_rejected_before_overlay():
    snap = _current()
    original = _make(snap)
    snap["_receiving_runtime_selection"]["bay_id"] = "wrong"
    with pytest.raises(ValueError, match="IDENTITY_DRIFT"):
        apply_committed_csv_v5_to_canonical_parts(snap, (original,))
    snap = _current()
    original = _make(snap)
    broken = replace(original, offset=(0., original.offset[1] + 15., original.offset[2]))
    with pytest.raises(ValueError, match="安裝位置"):
        apply_committed_csv_v5_to_canonical_parts(snap, (broken,))
    other = replace(original, render_data=replace(
        original.render_data,
        metadata={**original.render_data.metadata,
                  "receiving_bend_pattern": "RIGHT_FLAT_SIDE"},
    ))
    with pytest.raises(ValueError, match="來源 PartSpec"):
        apply_committed_csv_v5_to_canonical_parts(snap, (other,))


def test_resolver_has_normal_source_seam_not_a_new_operator_export_button():
    import inspect
    import phase6_manufacturing_service
    from gui_modules.application import receiving_multi_settings_window
    resolver = inspect.getsource(phase6_manufacturing_service.resolve)
    window = inspect.getsource(receiving_multi_settings_window)
    assert "apply_committed_csv_v5_to_canonical_parts" in resolver
    assert "expand_receiving_nfb_layer_parts" in resolver
    assert resolver.index("expand_receiving_nfb_layer_parts") < resolver.index(
        "apply_committed_csv_v5_to_canonical_parts"
    )
    assert "輸出 CSV 底板 DXF（單片）" not in window


def test_existing_editor_csv_feature_is_alias_not_duplicate_source():
    """Current Hole Editor CSV opening exists before normal Phase6 resolve."""
    from ae_engine.receiving_nfb_v5_part_only_manufacturing import (
        _current_single_tier_csv_holes,
    )
    from ae_engine.receiving_nfb_v5_configured_inner_door import (
        trial_configured_nfb_v5_inner_door_render_data,
    )
    from ae_engine.cabinet_types.policy import derive_inner_door_panels
    from ae_engine.sheetmetal_feature_core import (
        FeatureAnchor, ProfileFeature,
    )
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data

    snap = _current()
    holes, _, _ = _current_single_tier_csv_holes(snap, "upper")
    proof = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=holes,
    )
    panel = next(p for p in derive_inner_door_panels(snap)
                 if p.stable_id == proof.part_id)
    delta_x = float(panel.fold_left) - float(panel.thickness)
    delta_y = float(panel.fold_bottom) - float(panel.thickness)
    aliases = tuple(
        ProfileFeature(
            points=tuple(Vec2(float(x)-delta_x, float(y)-delta_y)
                         for x,y in pattern.opening_uv_mm),
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(0.,0.), layer="CUTTING",
            source_type="NFB_CSV_SOURCE",
            source_params=(("part_id",panel.stable_id),
                           ("brand",pattern.brand),
                           ("model",pattern.model)),
        )
        for pattern in proof.patterns
    )
    snap["part_features"] = {panel.stable_id: aliases}
    door = AssemblyScenePart(
        part_key=panel.stable_id,
        render_data=build_inner_door_panel_render_data(panel),
        x_profile=(),y_profile=(),placement="offset",offset=(0.,0.,0.),
    )
    base = _make(snap)
    output = apply_committed_csv_v5_to_canonical_parts(snap, (door, base))
    assert output[0].part_key == panel.stable_id
    assert output[0].render_data.scene.primitives == proof.render_data.scene.primitives
    assert output[0].render_data.material.equals(proof.render_data.material)
    assert len(_screws(output[1])) == 8
    # The committed source features are never edited, cleared or duplicated.
    assert snap["part_features"][panel.stable_id] == aliases


def test_non_csv_editor_features_are_not_erased_by_source_projection():
    from ae_engine.receiving_nfb_committed_final_scene import (
        _without_derived_csv_door_features,
    )
    snap = _current()
    other = SimpleNamespace(source_type="USER_DRAWN_OTHER")
    derived = SimpleNamespace(source_type="NFB_CSV_SOURCE")
    snap["part_features"] = {"inner_door:upper:panel": (derived, other)}
    checked = _without_derived_csv_door_features(snap, "upper")
    assert checked["part_features"]["inner_door:upper:panel"] == (other,)
    assert snap["part_features"]["inner_door:upper:panel"] == (derived, other)


def test_saved_native_hole_editor_position_drives_screws_without_second_x_input():
    from hashlib import sha256
    from ae_engine.receiving_nfb_v5_part_only_manufacturing import (
        _current_single_tier_csv_holes,
    )
    from ae_engine.receiving_nfb_v5_configured_inner_door import (
        trial_configured_nfb_v5_inner_door_render_data,
    )
    from ae_engine.receiving_nfb_numeric_catalog import brand_csv_path
    from ae_engine.cabinet_types.policy import derive_inner_door_panels
    from ae_engine.sheetmetal_feature_core import (
        FeatureAnchor, ProfileFeature,
    )
    from ae_engine.sheetmetal_geometry import Vec2

    snap = _current()
    original_holes, _, _ = _current_single_tier_csv_holes(snap, "upper")
    proof = trial_configured_nfb_v5_inner_door_render_data(
        snap, "upper", holes=original_holes,
    )
    panel = next(p for p in derive_inner_door_panels(snap)
                 if p.stable_id == proof.part_id)
    aliases = []
    for row, pattern in zip(snap["nfb_config"]["holes"], proof.patterns):
        aliases.append(ProfileFeature(
            points=tuple(Vec2(float(x)-panel.fold_left+panel.thickness,
                              float(y)-panel.fold_bottom+panel.thickness)
                         for x,y in pattern.opening_uv_mm),
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(0.,0.), layer="CUTTING",
            source_type="NFB_CSV_SOURCE",
            source_params=(
                ("part_id", panel.stable_id),
                ("brand", pattern.brand),
                ("model", pattern.model),
                ("csv_sha256",
                 sha256(brand_csv_path(pattern.brand).read_bytes()).hexdigest()),
                ("layer_index", 0),
                ("slot_index", row["slot_index"]),
            ),
        ))
    snap["part_features"] = {panel.stable_id: tuple(aliases)}
    for row in snap["nfb_config"]["holes"]:
        row["manual_x_state"] = "UNVERIFIED_BASIS"
        row["manual_x_mm"] = None
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    original = _make(snap)
    processed = apply_committed_csv_v5_to_canonical_parts(snap, (original,))
    assert len(_screws(processed[0])) == 8
    assert tuple(aliases) == snap["part_features"][panel.stable_id]
    assert processed[0].render_data.metadata["nfb_v5_hole_ids"] == (
        "nfb:0", "nfb:1",
    )


def test_changed_csv_hash_or_ambiguous_editor_feature_must_not_generate_screws():
    from ae_engine.receiving_nfb_committed_final_scene import (
        _source_world_x_from_committed_editor_feature,
    )
    from ae_engine.cabinet_types.policy import derive_inner_door_panels
    snap = _current()
    panel = next(p for p in derive_inner_door_panels(snap)
                 if str(p.cell_key).split(":")[-1] == "0")
    row = snap["nfb_config"]["holes"][0]
    assert _source_world_x_from_committed_editor_feature(
        snap,panel,row,brand="士林",model="2P400",
    ) is None


def test_frozen_manufacturing_dto_recovers_typed_hole_editor_features():
    from phase6_manufacturing_contracts import (
        freeze_manufacturing_value, thaw_manufacturing_value,
    )
    from ae_engine.receiving_nfb_committed_final_scene import (
        _physical_feature_from_transport, _without_derived_csv_door_features,
    )
    from ae_engine.sheetmetal_feature_core import (
        ProfileFeature, FeatureAnchor,
    )
    from ae_engine.sheetmetal_geometry import Vec2
    source = ProfileFeature(
        points=(Vec2(40.,40.), Vec2(60.,40.),
                Vec2(60.,70.), Vec2(40.,70.)),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(0.,0.),
        layer="CUTTING", source_type="NFB_CSV_SOURCE",
        source_params=(("part_id","inner_door:upper:panel"),),
    )
    raw = thaw_manufacturing_value(freeze_manufacturing_value(source))
    assert isinstance(raw, dict)
    assert raw["__dataclass_type__"].endswith(".ProfileFeature")
    assert _physical_feature_from_transport(raw) == source
    saved = _current()
    saved["part_features"] = {"inner_door:upper:panel": (source,)}
    frozen = thaw_manufacturing_value(freeze_manufacturing_value(saved))
    projected = _without_derived_csv_door_features(frozen, "upper")
    assert projected["part_features"]["inner_door:upper:panel"] == ()
    assert frozen["part_features"]["inner_door:upper:panel"][0] == raw
