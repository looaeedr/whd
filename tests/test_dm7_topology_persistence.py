from __future__ import annotations

import inspect

import fold_designer_bridge as bridge
import phase6_part_navigation as nav
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_part_navigation import (
    NavigationIntent,
    NavigationMemory,
    NavigationRequest,
    project_hierarchy,
    resolve_navigation,
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


def test_topology_contraction_invalidates_removed_active_child_and_memory_without_guessing():
    workspace = Phase6DesignerWorkspace.from_snapshot(
        {
            "existing_parts": list(_multipart_parts()),
            "active_part": "box_body:left_side",
        }
    )
    memory = NavigationMemory("box_body:left_side")

    assert workspace.remove_part("box_body:left_side") is True
    assert workspace.active_part is None

    projection = resolve_navigation(
        workspace.available_parts,
        NavigationRequest("box_body:left_side", NavigationIntent.EXPLICIT_SELECT),
        memory,
    )
    assert projection.resolved_key is None
    assert projection.reason == "STALE_PHYSICAL_CHILD"
    assert projection.memory.remembered_box_body_child is None
    assert "box_body:back" in workspace.available_parts
    assert projection.resolved_key != "box_body:back"


def test_stale_explicit_child_never_substitutes_a_still_valid_remembered_sibling():
    parts = ("box_body", "box_body:back", "box_body:right_side", "head")
    projection = resolve_navigation(
        parts,
        NavigationRequest("box_body:left_side", NavigationIntent.EXPLICIT_SELECT),
        NavigationMemory("box_body:back"),
    )

    assert projection.resolved_key is None
    assert projection.reason == "STALE_PHYSICAL_CHILD"
    assert projection.memory.remembered_box_body_child == "box_body:back"


def test_restore_child_context_clears_memory_when_topology_removed_that_child():
    projection = resolve_navigation(
        ("box_body", "box_body:right_side", "head"),
        NavigationRequest(None, NavigationIntent.RESTORE_CHILD_CONTEXT),
        NavigationMemory("box_body:back"),
    )

    assert projection.resolved_key is None
    assert projection.reason == "NO_REMEMBERED_CHILD"
    assert projection.memory.remembered_box_body_child is None


def test_explicit_aggregate_parent_survives_child_contraction_and_memory():
    projection = resolve_navigation(
        ("box_body", "box_body:back", "head"),
        NavigationRequest("box_body", NavigationIntent.EXPLICIT_SELECT),
        NavigationMemory("box_body:right_side"),
    )

    assert projection.resolved_key == "box_body"
    assert projection.selection_kind == "AGGREGATE_PARENT"
    # stale view memory is revalidated independently of explicit parent intent.
    assert projection.memory.remembered_box_body_child is None


def test_hierarchy_projection_never_invents_missing_aggregate_parent():
    parts = ("box_body:left_side", "box_body:back", "head")
    rows = project_hierarchy(parts)

    assert [row.part_key for row in rows] == list(parts)
    assert all(row.depth == 0 and row.parent_key is None for row in rows)
    assert "box_body" not in {row.part_key for row in rows}

    parent = resolve_navigation(
        parts,
        NavigationRequest("box_body", NavigationIntent.EXPLICIT_SELECT),
        NavigationMemory("box_body:left_side"),
    )
    assert parent.resolved_key is None
    assert parent.reason == "PART_NOT_PRESENT"


def test_save_reload_rebuilds_navigation_from_authoritative_project_state_not_view_memory():
    workspace = Phase6DesignerWorkspace.from_snapshot(
        {
            "existing_parts": list(_multipart_parts()),
            "active_part": "box_body:back",
        }
    )
    saved = workspace.snapshot()

    # Navigation memory is ephemeral UI state and must not become project truth.
    assert "navigation_memory" not in saved
    assert "remembered_box_body_child" not in saved
    assert "_phase6_box_body_active_piece_key" not in saved

    reloaded = Phase6DesignerWorkspace.from_snapshot(saved)
    assert reloaded.available_parts == workspace.available_parts
    assert reloaded.active_part == "box_body:back"

    rows = project_hierarchy(reloaded.available_parts)
    assert any(
        row.part_key == "box_body:back" and row.parent_key == "box_body" and row.depth == 1
        for row in rows
    )
    restored = resolve_navigation(
        reloaded.available_parts,
        NavigationRequest(None, NavigationIntent.RESTORE_CHILD_CONTEXT),
        NavigationMemory(),
    )
    assert restored.resolved_key is None
    assert restored.reason == "NO_REMEMBERED_CHILD"


def test_family_switch_commits_derived_topology_before_visible_navigation_refresh():
    source = inspect.getsource(bridge._phase6_on_baseline_model_changed)
    sync_at = source.index("_phase6_sync_authoritative_derived_parts")
    refresh_at = source.index("refresh_parts")
    assert sync_at < refresh_at


def test_source_guard_navigation_core_has_no_forbidden_identity_reconstruction():
    source = inspect.getsource(nav)
    for forbidden in (
        "children[0]",
        "PART_LABELS",
        "KNOWN_PARTS",
        "menu text",
        "tree text",
    ):
        assert forbidden not in source

    hierarchy = inspect.getsource(bridge._phase6_structure_tree_rows)
    assert "_dm7_project_hierarchy" in hierarchy
    assert "startswith" not in hierarchy

    corner = inspect.getsource(bridge._phase6_select_corner_data_part)
    assert "_phase6_resolve_operator_part_key" in corner
    assert ".activate_part(" not in corner

    tab = inspect.getsource(bridge._phase6_on_box_body_piece_tab_changed)
    assert "_phase6_activate_operator_part" in tab
    assert "self.activate_part(" not in tab
