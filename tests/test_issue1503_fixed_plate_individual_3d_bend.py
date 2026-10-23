# -*- coding: utf-8 -*-
"""#1503: real independent fixed-plate 3D must be bent, never a flat BEND drawing.

No invented geometry: the 2D/manufacturing source remains at BEND y=23,
while the existing physical T2 signed skin engine folds at mid-skin y=22.
"""
from types import SimpleNamespace

import pytest

from ae_engine.receiving_base_fixing_plate_geometry import (
    build_fixing_plate_source_render_data,
)
from ae_engine.receiving_fixed_plate_formed_skins import (
    verified_receiving_fixing_plate_local_fold,
)
from phase6_final_scene_contracts import FinalSceneViewRequest
from phase6_final_scene_renderer import Phase6FinalSceneRenderer


@pytest.mark.parametrize("part_id", (
    "base_plate:fixing_plate:left",
    "base_plate:fixing_plate:right",
    "base_plate:fixing_plate:nfb_layer:0:left",
    "base_plate:fixing_plate:nfb_layer:1:right",
))
def test_individual_3d_uses_signed_90_degree_bend_and_preserves_mfg_source(part_id):
    from matplotlib.figure import Figure

    # Installed second-tier IDs require the actual committed Set/Bay owner.
    # Do not fabricate tier identities without the same source used in GUI.
    snapshot = None
    if "nfb_layer:" in part_id:
        from tests.test_receiving_two_tier_physical_base_parts import _two_tier
        snapshot = _two_tier()
    source = build_fixing_plate_source_render_data(part_id, snapshot=snapshot)
    guides_before = source.fold_guides
    scene_before = tuple(source.scene.primitives)
    source_metadata = dict(source.metadata)
    hinge_y, x_profile, y_profile, physical_guides = (
        verified_receiving_fixing_plate_local_fold(source)
    )
    assert hinge_y == pytest.approx(22.)
    assert physical_guides[0].position == pytest.approx(22.)
    assert y_profile[0].angle == pytest.approx(90.)
    assert sum(row.length for row in y_profile) == pytest.approx(105.)

    fig = Figure()
    axis = fig.add_subplot(111, projection="3d")
    renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=axis))
    # Reproduce actual earlier defect: the editable Fold Designer has only a
    # flat profile, but fixed-plate 3D MUST take the authentic source fold.
    request = FinalSceneViewRequest(
        render_data=source,
        x_profile=({"len": 256.},),
        y_profile=({"len": 105.},),
        part_key=part_id,
        thickness=2.,
        finished_dimensions=(800., 1600., 350.),
    )
    mesh = renderer.render(request)
    assert mesh
    coordinates = [vertex for triangle in mesh for vertex in triangle]
    z_span = max(point[2] for point in coordinates) - min(point[2] for point in coordinates)
    assert z_span >= 22., "standalone 3D is still an unbent flat"
    assert renderer.last_cutting_material.equals(source.material)
    assert len(axis.lines) >= 1  # physical 3D hinge, not a mesh-grid overlay

    # A 3D-only preview must not rewrite original CUTTING/BEND or certify weld.
    assert source.fold_guides == guides_before
    assert source.fold_guides[0].position == 23.
    assert tuple(source.scene.primitives) == scene_before
    assert source.metadata == source_metadata
    assert source.metadata["manufacturing_ready"] is False


def test_unverified_individual_fixed_plate_cannot_be_formed_by_metadata_guess():
    from dataclasses import replace
    source = build_fixing_plate_source_render_data("base_plate:fixing_plate:left")
    incorrect = replace(source, metadata={**source.metadata, "source_bend_verified": False})
    with pytest.raises(ValueError, match="EAR_LOCAL_FORM_NOT_CURRENT_VERIFIED_BEND23"):
        verified_receiving_fixing_plate_local_fold(incorrect)
