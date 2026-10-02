"""Visibility/presence routing for #295/T7.

Physical-part identity and active-part state remain owned by
Phase6WorkspaceController. This module only routes visibility/presence UI
requests to that owner and refreshes derived presentation/cache state.
"""
from gui_modules.parts.selector import refresh_presence_ui


def phase6_current_existing_parts(host):
    """Return physical presence from the single Workspace Controller."""
    indicator_var = getattr(host, "is_indicator_box_var", None)
    indicator_enabled = bool(indicator_var.get()) if indicator_var is not None else False
    return host.workspace_controller.current_existing_parts(
        indicator_box_enabled=indicator_enabled
    )


def phase6_set_part_presence(host, key, present):
    """Mutate physical presence through the single Workspace Controller."""
    existing = host.workspace_controller.set_part_presence(str(key), bool(present))
    host._phase6_refresh_presence_ui(existing)
    owner = getattr(host, "_derived_cache_owner", None)
    if owner is not None:
        owner.invalidate("geometry")
    return existing


def phase6_refresh_presence_ui(host, existing_parts=None):
    """Project authoritative presence into the existing UI only."""
    return refresh_presence_ui(host, existing_parts)
