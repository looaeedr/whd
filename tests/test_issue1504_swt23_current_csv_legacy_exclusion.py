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
    """#1504 AC52: fail closed at both CSV ownership and actual FinalScene.

    A lower-level all-invalid V5 list previously reached the legacy fallback,
    but the full FinalScene's earlier depth/brand owner guard also rejects it.
    Exercise both gates independently; never call that rejection a DXF export.
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
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes

    # The exact lower-level source-owner gate must independently reject
    # malformed V5, even if an upstream geometry/depth gate is bypassed.
    with pytest.raises(ValueError, match="NFB_COMMITTED_CSV_MALFORMED_V5_IDENTITY"):
        _submitted_csv_holes(submitted)
    # The actual full FinalScene may correctly reject earlier (depth/brand).
    # Whichever gate runs first, it must not produce editable/manufactured
    # parts with missing source-owned NFB holes.
    with pytest.raises(
        ValueError,
        match="RECEIVING_NFB_DEPTH_V5_BRAND_IDENTITY_MISMATCH|"
              "NFB_COMMITTED_CSV_MALFORMED_V5_IDENTITY",
    ):
        _scene(submitted)
    assert snapshot == before
    assert not list(tmp_path.glob("*.dxf"))


@pytest.mark.parametrize("invalid_legacy", [
    None,
    "",
    "NOT_A_DXF",
    "legacy/escape.dxf",
    ["unexpected", "list"],
])
def test_ac52_all_unparseable_legacy_names_cannot_approve_empty_numeric_source(
    invalid_legacy,
):
    """Submitted damaged legacy names are not a valid all-legacy fallback."""
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes

    submitted = _valid_project()
    for hole in submitted["nfb_config"]["holes"]:
        hole["model_filename"] = deepcopy(invalid_legacy)
    submitted["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        submitted["nfb_config"]
    )
    with pytest.raises(ValueError, match="NFB_COMMITTED_CSV_STORED_MODEL_INVALID"):
        _submitted_csv_holes(submitted)


def test_ac52_legitimate_historical_dxf_names_still_use_unchanged_legacy_path():
    """Reject malformed records, but never migrate a legal historical model."""
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes

    snapshot = _valid_project()
    for hole in snapshot["nfb_config"]["holes"]:
        hole["model_filename"] = "400_140X257_107.dxf"
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snapshot["nfb_config"]
    )
    assert _submitted_csv_holes(snapshot) == ()


@pytest.mark.parametrize("invalid_identity", [
    "nfbv5:士林:",
    None,
    "legacy/escape.dxf",
])
def test_ac52_original_pair_writer_rejects_corrupt_reloaded_model_before_dxf_publish(
    invalid_identity, tmp_path,
):
    """The actual original operator must never publish from a stale scene.

    A valid submitted source first produces real paired manufacturing DXFs.
    Corrupt *only* the saved physical model identity, keep the previous
    resolved FinalScene, and exercise the same original two-sheet writer.
    The already exported source evidence and its bytes must remain untouched.
    """
    valid = _valid_project()
    assembly = _scene(valid)
    valid_before = deepcopy(valid)
    first = _save(valid, assembly, tmp_path / "baseline")
    existing = _files(first)
    original_bytes = tuple(path.read_bytes() for path in existing)
    assert all(original_bytes)

    broken = deepcopy(valid)
    for row in broken["nfb_config"]["holes"]:
        row["model_filename"] = deepcopy(invalid_identity)
    broken["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        broken["nfb_config"]
    )
    broken_before = deepcopy(broken)
    rejected = tmp_path / "rejected"
    rejected.mkdir()
    with pytest.raises(ValueError):
        _export(broken, assembly, rejected)
    assert not list(rejected.iterdir())
    assert tuple(path.read_bytes() for path in existing) == original_bytes
    assert broken == broken_before and valid == valid_before


@pytest.mark.parametrize("corruption", [
    "missing_config", "null_config", "list_config",
    "missing_holes", "empty_holes", "not_a_hole_list",
])
def test_ac52_submitted_but_missing_physical_nfb_config_must_fail_closed(
    corruption, tmp_path,
):
    """A committed Bay may not masquerade as an unconfigured legacy source."""
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes

    valid = _valid_project()
    old_scene = _scene(valid)
    snapshot = deepcopy(valid)
    if corruption == "missing_config":
        snapshot.pop("nfb_config")
    elif corruption == "null_config":
        snapshot["nfb_config"] = None
    elif corruption == "list_config":
        snapshot["nfb_config"] = []
    else:
        config = deepcopy(snapshot["nfb_config"])
        if corruption == "missing_holes":
            config.pop("holes")
        elif corruption == "empty_holes":
            config["holes"] = []
        else:
            config["holes"] = {"invalid": "not a list"}
        snapshot["nfb_config"] = config
    # Maintain the submitted fact: this is corruption, not a user-requested
    # Restore Unconfigured transaction. The old FinalScene cannot approve it.
    before = deepcopy(snapshot)
    with pytest.raises(ValueError, match="NFB_COMMITTED_CSV_SUBMITTED_CONFIG_INVALID"):
        _submitted_csv_holes(snapshot)
    assert snapshot == before
    out = tmp_path / "rejected"
    out.mkdir()
    with pytest.raises(ValueError):
        _export(snapshot, old_scene, out)
    assert not list(out.iterdir())
    assert snapshot == before


def test_ac52_truly_unconfigured_project_can_still_have_no_nfb_config():
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes

    snapshot = _valid_project()
    snapshot["nfb_config_submitted"] = False
    snapshot.pop("nfb_config")
    snapshot["receiving_layout"] = update_receiving_bay(
        snapshot["receiving_layout"], set_index=0, bay_index=0,
        nfb_config_submitted=False,
    )
    bay = snapshot["receiving_layout"]["sets"][0]["bays"][0]
    assert bay.get("nfb_config_submitted") is not True
    assert "nfb_config" not in bay
    assert _submitted_csv_holes(snapshot) == ()


@pytest.mark.parametrize("malformed_submitted", [1, 0, "true", None, [], {}])
def test_ac52_nonboolean_submission_fact_never_acts_as_legacy_exemption(
    malformed_submitted, tmp_path,
):
    """A damaged submitted fact is not an operator Restore Unconfigured."""
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes

    submitted = _valid_project()
    original_scene = _scene(submitted)
    broken = deepcopy(submitted)
    broken["nfb_config_submitted"] = deepcopy(malformed_submitted)
    original = deepcopy(broken)
    with pytest.raises(ValueError, match="NFB_COMMITTED_CSV_SUBMISSION_FACT_INVALID"):
        _submitted_csv_holes(broken)
    rejected = tmp_path / "rejected"
    rejected.mkdir()
    with pytest.raises(ValueError):
        _export(broken, original_scene, rejected)
    assert not list(rejected.iterdir())
    assert broken == original


def test_ac52_old_project_without_submission_field_uses_unchanged_legacy_path():
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes

    snapshot = _valid_project()
    snapshot.pop("nfb_config_submitted")
    snapshot.pop("nfb_config", None)
    snapshot["receiving_layout"] = update_receiving_bay(
        snapshot["receiving_layout"], set_index=0, bay_index=0,
        nfb_config_submitted=False,
    )
    assert _submitted_csv_holes(snapshot) == ()


@pytest.mark.parametrize("root_fact", ["false", "missing"])
def test_ac52_selected_committed_bay_cannot_be_hidden_by_root_unsubmitted_alias(
    root_fact, tmp_path,
):
    """The selected persisted Bay owns the commit; root aliases are projections."""
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes

    valid = _valid_project()
    previous_scene = _scene(valid)
    snapshot = deepcopy(valid)
    bay = snapshot["receiving_layout"]["sets"][0]["bays"][0]
    assert bay["nfb_config_submitted"] is True
    if root_fact == "false":
        snapshot["nfb_config_submitted"] = False
    else:
        snapshot.pop("nfb_config_submitted")
    original = deepcopy(snapshot)
    with pytest.raises(ValueError, match="NFB_COMMITTED_CSV_SELECTED_BAY_SUBMISSION_DRIFT"):
        _submitted_csv_holes(snapshot)
    target = tmp_path / "held"
    target.mkdir()
    with pytest.raises(ValueError):
        _export(snapshot, previous_scene, target)
    assert not list(target.iterdir())
    assert snapshot == original
