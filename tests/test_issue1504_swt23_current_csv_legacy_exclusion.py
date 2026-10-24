# -*- coding: utf-8 -*-
"""#1504 SWT-AC-23 — current numeric CSV, native legacy Feature and source ownership.

Uses WHD's real submitted Receiving family, canonical FinalScene and DXF
operator path.  No historic supplier-DXF manufacturing approval is inferred.
"""
from copy import deepcopy

import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.receiving_layout import update_receiving_bay
from ae_engine.sheetmetal_feature_core import FeatureAnchor, ProfileFeature
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.receiving_nfb_v5_part_only_manufacturing import (
    _current_single_tier_csv_holes,
)
from ae_engine.receiving_nfb_v5_configured_inner_door import (
    trial_configured_nfb_v5_inner_door_render_data,
)
from ae_engine.receiving_nfb_legacy_feature_bridge import (
    existing_inner_door_feature_finalscene,
)
from tests.test_issue1504_ac29_swt19_v5_reload_source_rederive import (
    _valid_project, _reloaded_project,
)
from tests.test_issue1502_current_csv_original_pair_dxf import _scene, _export
from tests.test_issue1504_ac27_swt06_v5_physical_q16_transactions import (
    _save, _files, _shapes,
)


def _door_panel(snapshot):
    (panel,) = tuple(
        p for p in derive_inner_door_panels(snapshot)
        if p.inner_door_id == "upper"
        and str(p.cell_key).split(":")[-1] == "0"
    )
    return panel


def _feature(points, source_type):
    return ProfileFeature(
        points=tuple(Vec2(float(x), float(y)) for x, y in points),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(0., 0.),
        layer="CUTTING",
        source_type=source_type,
        source_params=(),
    )


def _csv_exact_native_opening(snapshot, panel, *, source_type):
    holes, _, _ = _current_single_tier_csv_holes(snapshot, "upper")
    proof = trial_configured_nfb_v5_inner_door_render_data(
        snapshot, "upper", holes=holes,
    )
    pattern = proof.patterns[0]
    # Real Hole Editor coordinates are on the finished face, not in
    # unfolded UV. Derive, never hard-code a WHD hole position.
    dx = float(panel.fold_left) - float(panel.thickness)
    dy = float(panel.fold_bottom) - float(panel.thickness)
    return _feature(
        tuple((float(x) - dx, float(y) - dy)
              for x, y in pattern.opening_uv_mm),
        source_type,
    )


def test_swt23_current_csv_same_physical_legacy_hole_blocks_without_writing(tmp_path):
    snapshot = _valid_project()
    panel = _door_panel(snapshot)
    old_parts = _scene(snapshot)
    original_geometry = tuple(
        tuple(part.render_data.scene.primitives) for part in old_parts
    )
    legacy = _csv_exact_native_opening(
        snapshot, panel, source_type="USER_DRAWN_LEGACY"
    )
    snapshot["part_features"] = {panel.stable_id: (legacy,)}
    preserved = deepcopy(snapshot)
    with pytest.raises(ValueError, match="既有|碰撞|collision|overlap"):
        _scene(snapshot)
    target = tmp_path / "denied"
    target.mkdir()
    with pytest.raises(ValueError):
        _export(snapshot, old_parts, target)
    assert snapshot == preserved
    assert not list(target.glob("*.dxf"))
    assert tuple(tuple(p.render_data.scene.primitives) for p in old_parts) == original_geometry

    # NFB_CSV_SOURCE is only a derived Hole Editor alias: its exact opening
    # must not become a second CUTTING hole.
    # Re-label the already source-derived EXACT SAME geometry rather than
    # calling the V5 resolver again against the intentionally colliding
    # legacy owner above. That earlier rejection is expected and remains
    # a separate required assertion.
    from dataclasses import replace
    alias = replace(legacy, source_type="NFB_CSV_SOURCE")
    alias_source = deepcopy(snapshot)
    alias_source["part_features"][panel.stable_id] = (alias,)
    resolved = _scene(alias_source)
    assert tuple(p.part_key for p in resolved) == tuple(p.part_key for p in old_parts)
    assert tuple(p.render_data.scene.primitives for p in resolved) == tuple(
        p.render_data.scene.primitives for p in old_parts
    )
    assert alias_source["part_features"][panel.stable_id] == (alias,)


