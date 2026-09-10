from types import SimpleNamespace
import inspect

import fold_designer_bridge as bridge
import gui


class _Canvas:
    def __init__(self):
        self.deleted = []
        self.bound = {}
        self.text = []

    def delete(self, tag):
        self.deleted.append(tag)

    def winfo_width(self):
        return 960

    def winfo_height(self):
        return 720

    def bind(self, sequence, callback):
        self.bound[sequence] = callback

    def unbind(self, sequence):
        self.bound.pop(sequence, None)

    def create_text(self, *args, **kwargs):
        self.text.append((args, kwargs))
        return len(self.text)


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


def _legacy_owner():
    calls = []
    owner = SimpleNamespace()
    owner.COLOR_CANVAS_BG = "white"
    owner.COLOR_TEXT = "black"
    owner.COLOR_TEXT_MUTED = "gray"
    owner.draw_grid = lambda canvas, w, h: calls.append(("grid", canvas, w, h))
    owner._draw_phase6_finished_dimension_summary = (
        lambda canvas, *, part_key, y=132: calls.append(("finished", canvas, part_key))
    )
    owner.open_part_hole_editor = lambda key: calls.append(("hole", key))
    owner.on_door_canvas_press = lambda event: calls.append(("door_press", event))
    owner.on_door_canvas_drag = lambda event: calls.append(("door_drag", event))
    owner.on_door_canvas_release = lambda event: calls.append(("door_release", event))
    owner._authoritative_render_data = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("new Fold Designer View must consume supplied T4 render_data")
    )
    owner._phase6_resolved_finished_dimensions = lambda *_args, **_kwargs: None
    return owner, calls


def _render_data():
    material = SimpleNamespace(bounds=(0.0, 0.0, 500.0, 300.0), is_empty=False)
    scene = SimpleNamespace(primitives=(
        SimpleNamespace(layer="CUTTING"),
        SimpleNamespace(layer="BEND"),
        SimpleNamespace(layer="CUTTING"),
    ))
    return SimpleNamespace(material=material, scene=scene, warnings=())


def test_full_2d_view_consumes_supplied_authoritative_render_data_and_shared_helpers(monkeypatch):
    canvas = _Canvas()
    owner, calls = _legacy_owner()
    render_data = _render_data()
    transform = object()
    drawing_calls = []
    annotation_calls = []

    monkeypatch.setattr(
        gui,
        "_phase6_2d_material_viewport",
        lambda bounds, cw, ch: (transform, 0.0, 0.0, 1.0, 0.0),
    )
    monkeypatch.setattr(
        gui,
        "render_drawing_scene",
        lambda target, scene, tx, *, skip_layers=(): drawing_calls.append(
            (target, scene, tx, tuple(skip_layers))
        ),
    )
    monkeypatch.setattr(
        gui,
        "_draw_phase6_annotation_projection",
        lambda target, data, tx, *, part_key="", strict=False: annotation_calls.append(
            (target, data, tx, part_key, strict)
        ),
    )
    monkeypatch.setattr(gui, "draw_hole_editor_hint", lambda target, cw, endcap=False: calls.append(("hint", target, cw, endcap)))

    render = getattr(gui.BoxCalculatorGUI, "_render_fold_designer_corner_data_view", None)
    assert callable(render), "T5 must install the existing 2D capability renderer for the new View"

    result = render(owner, canvas, "head", render_data)

    assert result is render_data
    assert canvas.deleted == ["all"]
    assert drawing_calls == [(canvas, render_data.scene, transform, ("CHECK", "STOCK"))]
    assert annotation_calls == [(canvas, render_data, transform, "head", False)]
    assert ("finished", canvas, "head") in calls
    assert ("hint", canvas, 960, True) in calls


def test_full_2d_view_binds_existing_hole_editor_to_exact_stable_identity(monkeypatch):
    canvas = _Canvas()
    owner, calls = _legacy_owner()
    render_data = _render_data()

    monkeypatch.setattr(gui, "_phase6_2d_material_viewport", lambda *_args: (object(), 0.0, 0.0, 1.0, 0.0))
    monkeypatch.setattr(gui, "render_drawing_scene", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gui, "_draw_phase6_annotation_projection", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gui, "draw_hole_editor_hint", lambda *_args, **_kwargs: None)

    render = getattr(gui.BoxCalculatorGUI, "_render_fold_designer_corner_data_view", None)
    assert callable(render)
    render(owner, canvas, "base_plate_c1_r2", render_data)

    assert "<Double-Button-1>" in canvas.bound
    canvas.bound["<Double-Button-1>"](SimpleNamespace())
    assert ("hole", "base_plate_c1_r2") in calls


def test_full_2d_view_preserves_existing_door_drag_callbacks(monkeypatch):
    canvas = _Canvas()
    owner, calls = _legacy_owner()
    render_data = _render_data()

    monkeypatch.setattr(gui, "_phase6_2d_material_viewport", lambda *_args: (object(), 0.0, 0.0, 1.0, 0.0))
    monkeypatch.setattr(gui, "render_drawing_scene", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gui, "_draw_phase6_annotation_projection", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gui, "draw_hole_editor_hint", lambda *_args, **_kwargs: None)

    render = getattr(gui.BoxCalculatorGUI, "_render_fold_designer_corner_data_view", None)
    assert callable(render)
    render(owner, canvas, "door_c1_r1", render_data)

    for sequence in ("<Button-1>", "<B1-Motion>", "<ButtonRelease-1>"):
        assert sequence in canvas.bound
    event = SimpleNamespace(x=10, y=20)
    canvas.bound["<Button-1>"](event)
    canvas.bound["<B1-Motion>"](event)
    canvas.bound["<ButtonRelease-1>"](event)
    assert ("door_press", event) in calls
    assert ("door_drag", event) in calls
    assert ("door_release", event) in calls


def test_full_2d_renderer_source_has_no_second_manufacturing_calculation_path():
    render = getattr(gui.BoxCalculatorGUI, "_render_fold_designer_corner_data_view", None)
    assert callable(render)
    src = inspect.getsource(render).lower()
    for forbidden in (
        "_authoritative_render_data(",
        "build_part_render_data(",
        "build_box_body_structure_render_data(",
        "resolve_manufacturing",
        "measure_unfolded_blanks(",
        "save_part_render_data_dxf(",
    ):
        assert forbidden not in src, forbidden


def test_fold_designer_owns_a_real_corner_data_canvas_in_same_renderer_viewport():
    prepare = getattr(bridge, "_phase6_prepare_corner_data_canvas", None)
    hide = getattr(bridge, "_phase6_hide_corner_data_canvas", None)
    assert callable(prepare), "T5 needs a real Fold Designer corner-data canvas"
    assert callable(hide), "T5 needs a reversible 2D/3D viewport switch"
    show_src = inspect.getsource(bridge._phase6_show_corner_data)
    assert "_phase6_prepare_corner_data_canvas(self)" in show_src
    assert "_phase6_refresh_corner_data_unfold_view(self)" in show_src


def test_main_gui_installs_new_view_callback_without_returning_to_legacy_notebook():
    cls_src = inspect.getsource(gui.BoxCalculatorGUI)
    assert "designer._corner_data_view_render_callback = self._render_fold_designer_corner_data_view" in cls_src
    renderer_src = inspect.getsource(gui.BoxCalculatorGUI._render_fold_designer_corner_data_view).lower()
    for forbidden in ("self.notebook", "tab_z", "tab_head", "tab_tail", "tab_door", "tab_base_plate"):
        assert forbidden not in renderer_src, forbidden
