from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one patch anchor, got {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "fold_designer_bridge.py",
    """def _fix11_activate_part(self, key, initial=False):\n    if key not in self.designer_workspace.available_parts:\n        return\n    _phase6_hide_corner_data_canvas(self)\n    if _phase6_is_box_body_physical_piece_key(key):\n""",
    """def _fix11_activate_part(self, key, initial=False):\n    if key not in self.designer_workspace.available_parts:\n        return\n    _phase6_hide_corner_data_canvas(self)\n    corner_data_panel = getattr(self, \"corner_data_panel\", None)\n    if corner_data_panel is not None:\n        try:\n            if corner_data_panel.winfo_manager():\n                corner_data_panel.pack_forget()\n        except Exception:\n            pass\n    if _phase6_is_box_body_physical_piece_key(key):\n""",
)

replace_once(
    "fold_designer_bridge.py",
    """    _phase6_sync_authoritative_derived_parts(self)\n    refresh_parts = getattr(self, \"_refresh_part_buttons\", None)\n""",
    """    _phase6_sync_authoritative_derived_parts(self)\n    # A live Cabinet Family switch can change the authoritative physical-part\n    # topology while Corner Data is already open. Refresh that navigation in\n    # the same transaction so Receiving multipart children appear immediately.\n    _phase6_refresh_corner_data_parts_panel(self)\n    refresh_parts = getattr(self, \"_refresh_part_buttons\", None)\n""",
)

replace_once(
    "fold_designer_bridge.py",
    """        info_label = original.ttk.Label(\n            mpl_widget.master, textvariable=self.corner_data_info_var,\n            justify=original.tk.LEFT, anchor=original.tk.W, wraplength=1100,\n        )\n""",
    """        info_label = original.ttk.Label(\n            mpl_widget.master, textvariable=self.corner_data_info_var,\n            justify=original.tk.LEFT, anchor=original.tk.W, wraplength=1100,\n            font=(\"Microsoft JhengHei\", 11, \"bold\"),\n        )\n""",
)

replace_once(
    "gui.py",
    """        transform, _ox, _oy, _scale, _material_top = _phase6_2d_material_viewport(\n            bounds, cw, ch\n        )\n""",
    """        # Corner Data already owns a readable operator-info row above this\n        # canvas, so it does not need the large generic 2D annotation band.\n        # Keep side/bottom dimension channels unchanged; only reclaim vertical\n        # preview space for the authoritative unfolded material.\n        transform, _ox, _oy, _scale, _material_top = _phase6_2d_material_viewport(\n            bounds, cw, ch, top_gutter=64.0\n        )\n""",
)

replace_once(
    "gui.py",
    """        _draw_phase6_annotation_projection(\n            canvas, render_data, transform, part_key=key\n        )\n        self._draw_phase6_finished_dimension_summary(canvas, part_key=key)\n        draw_hole_editor_hint(canvas, cw, endcap=(key in {\"head\", \"tail\"}))\n""",
    """        _draw_phase6_annotation_projection(\n            canvas, render_data, transform, part_key=key\n        )\n        # Finished dimensions are already present in the Corner Data info row;\n        # drawing them again inside the canvas wastes the vertical viewport.\n        draw_hole_editor_hint(canvas, cw, endcap=(key in {\"head\", \"tail\"}))\n""",
)

print("ISSUE119_PATCH=APPLIED")
