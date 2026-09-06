from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_gui():
    path = Path("gui.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '        self.door_layout_selected_var = tk.StringVar(value="0:0")\n        self.door_layout_columns = []\n        # Family-authoritative inner-door presence/config. Geometry spans are\n',
        '        self.door_layout_selected_var = tk.StringVar(value="0:0")\n        self.door_layout_columns = []\n        # UI adapter only. Authoritative inner-door enable state remains\n        # self.receiving_inner_doors; these vars are rebuilt from that state.\n        self.door_layout_inner_door_vars = {}\n        # Family-authoritative inner-door presence/config. Geometry spans are\n',
        "gui inner-door vars",
    )

    text = replace_once(
        text,
        '            return manufacturing_api.build_box_body_divider_render_data(divider)\n\n        if key.startswith("inner_door:") and key.endswith("_frame"):\n',
        '            return manufacturing_api.build_box_body_divider_render_data(divider)\n\n        if key.startswith("inner_door:") and key.endswith(":panel"):\n            data = dict(payload or {})\n            panels = cabinet_family_policy.derive_inner_door_panels(data)\n            panel = next((item for item in panels if item.stable_id == key), None)\n            if panel is None:\n                raise ValueError(f"內門板 stable_id 不存在於 authoritative topology: {key}")\n            return manufacturing_api.build_inner_door_panel_render_data(panel)\n\n        if key.startswith("inner_door:") and key.endswith("_frame"):\n',
        "gui render panel",
    )

    helper_anchor = '    def refresh_door_layout_status(self):\n'
    helper_block = '''    @staticmethod\n    def _receiving_inner_door_stable_id_for_cell(cell_key):\n        key = str(cell_key or "").strip()\n        if key == "0:0":\n            return "upper"\n        if key == "0:1":\n            return "lower"\n        try:\n            column, row = (int(v) for v in key.split(":", 1))\n        except (TypeError, ValueError):\n            raise ValueError(f"invalid door cell key: {cell_key!r}")\n        return f"c{column + 1}r{row + 1}"\n\n    def _receiving_inner_door_enabled(self, cell_key):\n        key = str(cell_key or "").strip()\n        return any(\n            isinstance(item, dict) and str(item.get("cell_key") or "").strip() == key\n            for item in list(getattr(self, "receiving_inner_doors", []) or [])\n        )\n\n    def _set_receiving_inner_door_enabled(self, cell_key, enabled):\n        key = str(cell_key or "").strip()\n        items = [deepcopy(item) for item in list(getattr(self, "receiving_inner_doors", []) or []) if isinstance(item, dict)]\n        existing = next((item for item in items if str(item.get("cell_key") or "").strip() == key), None)\n        items = [item for item in items if str(item.get("cell_key") or "").strip() != key]\n        if bool(enabled):\n            stable_id = str((existing or {}).get("stable_id") or self._receiving_inner_door_stable_id_for_cell(key)).strip()\n            item = deepcopy(existing or {})\n            item.update({\n                "stable_id": stable_id,\n                "cell_key": key,\n                "included_frame_sides": list(item.get("included_frame_sides") or ("top", "left", "right")),\n            })\n            items.append(item)\n        def sort_key(item):\n            raw = str(item.get("cell_key") or "")\n            try:\n                return tuple(int(v) for v in raw.split(":", 1))\n            except Exception:\n                return (10**9, 10**9)\n        items.sort(key=sort_key)\n        self.receiving_inner_doors = items\n        return bool(enabled)\n\n    def _commit_receiving_inner_door_checkbox(self, cell_key):\n        key = str(cell_key or "").strip()\n        var = dict(getattr(self, "door_layout_inner_door_vars", {}) or {}).get(key)\n        enabled = bool(var.get()) if var is not None else False\n        self._set_receiving_inner_door_enabled(key, enabled)\n        owner = getattr(self, "_derived_cache_owner", None)\n        if owner is not None:\n            owner.invalidate("geometry")\n        scheduler = getattr(self, "_phase6_update_scheduler", None)\n        if scheduler is not None:\n            scheduler.mark_dirty("inner_door")\n        if hasattr(self, "canvas_door"):\n            try:\n                self.draw_door_layout_overview()\n            except Exception:\n                pass\n        return enabled\n\n'''
    if helper_block not in text:
        if text.count(helper_anchor) != 1:
            raise RuntimeError("gui helper anchor missing/ambiguous")
        text = text.replace(helper_anchor, helper_block + helper_anchor, 1)

    text = replace_once(
        text,
        '        for widget in self.door_layout_columns_frame.winfo_children():\n            widget.destroy()\n        self._ensure_door_layout_default()\n',
        '        for widget in self.door_layout_columns_frame.winfo_children():\n            widget.destroy()\n        self.door_layout_inner_door_vars = {}\n        self._ensure_door_layout_default()\n',
        "gui reset inner vars",
    )

    checkbox_old = '''                    ).pack(side=tk.LEFT, padx=(1, 0))\n\n            if not column.get("width_auto"):\n'''
    checkbox_new = '''                    ).pack(side=tk.LEFT, padx=(1, 0))\n\n                if str(self.baseline_var.get() or "").strip() == "受電箱":\n                    cell_key = f"{column_index}:{row_index}"\n                    inner_var = tk.BooleanVar(\n                        master=self.root,\n                        value=self._receiving_inner_door_enabled(cell_key),\n                    )\n                    self.door_layout_inner_door_vars[cell_key] = inner_var\n                    tk.Checkbutton(\n                        height_row, text="內門", variable=inner_var,\n                        bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,\n                        activebackground=self.COLOR_PANEL, activeforeground=self.COLOR_ACCENT,\n                        font=('Microsoft JhengHei', 8, 'bold'), cursor="hand2",\n                        command=lambda key=cell_key: self._commit_receiving_inner_door_checkbox(key),\n                    ).pack(side=tk.LEFT, padx=(5, 0))\n\n            if not column.get("width_auto"):\n'''
    text = replace_once(text, checkbox_old, checkbox_new, "gui checkbox")
    path.write_text(text, encoding="utf-8")


