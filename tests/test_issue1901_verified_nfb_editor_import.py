"""Issue #1901: only source-proven physical NFB contours enter the original editor."""
from types import SimpleNamespace

import pytest

from ae_engine.receiving_nfb_editor_features import (
    verified_nfb_openings_to_editor_features, assert_editor_nfb_proof_scope,
)
from ae_engine.receiving_nfb_ui1b_bridge import NfbVerifiedDraftSubmission
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.sheetmetal_feature_core import FeatureAnchor, ProfileFeature
from ae_engine.sheetmetal_geometry import Vec2


PART_ID = "inner_door:sample:panel"


def _verified_bundle(*, source_drift=False, manufactured=True, baseline_features=()):
    panel = SimpleNamespace(
        stable_id=PART_ID, fold_left=19.0, fold_bottom=19.0, thickness=2.0,
    )
    original = DrawingScene()
    original.add_polyline([(0, 0), (400, 0), (400, 800), (0, 800)],
                          layer="CUTTING", closed=True)
    manufactured_scene = DrawingScene(list(original.primitives))
    manufactured_scene.add_polyline(
        [(100, 200), (125, 200), (125, 311), (100, 311)],
        layer="CUTTING", closed=True,
    )
    if source_drift:
        manufactured_scene.primitives.pop(0)
    verified = SimpleNamespace(
        part_id=PART_ID,
        manufacturing_ready=manufactured,
        physical_hole_ids=("nfb:source-1",),
        source_sha256="0123456789abcdef",
        render_data=SimpleNamespace(scene=manufactured_scene),
    )
    bundle = NfbVerifiedDraftSubmission(
        set_index=0, bay_index=0, version_id="inner-door-v1", config={},
        scope=SimpleNamespace(inner_door_part_id=PART_ID),
        source_inventory=None, verified_door=verified,
        readiness=SimpleNamespace(can_submit=True),
        source_path="/fake/original.dxf",
        snapshot_at_verification={"part_features": {PART_ID: list(baseline_features)}},
        bay_at_verification={},
    )
    return panel, original, bundle


def test_source_verified_finalscene_becomes_native_finished_face_profile(monkeypatch):
    import ae_engine.receiving_nfb_editor_features as adapter
    from ae_engine.cabinet_types import policy
    panel, canonical, verified = _verified_bundle()
    monkeypatch.setattr(policy, "derive_inner_door_panels", lambda _snapshot: [panel])
    monkeypatch.setattr(adapter, "build_inner_door_panel_render_data",
                        lambda _panel: SimpleNamespace(scene=canonical))
    monkeypatch.setattr(adapter, "existing_inner_door_feature_finalscene",
                        lambda *_args: None)
    features = verified_nfb_openings_to_editor_features(
        verified, current_features=[],
    )
    assert len(features) == 1
    feature = features[0]
    assert isinstance(feature, ProfileFeature)
    assert feature.source_type == "NFB_VERIFIED_SOURCE"
    assert feature.anchor is FeatureAnchor.ABSOLUTE_FINISHED_FACE
    assert feature.points == (
        Vec2(83.0, 183.0), Vec2(108.0, 183.0),
        Vec2(108.0, 294.0), Vec2(83.0, 294.0),
    )
    assert dict(feature.source_params)["source_sha256"] == "0123456789abcdef"


def test_quantity_source_proof_imports_same_native_profile_without_version(monkeypatch):
    import ae_engine.receiving_nfb_editor_features as adapter
    from ae_engine.receiving_nfb_quantity_editor import NfbVerifiedQuantityDoorProof
    from ae_engine.cabinet_types import policy

    panel, canonical, old_bundle = _verified_bundle()
    actual_single_proof = NfbVerifiedQuantityDoorProof(
        snapshot_at_verification=old_bundle.snapshot_at_verification,
        part_id=PART_ID,
        verified_door=old_bundle.verified_door,
        source_path="/original/NFB.dxf",
        source_sha256="0123456789abcdef",
        world_x_by_unit=(("unit-1", 165.0),),
        draft_at_verification={},
    )
    monkeypatch.setattr(policy, "derive_inner_door_panels", lambda _snap: [panel])
    monkeypatch.setattr(adapter, "build_inner_door_panel_render_data",
                        lambda _panel: SimpleNamespace(scene=canonical))
    monkeypatch.setattr(adapter, "existing_inner_door_feature_finalscene",
                        lambda *_args: None)
    features = verified_nfb_openings_to_editor_features(
        actual_single_proof, current_features=[],
    )
    assert len(features) == 1
    assert features[0].source_type == "NFB_VERIFIED_SOURCE"
    assert dict(features[0].source_params)["part_id"] == PART_ID


@pytest.mark.parametrize("case", ["unverified", "source_drift", "editor_drift"])
def test_unverified_or_stale_nfb_never_enters_native_editor(monkeypatch, case):
    import ae_engine.receiving_nfb_editor_features as adapter
    from ae_engine.cabinet_types import policy
    panel, canonical, bundle = _verified_bundle(
        source_drift=(case == "source_drift"),
        manufactured=(case != "unverified"),
    )
    monkeypatch.setattr(policy, "derive_inner_door_panels", lambda _snapshot: [panel])
    monkeypatch.setattr(adapter, "build_inner_door_panel_render_data",
                        lambda _panel: SimpleNamespace(scene=canonical))
    monkeypatch.setattr(adapter, "existing_inner_door_feature_finalscene",
                        lambda *_args: None)
    with pytest.raises(ValueError):
        verified_nfb_openings_to_editor_features(
            bundle, current_features=(["unsaved-change"]
                                      if case == "editor_drift" else []),
        )


@pytest.mark.parametrize("settings_mode,active_mode,blocked", [
    ("single", "quantity", True),
    ("single", "set_bay", False),
    ("candidate", "set_bay", False),
    (None, "quantity", False),
])
def test_single_quantity_must_not_reuse_multi_bay_verified_nfb_scope(
    settings_mode, active_mode, blocked,
):
    if blocked:
        with pytest.raises(ValueError, match="不可沿用多連 Bay"):
            assert_editor_nfb_proof_scope(
                settings_mode=settings_mode, active_mode=active_mode,
            )
    else:
        assert_editor_nfb_proof_scope(
            settings_mode=settings_mode, active_mode=active_mode,
        ) is None
