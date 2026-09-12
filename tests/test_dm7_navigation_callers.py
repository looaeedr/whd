from types import SimpleNamespace

import fold_designer_bridge as bridge


class _Notebook:
    def __init__(self, selected):
        self._selected = selected

    def select(self):
        return self._selected


class _Workspace:
    def __init__(self, available_parts, *, active_part="head", selected_part="head"):
        self.available_parts = tuple(available_parts)
        self.active_part = active_part
        self.selected_part = selected_part


def test_legacy_box_body_tab_callback_delegates_to_central_operator_navigation(monkeypatch):
    workspace = _Workspace(
        ("box_body", "box_body:left_side", "box_body:back", "head"),
        active_part="box_body:left_side",
        selected_part="box_body:left_side",
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        box_body_piece_selector=_Notebook("tab-back"),
        _phase6_box_body_piece_tab_guard=False,
        _phase6_box_body_piece_tab_map={"tab-back": "box_body:back"},
        _phase6_box_body_active_piece_key="box_body:left_side",
    )
    app.activate_part = lambda key: (_ for _ in ()).throw(
        AssertionError(f"legacy tab bypassed central navigation: {key}")
    )
    calls = []

    def _central(owner, key):
        # The caller must not pre-write child memory before the central resolver
        # validates the requested stable identity.
        calls.append((owner, key, owner._phase6_box_body_active_piece_key))
        return key

    monkeypatch.setattr(bridge, "_phase6_activate_operator_part", _central)

    bridge._phase6_on_box_body_piece_tab_changed(app)

    assert calls == [(app, "box_body:back", "box_body:left_side")]


def test_stale_legacy_box_body_tab_fails_closed_through_dm7_without_activation():
    workspace = _Workspace(
        ("box_body", "box_body:back", "head"),
        active_part="head",
        selected_part="head",
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        box_body_piece_selector=_Notebook("tab-stale"),
        _phase6_box_body_piece_tab_guard=False,
        _phase6_box_body_piece_tab_map={"tab-stale": "box_body:left_side"},
        _phase6_box_body_active_piece_key="box_body:left_side",
    )
    activation_calls = []
    app.activate_part = lambda key: activation_calls.append(key)

    bridge._phase6_on_box_body_piece_tab_changed(app)

    assert activation_calls == []
    assert app._phase6_box_body_active_piece_key is None
    assert workspace.active_part == "head"
    assert workspace.selected_part == "head"


def test_activate_selected_part_delegates_to_central_operator_navigation(monkeypatch):
    app = SimpleNamespace(
        selected_part_key="head",
        available_parts=("box_body", "head", "tail"),
    )
    app.activate_part = lambda key: (_ for _ in ()).throw(
        AssertionError(f"selected-part caller bypassed central navigation: {key}")
    )
    calls = []
    monkeypatch.setattr(
        bridge,
        "_phase6_activate_operator_part",
        lambda owner, key: calls.append((owner, key)) or True,
    )

    assert bridge._fix11_activate_selected_part(app) is True
    assert calls == [(app, "head")]


def test_corner_data_regular_part_selection_uses_same_navigation_resolver_without_activation(monkeypatch):
    workspace = _Workspace(
        ("box_body", "head", "tail"),
        active_part="tail",
        selected_part="tail",
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_corner_data_selected_part_key=None,
        _phase6_box_body_active_piece_key=None,
    )
    app.activate_part = lambda key: (_ for _ in ()).throw(
        AssertionError(f"corner-data selection mutated manufacturing state: {key}")
    )
    calls = []

    def _resolve(owner, key):
        calls.append((owner, key))
        return "head"

    monkeypatch.setattr(bridge, "_phase6_resolve_operator_part_key", _resolve)

    resolved = bridge._phase6_select_corner_data_part(app, "head", refresh_view=False)

    assert resolved == "head"
    assert calls == [(app, "head")]
    assert app._phase6_corner_data_selected_part_key == "head"
    assert (workspace.active_part, workspace.selected_part) == ("tail", "tail")


def test_corner_data_obeys_central_fail_closed_resolution_even_for_regular_part(monkeypatch):
    workspace = _Workspace(
        ("box_body", "head", "tail"),
        active_part="tail",
        selected_part="tail",
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_corner_data_selected_part_key="tail",
        _phase6_box_body_active_piece_key=None,
    )
    calls = []
    monkeypatch.setattr(
        bridge,
        "_phase6_resolve_operator_part_key",
        lambda owner, key: calls.append((owner, key)) or None,
    )

    resolved = bridge._phase6_select_corner_data_part(app, "head", refresh_view=False)

    assert resolved is None
    assert calls == [(app, "head")]
    assert app._phase6_corner_data_selected_part_key is None
    assert (workspace.active_part, workspace.selected_part) == ("tail", "tail")


def test_existing_menu_and_structure_tree_paths_keep_central_operator_activation():
    # These two callers were already migrated by the accepted T2 seam.  T3 must
    # preserve them while migrating the remaining legacy callers above.
    import inspect

    menu_source = inspect.getsource(bridge._fix11_refresh_part_buttons)
    tree_source = inspect.getsource(bridge._phase6_on_structure_tree_select)

    assert "_phase6_activate_operator_part" in menu_source
    assert "_phase6_activate_operator_part" in tree_source