def patch_bridge():
    path = Path("fold_designer_bridge.py")
    text = path.read_text(encoding="utf-8")

    old = '''    frames = derive_all_inner_door_frames(tuple(frame_sets))\n    sync_derived_parts(\n        namespace="inner_door:",\n        part_profiles=inner_door_frame_part_profiles(frames),\n    )\n    return tuple(divider_profiles), tuple(frame.stable_id for frame in frames)\n'''
    new = '''    frames = derive_all_inner_door_frames(tuple(frame_sets))\n    from ae_engine.inner_door_panels import inner_door_panel_part_profiles\n    panels = cabinet_family_policy.derive_inner_door_panels(snapshot)\n    inner_profiles = inner_door_frame_part_profiles(frames)\n    inner_profiles.update(inner_door_panel_part_profiles(panels))\n    sync_derived_parts(\n        namespace="inner_door:",\n        part_profiles=inner_profiles,\n    )\n    return (\n        tuple(divider_profiles),\n        tuple([*(frame.stable_id for frame in frames), *(panel.stable_id for panel in panels)]),\n    )\n'''
    text = replace_once(text, old, new, "bridge derived sync")

    text = replace_once(
        text,
        '        or (key.startswith("inner_door:") and key.endswith("_frame"))\n    )\n',
        '        or (key.startswith("inner_door:") and key.endswith("_frame"))\n        or (key.startswith("inner_door:") and key.endswith(":panel"))\n    )\n',
        "bridge derived predicate",
    )

    label_anchor = '''    if key.startswith("inner_door:") and key.endswith("_frame"):\n        side = key.rsplit(":", 1)[-1].removesuffix("_frame")\n'''
    label_new = '''    if key.startswith("inner_door:") and key.endswith(":panel"):\n        door_id = key.split(":", 2)[1]\n        door_label = {"upper": "上層內門", "lower": "下層內門"}.get(door_id, "內門")\n        return f"{door_label}門板"\n    if key.startswith("inner_door:") and key.endswith("_frame"):\n        side = key.rsplit(":", 1)[-1].removesuffix("_frame")\n'''
    text = replace_once(text, label_anchor, label_new, "bridge panel label")
    path.write_text(text, encoding="utf-8")


def patch_manufacturing():
    path = Path("ae_engine/manufacturing_api.py")
    text = path.read_text(encoding="utf-8")
    marker = 'def build_inner_door_frame_render_data(frame) -> PartRenderData:\n'
    block = '''def build_inner_door_panel_render_data(panel) -> PartRenderData:\n    """Build one flat physical inner-door panel from its canonical part."""\n    from .inner_door_panels import InnerDoorPanelPart\n    from .sheetmetal_drawing import DrawingScene, PolylinePrimitive\n    from .sheetmetal_geometry import Vec2\n\n    if not isinstance(panel, InnerDoorPanelPart):\n        raise TypeError("panel must be InnerDoorPanelPart")\n    w = float(panel.width)\n    h = float(panel.height)\n    scene = DrawingScene()\n    scene.add(PolylinePrimitive(\n        points=(Vec2(0.0, 0.0), Vec2(w, 0.0), Vec2(w, h), Vec2(0.0, h)),\n        layer="CUTTING", closed=True,\n    ))\n    topology = UnfoldedBlankTopology(\n        piece_id=str(panel.stable_id),\n        x_segments=(MaterialSegment("X", "inner_door_panel_width", w, "INNER_DOOR_PANEL_FINISHED_AREA"),),\n        y_segments=(MaterialSegment("Y", "inner_door_panel_height", h, "INNER_DOOR_PANEL_FINISHED_AREA"),),\n        source="INNER_DOOR_PANEL_FINISHED_AREA", revision=1,\n    )\n    return PartRenderData(\n        scene=scene,\n        material=material_polygon_from_final_scene(scene),\n        fold_guides=(),\n        metadata={\n            "stable_id": str(panel.stable_id),\n            "inner_door_id": str(panel.inner_door_id),\n            "cell_key": str(panel.cell_key),\n            "thickness": float(panel.thickness),\n        },\n        unfolded_topology=topology,\n    )\n\n\n'''
    if block not in text:
        if text.count(marker) != 1:
            raise RuntimeError("manufacturing frame marker missing/ambiguous")
        text = text.replace(marker, block + marker, 1)
    path.write_text(text, encoding="utf-8")


patch_gui()
patch_bridge()
patch_manufacturing()
