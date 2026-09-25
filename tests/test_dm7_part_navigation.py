from types import SimpleNamespace

import fold_designer_bridge as bridge


class _Workspace:
    def __init__(self, available_parts):
        self.available_parts = tuple(available_parts)
        self.active_part = "head"
        self.selected_part = "head"
        self.part_profiles = {"head": {"X": [{"length": 1.0}], "Y": []}}


def _app(parts, *, remembered=None):
    return SimpleNamespace(
        designer_workspace=_Workspace(parts),
        _phase6_box_body_active_piece_key=remembered,
        _phase6_corner_data_selected_part_key=None,
    )


def _multipart_parts():
    return (
        "box_body",
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
        "head",
        "tail",
    )


def test_dm7_explicit_aggregate_parent_is_not_replaced_by_child_memory():
    app = _app(_multipart_parts(), remembered="box_body:back")

    resolved = bridge._phase6_resolve_operator_part_key(app, "box_body")

    assert resolved == "box_body"
    assert app._phase6_box_body_active_piece_key == "box_body:back"


def test_dm7_explicit_existing_physical_child_keeps_exact_identity():
    app = _app(_multipart_parts(), remembered="box_body:left_side")

    resolved = bridge._phase6_resolve_operator_part_key(app, "box_body:right_side")

    assert resolved == "box_body:right_side"
    assert app._phase6_box_body_active_piece_key == "box_body:right_side"


def test_dm7_stale_explicit_child_fails_closed_instead_of_using_valid_remembered_sibling():
    app = _app(
        ("box_body", "box_body:back", "box_body:right_side", "head"),
        remembered="box_body:back",
    )

    resolved = bridge._phase6_resolve_operator_part_key(app, "box_body:left_side")

    assert resolved is None
    assert app._phase6_box_body_active_piece_key == "box_body:back"


def test_dm7_stale_remembered_child_is_cleared_instead_of_falling_to_first_child():
    app = _app(
        ("box_body", "box_body:back", "box_body:right_side", "head"),
        remembered="box_body:left_side",
    )

    resolved = bridge._phase6_resolve_operator_part_key(app, "box_body:left_side")

    assert resolved is None
    assert app._phase6_box_body_active_piece_key is None


def test_dm7_menu_tree_and_corner_data_project_the_same_stable_identity_hierarchy():
    parts = _multipart_parts()
    app = _app(parts)

    menu_keys = tuple(bridge._phase6_operator_part_selector_keys(parts))
    tree_rows = tuple(bridge._phase6_structure_tree_rows(parts))
    corner_rows = tuple(bridge._phase6_corner_data_navigation_rows(app))

    expected_tree = (
        ("box_body", None),
        ("box_body:left_side", "box_body"),
        ("box_body:back", "box_body"),
        ("box_body:right_side", "box_body"),
        ("head", None),
        ("tail", None),
    )
    expected_corner = tuple(
        (key, 1 if parent == "box_body" else 0) for key, parent in expected_tree
    )

    assert tree_rows == expected_tree
    assert corner_rows == expected_corner
    assert menu_keys == tuple(key for key, parent in expected_tree if parent is None)


def test_dm7_identity_projection_never_depends_on_display_labels(monkeypatch):
    parts = _multipart_parts()
    app = _app(parts, remembered="box_body:back")

    monkeypatch.setattr(
        bridge,
        "_phase6_part_label",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("display label used as identity authority")
        ),
    )

    assert bridge._phase6_resolve_operator_part_key(app, "box_body") == "box_body"
    assert tuple(bridge._phase6_operator_part_selector_keys(parts)) == (
        "box_body",
        "head",
        "tail",
    )
    assert tuple(bridge._phase6_structure_tree_rows(parts))[1] == (
        "box_body:left_side",
        "box_body",
    )
    assert tuple(bridge._phase6_corner_data_navigation_rows(app))[2] == (
        "box_body:back",
        1,
    )


def test_dm7_resolve_and_hierarchy_projection_do_not_mutate_manufacturing_workspace():
    parts = _multipart_parts()
    app = _app(parts, remembered="box_body:left_side")
    workspace = app.designer_workspace
    before = (
        workspace.available_parts,
        workspace.active_part,
        workspace.selected_part,
        repr(workspace.part_profiles),
    )

    assert bridge._phase6_resolve_operator_part_key(app, "box_body:right_side") == "box_body:right_side"
    bridge._phase6_operator_part_selector_keys(parts)
    bridge._phase6_structure_tree_rows(parts)
    bridge._phase6_corner_data_navigation_rows(app)

    after = (
        workspace.available_parts,
        workspace.active_part,
        workspace.selected_part,
        repr(workspace.part_profiles),
    )
    assert after == before
