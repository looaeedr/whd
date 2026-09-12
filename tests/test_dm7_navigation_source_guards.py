import inspect

import fold_designer_bridge as bridge
import phase6_part_navigation as navigation
from phase6_designer_workspace import Phase6DesignerWorkspace


def _source(obj) -> str:
    return inspect.getsource(obj)


def test_navigation_core_never_reconstructs_identity_from_labels_indices_or_first_child():
    source = _source(navigation.resolve_navigation)

    for forbidden in (
        "children[0]",
        "PART_LABELS",
        "_phase6_part_label",
        ".index(",
        "winfo",
        "Treeview",
    ):
        assert forbidden not in source


def test_bridge_resolver_is_thin_and_has_no_caller_local_boxbody_fallback_rules():
    source = _source(bridge._phase6_resolve_operator_part_key)

    assert "_dm7_resolve_navigation" in source
    assert "NavigationIntent.EXPLICIT_SELECT" in source
    assert "children[0]" not in source
    assert "_phase6_part_label" not in source
    assert "PART_LABELS" not in source
    assert "box_body:" not in source


def test_menu_structure_tree_and_corner_data_consume_shared_projection_owners():
    selector_source = _source(bridge._phase6_operator_part_selector_keys)
    tree_source = _source(bridge._phase6_structure_tree_rows)
    corner_source = _source(bridge._phase6_corner_data_navigation_rows)

    assert "_dm7_operator_part_selector_keys" in selector_source
    assert "_dm7_project_hierarchy" in tree_source
    assert "_dm7_project_hierarchy" in corner_source

    for source in (selector_source, tree_source, corner_source):
        assert "startswith(\"box_body:\")" not in source
        assert "children[0]" not in source
        assert "PART_LABELS" not in source
        assert "_phase6_part_label" not in source


def test_operator_callers_do_not_reconstruct_stable_identity_from_display_text_or_positional_index():
    menu_source = _source(bridge._fix11_refresh_part_buttons)
    tree_select_source = _source(bridge._phase6_on_structure_tree_select)
    child_tab_source = _source(bridge._phase6_on_box_body_piece_tab_changed)

    # Menu commands capture the already-authoritative stable key; labels remain display-only.
    assert "command=lambda k=key: _phase6_activate_operator_part(self, k)" in menu_source
    assert "command=lambda k=label" not in menu_source

    # Tree selection uses the stable key encoded in the tree item's iid, never visible tree text.
    assert "_phase6_activate_operator_part" in tree_select_source
    assert ".item(" not in tree_select_source

    # Hidden legacy tabs may map their opaque widget id back to the stable key that created the tab,
    # but must never use a positional index or first-child fallback as engineering identity.
    assert "_phase6_box_body_piece_tab_map" in child_tab_source
    assert "notebook.index(" not in child_tab_source
    assert ".tabs()[" not in child_tab_source
    assert "children[0]" not in child_tab_source
    assert "_phase6_part_label" not in child_tab_source


def test_corner_data_selection_remains_view_only_and_never_activates_manufacturing_workspace():
    source = _source(bridge._phase6_select_corner_data_part)

    assert "_phase6_resolve_operator_part_key" in source
    assert "self.activate_part(" not in source
    assert "workspace.active_part" not in source
    assert "workspace.selected_part" not in source
    assert ".active_part =" not in source
    assert ".selected_part =" not in source


def test_workspace_snapshot_does_not_gain_navigation_memory_authority():
    source = _source(Phase6DesignerWorkspace.snapshot)

    for forbidden in (
        "_phase6_box_body_active_piece_key",
        "remembered_box_body_child",
        "navigation_memory",
        "corner_data_selected_part_key",
    ):
        assert forbidden not in source
