"""#2517/#2379: public Engine feature mapping is the single export authority."""
from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

from ae_engine import manufacturing_api, map_door_features_to_unfolded_material
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch


def _spec():
    return DoorPartSpec(
        width=500.0, height=600.0, thickness=2.0, frame_width=25.0,
        features=(CircleFeature(
            diameter=6.0, anchor=FeatureAnchor.BOTTOM_LEFT,
            offset=Vec2(20.0, 30.0), source_type="trusted-original-circle",
        ),),
        feature_space="finished_face",
    )


def test_public_door_material_map_preserves_source_identity_and_engine_geometry():
    from ae_engine.manufacturing_endcap_compat import _door_features_for_legacy_engine

    spec, ctx = _spec(), ManufacturingContext()
    actual = manufacturing_api.map_door_features_to_unfolded_material(spec, ctx)
    assert map_door_features_to_unfolded_material is manufacturing_api.map_door_features_to_unfolded_material
    assert actual == tuple(_door_features_for_legacy_engine(spec, ctx))
    assert len(actual) == 1
    assert actual[0].source_type == "trusted-original-circle"
    assert actual[0].anchor == FeatureAnchor.ABSOLUTE_FINISHED_FACE


def test_public_door_material_map_fails_closed_on_unknown_coordinate_space():
    wrong = replace(_spec(), feature_space="unknown-space")
    with pytest.raises(ValueError, match="Unsupported Door feature_space"):
        manufacturing_api.map_door_features_to_unfolded_material(wrong)
    assert manufacturing_api.map_door_features_to_unfolded_material(
        replace(_spec(), features=())
    ) == ()


def test_worker_dxf_source_verification_uses_public_engine_mapping_only():
    source = inspect.getsource(save_trusted_door_circle_finalscene_batch)
    assert "map_door_features_to_unfolded_material(owned_spec, context)" in source
    assert "from ae_engine.manufacturing_endcap_compat import _door_features_for_legacy_engine" not in source
