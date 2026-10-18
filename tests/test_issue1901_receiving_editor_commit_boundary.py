"""#1901: tab drafts and cancelling original editor cannot write live/candidate."""
from types import SimpleNamespace

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application.receiving_inner_door_hole_editor import open_inner_door_hole_editor
from phase6_designer_workspace import Phase6DesignerWorkspace


def test_multi_editor_sync_is_read_only_until_confirm_all():
    snapshot = apply_family_defaults({
        "model": "金庫型", "w": 400, "h": 600, "d": 250,
        "t": 2, "fw": 25,
    })
    panel_key = cabinet_family_policy.derive_inner_door_panels(snapshot)[0].stable_id
    workspace = Phase6DesignerWorkspace.from_snapshot({
        **snapshot, "existing_parts": ["box_body", panel_key],
        "active_part": "box_body",
    })
    captured = []
    writes = []

    class Host:
        def scene_query(self, *_args):
            return None

        def _open_unified_hole_editor(self, *_args, **kwargs):
            captured.append(kwargs)
            self.last_unified_hole_editor = SimpleNamespace()
            return self.last_unified_hole_editor

    host = Host()
    app = SimpleNamespace(
        root=SimpleNamespace(),
        designer_workspace=workspace,
        _phase6_input_snapshot=snapshot,
        _scene_query_callback=host.scene_query,
        _load_part_holes=lambda *_args: writes.append("reload"),
        submit_update_intent=lambda *_args, **_kwargs: writes.append("geometry"),
    )
    candidate = []
    window = open_inner_door_hole_editor(
        app, panel_key, settings_mode="candidate",
        selected_candidate_version="inner-door-v2",
        initial_features=candidate,
        on_settings_confirm=lambda key, features, config:
            writes.append((key, features, config)),
    )
    assert window._receiving_settings_mode == "candidate"
    assert window._receiving_candidate_version == "inner-door-v2"
    assert workspace.features_for(panel_key) == []
    feature = CircleFeature(
        diameter=8, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0),
    )
    # Preview/cancel callback is explicitly a no-op.
    captured[0]["feature_list_override"].append(feature)
    captured[0]["sync_callback"]()
    assert workspace.features_for(panel_key) == []
    assert writes == []

    # Only the outer editor's Confirm-only port receives a typed Feature.
    captured[0]["on_confirm_features"]([feature])
    assert writes == [(panel_key, [feature], None)]
    assert workspace.features_for(panel_key) == []
