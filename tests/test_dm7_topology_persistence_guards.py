from types import SimpleNamespace

import fold_designer_bridge as bridge
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


def test_topology_contraction_stale_explicit_child_fails_closed_without_sibling_substitution():
    reduced = ("box_body", "box_body:back", "box_body:right_side", "head")

    projection = resolve_navigation(
        reduced,
        NavigationRequest("box_body:left_side", NavigationIntent.EXPLICIT_SELECT),
        NavigationMemory("box_body:back"),
    )

    assert projection.resolved_key is None
    assert projection.reason == "STALE_PHYSICAL_CHILD"
    assert projection.memory.remembered_box_body_child == "box_body:back"


def test_topology_contraction_clears_removed_remembered_child_without_guessing_first_child():
    reduced = ("box_body", "box_body:back", "box_body:right_side", "head")

    projection = resolve_navigation(
        reduced,
        NavigationRequest(None, NavigationIntent.RESTORE_CHILD_CONTEXT),
        NavigationMemory("box_body:left_side"),
    )

    assert projection.resolved_key is None
    assert projection.reason == "NO_REMEMBERED_CHILD"
    assert projection.memory.remembered_box_body_child is None


def test_parent_remains_aggregate_when_children_change():
    reduced = ("box_body", "box_body:back", "head")

    projection = resolve_navigation(
        reduced,
        NavigationRequest("box_body", NavigationIntent.EXPLICIT_SELECT),
        NavigationMemory("box_body:back"),
    )

    assert projection.resolved_key == "box_body"
    assert projection.selection_kind == "AGGREGATE_PARENT"
    assert projection.memory.remembered_box_body_child == "box_body:back"


def test_hierarchy_never_invents_aggregate_parent_when_authoritative_parts_only_have_children():
    parts = ("box_body:left_side", "box_body:back", "head")

    rows = project_hierarchy(parts)

    assert tuple(row.part_key for row in rows) == parts
    assert all(row.parent_key is None and row.depth == 0 for row in rows)
    assert "box_body" not in tuple(row.part_key for row in rows)


def test_bridge_projection_reads_post_commit_authoritative_topology_not_cached_child_list():
    workspace = SimpleNamespace(
        available_parts=_multipart_parts(),
        active_part="head",
        selected_part="head",
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_box_body_active_piece_key="box_body:left_side",
    )

    # Simulate the authoritative topology commit that happens before UI projection.
    workspace.available_parts = ("box_body", "box_body:back", "head", "tail")

    resolved = bridge._phase6_resolve_operator_part_key(app, "box_body:left_side")

    assert resolved is None
    assert app._phase6_box_body_active_piece_key is None
    assert (workspace.active_part, workspace.selected_part) == ("head", "head")


def test_save_reload_rebuilds_authoritative_parts_without_persisting_navigation_memory():
    parts = _multipart_parts()
    workspace = Phase6DesignerWorkspace.from_snapshot(
        {
            "existing_parts": list(parts),
            "active_part": "box_body",
        }
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_box_body_active_piece_key="box_body:back",
    )

    payload = workspace.snapshot()

    # Navigation memory is a View-only attribute on the adapter, not project truth.
    forbidden = {
        "_phase6_box_body_active_piece_key",
        "phase6_box_body_active_piece_key",
        "remembered_box_body_child",
        "navigation_memory",
    }
    assert forbidden.isdisjoint(payload)

    rebuilt = Phase6DesignerWorkspace.from_snapshot(payload)
    assert tuple(rebuilt.available_parts) == tuple(workspace.available_parts)

    fresh_view_projection = resolve_navigation(
        rebuilt.available_parts,
        NavigationRequest(None, NavigationIntent.RESTORE_CHILD_CONTEXT),
        NavigationMemory(),
    )
    assert fresh_view_projection.resolved_key is None
    assert fresh_view_projection.reason == "NO_REMEMBERED_CHILD"

    # The pre-save adapter memory remains local to that adapter only.
    assert app._phase6_box_body_active_piece_key == "box_body:back"
