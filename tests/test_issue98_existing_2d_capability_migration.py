from types import SimpleNamespace

import fold_designer_bridge as bridge


class _Canvas:
    def __init__(self):
        self.deleted = []

    def delete(self, tag):
        self.deleted.append(tag)


class _Workspace:
    def __init__(self, parts):
        self.available_parts = tuple(parts)
        self.active_part = "tail"
        self.selected_part = "tail"


def _app(*, selected="head", callback=None):
    return SimpleNamespace(
        designer_workspace=_Workspace(("box_body", "head", "tail")),
        _phase6_corner_data_selected_part_key=selected,
        _phase6_box_body_active_piece_key=None,
        _phase6_3d_display_mode="corner_data",
        corner_data_canvas=_Canvas(),
        _corner_data_view_render_callback=callback,
    )


def test_corner_data_unfold_view_refresh_forwards_t4_projection_to_view_callback(monkeypatch):
    render_data = object()
    projection = bridge.Phase6CornerDataUnfoldProjection(
        part_key="head",
        render_data=render_data,
    )
    calls = []
    app = _app(callback=lambda canvas, key, data: calls.append((canvas, key, data)))

    monkeypatch.setattr(
        bridge,
        "_phase6_corner_data_unfold_projection",
        lambda owner: projection,
    )

    refresh = getattr(bridge, "_phase6_refresh_corner_data_unfold_view", None)
    assert callable(refresh), "T5 requires a Fold Designer unfold-view refresh seam"

    result = refresh(app)

    assert result is projection
    assert calls == [(app.corner_data_canvas, "head", render_data)]
    assert app.designer_workspace.active_part == "tail"
    assert app.designer_workspace.selected_part == "tail"


def test_corner_data_selection_refreshes_new_view_without_activating_manufacturing(monkeypatch):
    calls = []
    app = _app(selected=None, callback=lambda *_args: None)
    before = (app.designer_workspace.active_part, app.designer_workspace.selected_part)

    monkeypatch.setattr(
        bridge,
        "_phase6_refresh_corner_data_unfold_view",
        lambda owner: calls.append(owner) or "refreshed",
        raising=False,
    )

    resolved = bridge._phase6_select_corner_data_part(app, "head")

    assert resolved == "head"
    assert calls == [app]
    assert (app.designer_workspace.active_part, app.designer_workspace.selected_part) == before


def test_missing_projection_clears_new_canvas_without_calling_legacy_view(monkeypatch):
    calls = []
    app = _app(selected=None, callback=lambda *_args: calls.append(True))

    monkeypatch.setattr(
        bridge,
        "_phase6_corner_data_unfold_projection",
        lambda owner: None,
    )

    refresh = getattr(bridge, "_phase6_refresh_corner_data_unfold_view", None)
    assert callable(refresh), "T5 requires a Fold Designer unfold-view refresh seam"

    assert refresh(app) is None
    assert app.corner_data_canvas.deleted == ["all"]
    assert calls == []