def test_swt23_unrelated_legacy_cutting_survives_current_csv_save_reload_and_unconfigure(
    tmp_path,
):
    snapshot = _valid_project()
    panel = _door_panel(snapshot)
    old_parts = _scene(snapshot)
    # A native user CUTTING hole in the real finished inner-door face; it
    # is independent of the NFB's source-owned aperture and hole IDs.
    legacy = _feature(
        ((90., 90.), (110., 90.), (110., 110.), (90., 110.)),
        "USER_DRAWN_LEGACY",
    )
    snapshot["part_features"] = {panel.stable_id: (legacy,)}
    before = deepcopy(snapshot)
    with_legacy = _scene(snapshot)
    assert snapshot == before
    assert with_legacy[0].part_key == panel.stable_id
    assert len(with_legacy[0].render_data.scene.primitives) == (
        len(old_parts[0].render_data.scene.primitives) + 1
    )
    assert with_legacy[1].render_data.scene.primitives == old_parts[1].render_data.scene.primitives

    first = _save(snapshot, with_legacy, tmp_path / "first")
    first_shapes = tuple(_shapes(path) for path in _files(first))
    restored, project_path = _reloaded_project(snapshot, tmp_path)
    assert project_path.is_file()
    assert restored["part_features"][panel.stable_id]
    after_reload = _scene(restored)
    second = _save(restored, after_reload, tmp_path / "reloaded")
    assert tuple(_shapes(path) for path in _files(second)) == first_shapes
    assert tuple(p.render_data.scene.primitives for p in after_reload) == tuple(
        p.render_data.scene.primitives for p in with_legacy
    )

    unconfigured = deepcopy(restored)
    unconfigured["receiving_layout"] = update_receiving_bay(
        unconfigured["receiving_layout"], set_index=0, bay_index=0,
        nfb_config_submitted=False,
    )
    unconfigured.pop("nfb_config", None)
    unconfigured.pop("nfb_config_submitted", None)
    assert "nfb_config" not in unconfigured["receiving_layout"]["sets"][0]["bays"][0]
    assert unconfigured["part_features"][panel.stable_id]
    old_feature_scene = existing_inner_door_feature_finalscene(
        unconfigured, _door_panel(unconfigured),
    )
    assert old_feature_scene is not None
    assert old_feature_scene.metadata["nfb_legacy_feature_count"] == 1
    assert first_shapes == tuple(_shapes(path) for path in _files(first))


@pytest.mark.parametrize("invalid_v5", [
    "nfbv5:士林:",
    "nfbv5:士林:BAD/KEY",
    "nfbv5:士林:BAD:EXTRA",
])
def test_ac52_all_invalid_v5_refs_cannot_silently_fall_back_to_blank_finalscene(
    invalid_v5, tmp_path,
):
    """#1504 AC52: a submitted malformed CSV identity must fail closed.

    Previously all-invalid refs missed the mixed-source guard, skipping all
    NFB holes and returning raw door/base parts. This exercises the real
    saved Bay and installed FinalScene, not a synthetic renderer.
    """
    snapshot = _valid_project()
    before = deepcopy(snapshot)
    submitted = deepcopy(snapshot)
    holes = submitted["nfb_config"]["holes"]
    assert holes
    for hole in holes:
        hole["model_filename"] = invalid_v5
    submitted["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        submitted["nfb_config"]
    )
    with pytest.raises(ValueError, match="NFB_COMMITTED_CSV_MALFORMED_V5_IDENTITY"):
        _scene(submitted)
    assert snapshot == before
    assert not list(tmp_path.glob("*.dxf"))
