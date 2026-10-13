"""#1640: preview candidate rendering uses an isolated canonical layout clone."""
from types import SimpleNamespace

from ae_engine.receiving_hole_candidates import create_candidate
from ae_engine.receiving_inner_door_candidates import create_inner_candidate
from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
from ae_engine.receiving_shared_settings import setting_value
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from gui_modules.application import receiving_multi_settings_window as view
from gui_modules.application import fold_designer_composition_receiving as composition


def test_real_finalscene_preview_receives_isolated_candidate_set_bay_not_live_mutation(
        monkeypatch):
    captured = {}
    requests = []
    source = new_receiving_layout(width=800, height=1600, depth=350)
    adapter = ReceivingSetBayAdapter(source)
    endcaps, head_version = create_candidate(None, "head", [{"tag": "head-cut"}])
    inner, door_version = create_inner_candidate(None, {
        "layers": 1, "models": ["A.dxf", ""],
    })
    snapshot = {
        "receiving_layout": adapter.layout,
        "receiving_hole_candidates": endcaps,
        "receiving_inner_door_candidates": inner,
    }
    app = SimpleNamespace(
        root=object(), _phase6_input_snapshot=snapshot,
        designer_workspace=None,
    )
    receipt = object()

    def capture_scene(namespace, set_index, bay_index, *, preview_layout=None):
        requests.append((namespace, set_index, bay_index, preview_layout))
        return receipt

    fake = SimpleNamespace(
        app=app,
        receiving_layout_applicable=lambda: True,
        receiving_adapter=lambda namespace: adapter,
        receiving_bay_preview_request=capture_scene,
    )
    monkeypatch.setattr(
        view, "open_multi_settings",
        lambda root, **kwargs: captured.update(kwargs) or object(),
    )
    composition.open_receiving_multi_settings(fake, "receiving")
    real = captured["get_real_cut_preview_request"]

    assert real("head", None, 0, 0) is receipt
    assert requests[-1][3] == adapter.layout  # 即時 reads current canonical Set/Bay geometry.
    assert real("head", head_version, 0, 0) is receipt
    candidate_layout = normalize_receiving_layout(requests[-1][3])
    assert setting_value(candidate_layout["sets"][0], 0, "head_features") == [
        {"tag": "head-cut"},
    ]
    assert setting_value(candidate_layout["sets"][0], 0, "head_version_id") == head_version
    assert setting_value(adapter.layout["sets"][0], 0, "head_features") == []
    assert setting_value(adapter.layout["sets"][0], 0, "head_version_id") is None

    assert real("inner-door", door_version, 0, 0) is receipt
    virtual = normalize_receiving_layout(requests[-1][3])
    assert setting_value(virtual["sets"][0], 0, "inner_door_models") == [
        "A.dxf", "",
    ]
    assert setting_value(virtual["sets"][0], 0, "inner_door_version_id") == door_version
    assert setting_value(adapter.layout["sets"][0], 0, "inner_door_version_id") is None
    assert adapter.layout == source or setting_value(
        adapter.layout["sets"][0], 0, "head_features",
    ) == []
