# -*- coding: utf-8 -*-
"""Phase 3 T5 2D / Corner-Data view adapter.

Consumes authoritative identities, render data, dimensions, and measurement
providers. It owns only view projection/format/viewport decisions and never
solves or reconstructs manufacturing geometry.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Phase6CornerDataViewAdapter:
    def __init__(self, *, selected_part_key=None) -> None:
        self._selected_part_key = (
            None if selected_part_key in (None, "") else str(selected_part_key)
        )

    @property
    def selected_part_key(self):
        return self._selected_part_key

    @staticmethod
    def back_panel_mode_is_applicable(
        selected_part_key,
        *,
        family_name,
        active_type,
        three_piece_type,
    ) -> bool:
        return (
            str(selected_part_key or "") == "box_body:back"
            and str(family_name or "") == "受電箱"
            and str(active_type or "") == str(three_piece_type or "")
        )

    @staticmethod
    def refresh_back_panel_mode_control(
        owner,
        *,
        applicable,
        current_label,
        values,
        on_selected,
    ) -> bool:
        """Rebuild the Corner Data back-panel selector as view-only projection."""
        frame = getattr(owner, "corner_data_back_panel_mode_control", None)
        if frame is not None:
            try:
                if frame.winfo_exists():
                    frame.destroy()
            except Exception:
                pass
        owner.corner_data_back_panel_mode_control = None
        owner.corner_data_back_panel_mode_selector = None

        panel = getattr(owner, "corner_data_panel", None)
        if panel is None or not bool(applicable):
            return False

        var = getattr(owner, "back_panel_mode_var", None)
        if var is None:
            var = tk.StringVar(master=panel, value=str(current_label))
            owner.back_panel_mode_var = var
        elif str(var.get() or "") != str(current_label):
            var.set(str(current_label))

        frame = ttk.Frame(panel)
        ttk.Label(frame, text="後面板形式").pack(side=tk.LEFT, padx=(0, 6))
        selector = ttk.Combobox(
            frame,
            textvariable=var,
            values=tuple(values or ()),
            state="readonly",
            width=10,
        )
        selector.pack(side=tk.LEFT)
        selector.bind("<<ComboboxSelected>>", lambda _event: on_selected(var))
        frame.pack(fill=tk.X, pady=(2, 6))
        owner.corner_data_back_panel_mode_control = frame
        owner.corner_data_back_panel_mode_selector = selector
        return True

    def prepare_canvas(
        self,
        owner,
        *,
        canvas_bg,
        on_configure,
        on_mousewheel,
        visibility_plan=None,
    ):
        """Own Corner Data Tk canvas/info-label lifecycle and visibility effects."""
        renderer = getattr(owner, "renderer", None)
        mpl_canvas = getattr(renderer, "canvas", None)
        get_widget = getattr(mpl_canvas, "get_tk_widget", None)
        if not callable(get_widget):
            return None
        mpl_widget = get_widget()

        canvas = getattr(owner, "corner_data_canvas", None)
        try:
            canvas_alive = canvas is not None and bool(canvas.winfo_exists())
        except Exception:
            canvas_alive = canvas is not None

        info_var = getattr(owner, "corner_data_info_var", None)
        if info_var is None:
            info_var = tk.StringVar(master=mpl_widget.master, value="")
            owner.corner_data_info_var = info_var

        info_label = getattr(owner, "corner_data_info_label", None)
        try:
            info_alive = info_label is not None and bool(info_label.winfo_exists())
        except Exception:
            info_alive = info_label is not None
        if not info_alive:
            info_label = ttk.Label(
                mpl_widget.master,
                textvariable=info_var,
                justify=tk.LEFT,
                anchor=tk.W,
                wraplength=1100,
                font=("Microsoft JhengHei", 11, "bold"),
            )
            owner.corner_data_info_label = info_label

        if not canvas_alive:
            canvas = tk.Canvas(
                mpl_widget.master,
                bg=str(canvas_bg),
                highlightthickness=0,
                takefocus=False,
            )
            owner.corner_data_canvas = canvas
            canvas._phase6_unfold_zoom = 1.0
            canvas.bind("<Configure>", on_configure)
            canvas.bind("<MouseWheel>", on_mousewheel)
            canvas.bind("<Button-4>", on_mousewheel)
            canvas.bind("<Button-5>", on_mousewheel)

        plan = dict(visibility_plan or self.canvas_visibility_plan(True))
        if not plan["mpl_canvas"] and mpl_widget.winfo_manager():
            mpl_widget.pack_forget()
        if plan["info_label"] and not info_label.winfo_manager():
            info_label.pack(fill=tk.X, padx=8, pady=(6, 2))
        if plan["corner_canvas"] and not canvas.winfo_manager():
            canvas.pack(fill=tk.BOTH, expand=True)
        return canvas

    def refresh_parts_panel(
        self,
        owner,
        *,
        keys,
        selected,
        navigation_rows,
        label_for,
        on_select,
        on_refresh_back_panel_mode,
    ) -> tuple[str, ...]:
        """Own Corner Data parts-list widget rebuild while preserving selection authority."""
        keys = tuple(str(key) for key in tuple(keys or ()))
        owner.corner_data_part_keys = keys
        if selected is not None:
            on_select(selected)

        panel = getattr(owner, "corner_data_panel", None)
        if panel is None or not hasattr(panel, "winfo_children"):
            return keys

        for child in tuple(panel.winfo_children()):
            child.destroy()
        owner.corner_data_back_panel_mode_control = None
        owner.corner_data_back_panel_mode_selector = None
        owner.corner_data_part_rows = {}
        owner.corner_data_part_buttons = {}
        owner.corner_data_part_depths = {}

        for key, depth in tuple(navigation_rows or ()):
            row = ttk.Frame(panel)
            row.pack(fill=tk.X, pady=(0, 4), padx=(18, 0) if depth else 0)
            button = ttk.Button(
                row,
                text=label_for(key),
                command=lambda k=key: on_select(k),
            )
            button.pack(side=tk.LEFT, fill=tk.X, expand=True)
            owner.corner_data_part_rows[key] = row
            owner.corner_data_part_buttons[key] = button
            owner.corner_data_part_depths[key] = depth
        on_refresh_back_panel_mode()
        return keys

    @staticmethod
    def part_keys(workspace) -> tuple[str, ...]:
        return tuple(
            str(key)
            for key in tuple(getattr(workspace, "available_parts", ()) or ())
        )

    @staticmethod
    def navigation_rows(part_keys, *, hierarchy_projector):
        return tuple(
            (row.part_key, row.depth)
            for row in hierarchy_projector(tuple(part_keys or ()))
        )

    def resolve_selection(self, part_keys, requested, *, resolver):
        keys = tuple(str(key) for key in tuple(part_keys or ()))
        resolved = resolver(str(requested or ""))
        if resolved not in keys:
            resolved = None
        self._selected_part_key = resolved
        return resolved

    @staticmethod
    def info_request(
        *,
        part_key,
        render_data,
        request_factory,
        profile_provider,
        dimensions_provider,
        corner_text_provider,
        blank_text_provider,
        alpha_bend,
        thickness,
    ):
        key = str(part_key or "")
        if getattr(render_data, "pieces", None):
            x_profile, y_profile = (), ()
        else:
            material = getattr(render_data, "material", None)
            x_profile, y_profile = (
                ((), ())
                if material is None
                else profile_provider(key, material)
            )
        return request_factory(
            render_data=render_data,
            x_profile=tuple(dict(seg) for seg in (x_profile or ())),
            y_profile=tuple(dict(seg) for seg in (y_profile or ())),
            part_key=key,
            alpha_bend=float(alpha_bend),
            finished_dimensions=dimensions_provider(key),
            thickness=float(thickness),
            corner_dimension_text=corner_text_provider(render_data),
            unfolded_blank_text=blank_text_provider(render_data, part_key=key),
        )

    @staticmethod
    def unfold_projection(
        part_key,
        *,
        available_parts,
        render_provider,
        projection_factory,
    ):
        selected = str(part_key or "")
        keys = tuple(str(key) for key in tuple(available_parts or ()))
        if not selected or selected not in keys:
            return None
        render_data = render_provider(selected)
        if render_data is None:
            return None
        return projection_factory(part_key=selected, render_data=render_data)

    @staticmethod
    def unfold_projections(part_keys, *, projection_provider):
        rows = []
        for part_key in tuple(part_keys or ()):
            projection = projection_provider(part_key)
            if projection is not None:
                rows.append(projection)
        return tuple(rows)

    def selected_projection(self, *, projection_provider):
        return projection_provider(self._selected_part_key)

    @staticmethod
    def view_payload(projection, *, info_provider):
        if projection is None:
            return None
        return {
            "projection": projection,
            "info_text": info_provider(
                projection.part_key,
                projection.render_data,
            ),
        }

    @staticmethod
    def zoom_from_event(current_zoom, *, delta=0, button=0):
        try:
            delta = int(delta or 0)
        except (TypeError, ValueError):
            delta = 0
        try:
            button = int(button or 0)
        except (TypeError, ValueError):
            button = 0
        direction = (
            1 if (delta > 0 or button == 4)
            else -1 if (delta < 0 or button == 5)
            else 0
        )
        if direction == 0:
            return None
        try:
            current = float(current_zoom or 1.0)
        except (TypeError, ValueError):
            current = 1.0
        step = 1.12
        updated = current * step if direction > 0 else current / step
        return max(0.50, min(3.00, updated))

    @staticmethod
    def edge_host_placement(edge) -> dict:
        edge = str(edge).upper()
        if edge == "TOP":
            return {"relx": 0.5, "y": 8, "anchor": "n"}
        if edge == "BOTTOM":
            return {"relx": 0.5, "rely": 1.0, "y": -8, "anchor": "s"}
        if edge == "LEFT":
            return {"x": 8, "rely": 0.5, "anchor": "w"}
        if edge == "RIGHT":
            return {"relx": 1.0, "x": -8, "rely": 0.5, "anchor": "e"}
        return {}

    @staticmethod
    def formed_size_text(finished_dimensions, *, number_text) -> str:
        values = []
        for value in tuple(finished_dimensions or ()):
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number > 1e-7:
                values.append(number)
        primary = sorted(values, reverse=True)[:2]
        if len(primary) < 2:
            return "成形尺寸：-"
        return (
            f"成形尺寸：{number_text(primary[0])} × "
            f"{number_text(primary[1])} mm"
        )

    @staticmethod
    def unfolded_blank_text(
        render_data,
        *,
        part_key,
        measurer,
        number_text,
    ) -> str:
        if render_data is None:
            return "展開料：-"
        try:
            blanks = measurer(render_data, part_key=str(part_key or "part"))
        except Exception:
            return "展開料：-"
        if not blanks:
            return "展開料：-"

        piece_labels = {
            "left_side": "左側板",
            "back": "後面板",
            "right_side": "右側板",
            "box_body_left_side": "左側板",
            "box_body_back": "後面板",
            "box_body_right_side": "右側板",
            "left": "左箱身",
            "middle": "中箱身",
            "right": "右箱身",
        }
        rows = []
        multi = len(blanks) > 1
        for blank in blanks:
            label = ""
            if multi:
                suffix = str(blank.part_key).rsplit(":", 1)[-1]
                label = f"{piece_labels.get(suffix, suffix)} "
            rows.append(
                f"{label}{number_text(blank.width)} × "
                f"{number_text(blank.height)} mm"
            )
        return "展開料：" + "；".join(rows)

    @staticmethod
    def current_unfolded_size(render_data, *, part_key, measurer):
        if render_data is None:
            return None
        blanks = measurer(render_data, part_key=str(part_key or "part"))
        if not blanks:
            return None
        blank = blanks[0]
        return float(blank.width), float(blank.height)

    @staticmethod
    def registry_preview_geometry(result):
        outer = (15.0, 15.0, 225.0, 145.0)
        if not result:
            return {"outer": outer, "cuts": ()}
        pu = float(result["primary_u"])
        pv = float(result["primary_v"])
        secondary_depth = float(result.get("secondary_depth") or 0.0)
        scale = min(
            180.0 / max(pu, 1.0),
            95.0 / max(pv + secondary_depth, 1.0),
        )
        x0, y0 = 20.0, 140.0
        cuts = [
            (x0, y0 - pv * scale, x0 + pu * scale, y0)
        ]
        if result.get("secondary_u") is not None:
            su = float(result["secondary_u"])
            sd = float(result["secondary_depth"])
            cuts.append(
                (
                    x0,
                    y0 - (pv + sd) * scale,
                    x0 + su * scale,
                    y0 - pv * scale,
                )
            )
        return {"outer": outer, "cuts": tuple(cuts)}

    @staticmethod
    def canvas_visibility_plan(show_corner_data: bool) -> dict:
        show = bool(show_corner_data)
        return {
            "corner_canvas": show,
            "info_label": show,
            "mpl_canvas": not show,
        }
