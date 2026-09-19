# -*- coding: utf-8 -*-
"""Phase 3 T5 2D / Corner-Data view adapter.

Consumes authoritative identities, render data, dimensions, and measurement
providers. It owns only view projection/format/viewport decisions and never
solves or reconstructs manufacturing geometry.
"""
from __future__ import annotations


class Phase6CornerDataViewAdapter:
    def __init__(self, *, selected_part_key=None) -> None:
        self._selected_part_key = (
            None if selected_part_key in (None, "") else str(selected_part_key)
        )

    @property
    def selected_part_key(self):
        return self._selected_part_key

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
