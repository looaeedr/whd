"""DEPRECATED compatibility shim for legacy part-panel helper imports.

Current implementation lives in ``gui_modules.parts.panels.common``.
Internal callers in ``gui.py`` and ``gui_modules/application/lifecycle.py`` are
scheduled to migrate during #292; remove this shim in #292 before final closure.
"""

from gui_modules.parts.panels.common import logical_part_present as _phase6_logical_part_present

__all__ = ["_phase6_logical_part_present"]
