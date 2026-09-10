from types import SimpleNamespace

import fold_designer_bridge as bridge


class _Workspace:
    def __init__(self, available_parts):
        self.available_parts = tuple(available_parts)
        self.active_part = "head"
        self.selected_part = "head"


def _app(parts, selected=None, remembered_box_child=None):
    return SimpleNamespace(
        designer_workspace=_Workspace(parts),
        corner_data_panel=None,
        _phase6_corner_data_selected_part_key=selected,
        _phase6_box_body_active_piece_key=remembered_box_child,
    )


def _refresh(app):
    return bridge._phase6_refresh_corner_data_parts_panel(app)


def test_refresh_preserves_valid_stable_selection_when_authoritative_order_changes():
    app = _app(("box_body", "head", "tail"), selected="head")
    _refresh(app)

    app.designer_workspace.available_parts = (
        "door_c1_r1",
        "box_body",
        "tail",
        "head",
    )
    _refresh(app)

    assert app._phase6_corner_data_selected_part_key == "head"


def test_refresh_clears_stale_dynamic_selection_instead_of_using_row_index():
    app = _app(
        ("box_body", "door_c1_r1", "door_c1_r2", "tail"),
        selected="door_c1_r2",
    )
    _refresh(app)

    # Door topology contracts 2 -> 1.  The vanished stable key must not slide
    # onto whatever happens to occupy its former row index.
    app.designer_workspace.available_parts = (
        "box_body",
        "door_c1_r1",
        "tail",
    )
    _refresh(app)

    assert app._phase6_corner_data_selected_part_key is None


def test_multipart_box_body_uses_valid_remembered_physical_child_not_parent():
    app = _app(
        (
            "box_body",
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
            "head",
        ),
        selected="box_body",
        remembered_box_child="box_body:back",
    )

    _refresh(app)

    assert app._phase6_corner_data_selected_part_key == "box_body:back"
    assert app._phase6_corner_data_selected_part_key != "box_body"


def test_multipart_stale_child_resolves_to_first_authoritative_physical_child():
    app = _app(
        (
            "box_body",
            "box_body:right_side",
            "box_body:back",
            "head",
        ),
        selected="box_body:left_side",
        remembered_box_child="box_body:left_side",
    )

    _refresh(app)

    assert app._phase6_corner_data_selected_part_key == "box_body:right_side"
    assert app._phase6_box_body_active_piece_key == "box_body:right_side"


def test_adding_dynamic_part_does_not_offset_existing_selection():
    app = _app(("box_body", "head", "tail"), selected="tail")
    _refresh(app)

    app.designer_workspace.available_parts = (
        "box_body",
        "indicator:lamp_01",
        "head",
        "tail",
    )
    _refresh(app)

    assert app._phase6_corner_data_selected_part_key == "tail"


def test_corner_data_selection_callback_resolves_identity_without_activating_workspace():
    app = _app(
        (
            "box_body",
            "box_body:left_side",
            "box_body:back",
            "head",
        ),
        remembered_box_child="box_body:back",
    )
    before = (
        app.designer_workspace.active_part,
        app.designer_workspace.selected_part,
    )
    activation_calls = []
    app.activate_part = lambda key: activation_calls.append(key)

    select = getattr(bridge, "_phase6_select_corner_data_part", None)
    assert callable(select), "T3 requires a pure stable-identity corner-data selection callback"

    resolved = select(app, "box_body")

    assert resolved == "box_body:back"
    assert app._phase6_corner_data_selected_part_key == "box_body:back"
    assert activation_calls == []
    assert (
        app.designer_workspace.active_part,
        app.designer_workspace.selected_part,
    ) == before
