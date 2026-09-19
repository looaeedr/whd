# -*- coding: utf-8 -*-
"""Phase6 FinalScene 的 3D 顯示深模組。

此模組只消費 manufacturing 已完成的 ``PartRenderData`` 與 Fold Profile。
不得建立 PartSpec、重建 CUTTING material、解析 CornerType，或重新呼叫製造引擎。
"""
from __future__ import annotations

# Complete Matplotlib projection registration before any lazy art3d import.
# Importing mpl_toolkits.mplot3d.art3d first can circularly import
# matplotlib.projections and leave the global registry without Axes3D.
from phase6_fold_profiles import _num

from phase6_final_scene_contracts import (
    AssemblyScenePart,
    AssemblySceneRenderData,
    FinalSceneDependencies,
    FinalSceneEffects,
    FinalSceneRenderResult,
    FinalSceneRuntimeState,
    FinalSceneViewRequest,
)
from phase6_final_scene_projection import (
    make_assembly_scene_render_data as _project_assembly_scene_render_data,
)


from phase6_final_scene_renderer import (
    Phase6FinalSceneRenderer,
    Phase6FinalSceneView,
    _PHASE6_DEFAULT_VIEW,
    _PHASE6_ZOOM_MIN,
    _PHASE6_ZOOM_MAX,
    _PHASE6_ZOOM_STEP,
    _configure_3d_only_figure,
    _scale_current_3d_limits,
)


class Phase6FinalSceneViewAdapter:
    """Own 3D view orchestration while consuming authoritative injected providers only."""

    def __init__(
        self,
        owner,
        *,
        dependencies: FinalSceneDependencies,
    ):
        if not isinstance(dependencies, FinalSceneDependencies):
            raise TypeError("dependencies must be FinalSceneDependencies")
        self.owner = owner
        self.dependencies = dependencies

    def query_final_render_data(self):
        owner = self.owner
        key = str(getattr(getattr(owner, "designer_workspace", None), "active_part", "") or "")
        if not key:
            raise ValueError("no active part")

        if self.dependencies.is_physical_piece_key(key):
            return self.dependencies.physical_piece_render_data(key)

        user_joint_parts = {
            str(value or "")
            for value in tuple(self.dependencies.user_joint_parts() or ())
            if str(value or "")
        }
        if (
            key in {"box_body", "head", "tail"}
            or key.startswith("box_body:divider:")
            or key in user_joint_parts
        ):
            resolved = self.dependencies.resolve_geometry()
            return resolved.part(key).render_data

        callback = getattr(owner, "_scene_query_callback", None)
        if callback is None:
            raise RuntimeError("3D final-scene provider is not connected")
        render_data = callback(
            key,
            self.dependencies.scene_payload_for_part(key),
        )
        if render_data is None:
            raise ValueError(f"manufacturing render data unavailable: {key}")
        if getattr(render_data, "pieces", None):
            return render_data
        if (
            getattr(render_data, "scene", None) is None
            or getattr(render_data, "material", None) is None
        ):
            raise TypeError(
                "manufacturing render provider must return scene + material or physical pieces"
            )
        return render_data

    def make_assembly_scene_render_data(
        self,
        *,
        assembly_parts,
        visible_part_keys=None,
        visible_box_body_piece_keys=None,
        show_interference=False,
        ignore_fixed_corner_relief=False,
        interference_probe_parts=(),
        joint_diagnostics=(),
        selected_joint_id=None,
        preserve_endcap_core_origin=False,
        render_data_cls=None,
    ):
        return _project_assembly_scene_render_data(
            assembly_parts=assembly_parts,
            visible_part_keys=visible_part_keys,
            visible_box_body_piece_keys=visible_box_body_piece_keys,
            show_interference=show_interference,
            ignore_fixed_corner_relief=ignore_fixed_corner_relief,
            interference_probe_parts=interference_probe_parts,
            joint_diagnostics=joint_diagnostics,
            selected_joint_id=selected_joint_id,
            preserve_endcap_core_origin=preserve_endcap_core_origin,
            render_data_cls=render_data_cls,
        )

    def query_assembly_render_data(self):
        owner = self.owner
        resolved = self.dependencies.resolve_geometry()
        self.dependencies.publish_live_state(force=True)

        part_cls = self.dependencies.assembly_part_cls
        parts = [
            part_cls(
                part_key=part.part_key,
                render_data=part.render_data,
                x_profile=tuple(
                    dict(segment)
                    for segment in tuple(part.x_profile or ())
                ),
                y_profile=tuple(
                    dict(segment)
                    for segment in tuple(part.y_profile or ())
                ),
                placement=part.placement,
                offset=part.offset,
            )
            for part in resolved.parts
        ]

        corner_text = self.dependencies.corner_dimension_text
        owner._phase6_last_assembly_corner_dimension_texts = {
            part.part_key: corner_text(part.render_data)
            for part in parts
        }
        for key, text in owner._phase6_last_assembly_corner_dimension_texts.items():
            var = (getattr(owner, "assembly_part_corner_vars", {}) or {}).get(key)
            if var is not None and callable(getattr(var, "set", None)):
                var.set(text)

        snapshot = getattr(owner, "_phase6_input_snapshot", {}) or {}
        settings = getattr(owner, "_settings_values", {}) or {}
        thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
        formed_text = self.dependencies.formed_size_text
        blank_text = self.dependencies.blank_text
        dimensions = self.dependencies.operator_dimensions
        refresh_box_body = self.dependencies.refresh_box_body_piece_info
        for part in parts:
            formed_var = (
                getattr(owner, "assembly_part_formed_vars", {}) or {}
            ).get(part.part_key)
            if formed_var is not None and callable(getattr(formed_var, "set", None)):
                formed_var.set(
                    formed_text(
                        part.render_data,
                        part_key=part.part_key,
                        x_profile=part.x_profile,
                        y_profile=part.y_profile,
                        thickness=thickness,
                        finished_dimensions=dimensions(part.part_key),
                    )
                )
            blank_var = (
                getattr(owner, "assembly_part_blank_vars", {}) or {}
            ).get(part.part_key)
            if blank_var is not None and callable(getattr(blank_var, "set", None)):
                blank_var.set(
                    blank_text(part.render_data, part_key=part.part_key)
                )
            if (
                part.part_key == "box_body"
                and callable(refresh_box_body)
            ):
                refresh_box_body(part.render_data)

        visible_vars = getattr(owner, "assembly_part_visible_vars", {}) or {}
        visible_parts = [
            part
            for part in parts
            if bool(
                getattr(
                    visible_vars.get(part.part_key),
                    "get",
                    lambda: True,
                )()
            )
        ]
        if not visible_parts and parts:
            fallback = next(
                (part for part in parts if part.part_key == "box_body"),
                parts[0],
            )
            visible_parts = [fallback]
            var = visible_vars.get(fallback.part_key)
            if var is not None and callable(getattr(var, "set", None)):
                var.set(True)

        visible_keys = {part.part_key for part in visible_parts}
        box_part = next(
            (part for part in parts if part.part_key == "box_body"),
            None,
        )
        box_piece_keys = tuple(
            f"box_body:{str(getattr(piece, 'role', '') or '').strip()}"
            for piece in tuple(
                getattr(
                    getattr(box_part, "render_data", None),
                    "pieces",
                    (),
                )
                or ()
            )
            if str(getattr(piece, "role", "") or "").strip()
        )
        visible_box_body_piece_keys = None
        if box_piece_keys:
            piece_vars = dict(
                getattr(owner, "assembly_box_body_piece_visible_vars", {}) or {}
            )
            if "box_body" not in visible_keys:
                visible_box_body_piece_keys = ()
            else:
                visible_box_body_piece_keys = tuple(
                    key
                    for key in box_piece_keys
                    if bool(
                        getattr(
                            piece_vars.get(key),
                            "get",
                            lambda: True,
                        )()
                    )
                )
                if (
                    not visible_box_body_piece_keys
                    and visible_keys == {"box_body"}
                ):
                    first = box_piece_keys[0]
                    var = piece_vars.get(first)
                    if var is not None and callable(getattr(var, "set", None)):
                        var.set(True)
                    visible_box_body_piece_keys = (first,)

        visible_probe_parts = tuple(
            part
            for part in tuple(
                getattr(owner, "_phase6_last_interference_probe_parts", ())
                or ()
            )
            if part.part_key in visible_keys
        )
        show_var = getattr(owner, "assembly_show_interference_var", None)
        show_interference = (
            bool(show_var.get()) if show_var is not None else True
        )
        cabinet_family = self.dependencies.cabinet_family()
        render_data_cls = self.dependencies.assembly_render_data_cls
        return self.make_assembly_scene_render_data(
            assembly_parts=tuple(parts),
            visible_part_keys=tuple(
                part.part_key for part in visible_parts
            ),
            visible_box_body_piece_keys=visible_box_body_piece_keys,
            show_interference=show_interference,
            ignore_fixed_corner_relief=False,
            interference_probe_parts=visible_probe_parts,
            joint_diagnostics=(),
            selected_joint_id=None,
            preserve_endcap_core_origin=(cabinet_family == "受電箱"),
            render_data_cls=render_data_cls,
        )

    def build_request(self):
        owner = self.owner
        workspace = getattr(owner, "designer_workspace", None)
        active_part = getattr(workspace, "active_part", None)
        if not active_part:
            return None

        snapshot = getattr(owner, "_phase6_input_snapshot", {}) or {}
        settings = getattr(owner, "_settings_values", {}) or {}
        thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
        alpha_bend = float(
            getattr(getattr(owner, "state", None), "alpha_bend", 0.85)
        )
        dimensions = self.dependencies.operator_dimensions
        view_mode = str(
            getattr(owner, "_phase6_3d_display_mode", "single") or "single"
        )

        if view_mode == "assembly":
            provider = self.dependencies.assembly_render_provider
            assembly_render_data = (
                provider()
                if callable(provider)
                else self.query_assembly_render_data()
            )
            return FinalSceneViewRequest(
                render_data=assembly_render_data,
                x_profile=(),
                y_profile=(),
                part_key="assembly",
                alpha_bend=alpha_bend,
                finished_dimensions=dimensions(None),
                thickness=thickness,
                unfolded_blank_text=self.dependencies.assembly_blank_text(
                    assembly_render_data
                ),
            )

        provider = self.dependencies.final_render_provider
        render_data = (
            provider()
            if callable(provider)
            else self.query_final_render_data()
        )
        if getattr(render_data, "pieces", None):
            x_profile, y_profile = (), ()
        else:
            x_profile, y_profile = self.dependencies.active_mesh_profiles(
                render_data.material
            )
        key = str(active_part)
        return FinalSceneViewRequest(
            render_data=render_data,
            x_profile=tuple(dict(segment) for segment in x_profile),
            y_profile=tuple(dict(segment) for segment in y_profile),
            part_key=key,
            alpha_bend=alpha_bend,
            finished_dimensions=dimensions(None),
            thickness=thickness,
            corner_dimension_text=self.dependencies.corner_dimension_text(
                render_data
            ),
            unfolded_blank_text=self.dependencies.blank_text(
                render_data,
                part_key=key,
            ),
        )

    def render_cutting_mesh(self):
        owner = self.owner
        view = getattr(owner, "final_scene_view", None)
        if view is None:
            view = Phase6FinalSceneView(
                owner.renderer,
                number_text=self.dependencies.number_text,
            )
            owner.final_scene_view = view
        request_provider = self.dependencies.request_provider
        request = (
            request_provider()
            if callable(request_provider)
            else self.build_request()
        )
        triangles = view.render(request)
        mirror = self.dependencies.mirror_view_state
        if callable(mirror):
            mirror(view)
        return triangles

    def on_scroll(self, event):
        view = getattr(self.owner, "final_scene_view", None)
        if view is not None:
            return view.on_scroll(event)
        return None

    def install_renderer(self):
        owner = self.owner
        view = Phase6FinalSceneView(
            owner.renderer,
            number_text=self.dependencies.number_text,
        )
        owner.final_scene_view = view
        try:
            owner.renderer.canvas.get_tk_widget().configure(takefocus=False)
        except Exception:
            pass
        request_provider = self.dependencies.request_provider
        view.install(
            request_provider if callable(request_provider) else self.build_request,
            after_render=self.dependencies.after_render,
        )
        return view

    def render_committed(self):
        owner = self.owner
        if not getattr(owner, "preview_3d_enabled", True):
            return None
        canvas = owner.renderer.canvas
        draw = getattr(canvas, "draw", None)
        draw_idle = getattr(canvas, "draw_idle", None)
        if (
            callable(draw)
            and callable(draw_idle)
            and not getattr(owner, "_phase6_force_sync_preview", False)
        ):
            canvas.draw = draw_idle
            try:
                return owner.renderer.render()
            finally:
                canvas.draw = draw
        return owner.renderer.render()

    def set_preview_enabled(self, enabled):
        owner = self.owner
        enabled = bool(enabled)
        owner.preview_3d_enabled = enabled
        var = getattr(owner, "preview_3d_var", None)
        if var is not None and bool(var.get()) != enabled:
            var.set(enabled)
        widget = owner.renderer.canvas.get_tk_widget()
        if enabled:
            if not widget.winfo_manager():
                widget.pack(fill="both", expand=True)
            owner.submit_update_intent("display", commit=True)
        elif widget.winfo_manager() == "pack":
            widget.pack_forget()

    def refresh_preview(self):
        owner = self.owner
        if not getattr(owner, "preview_3d_enabled", True):
            self.set_preview_enabled(True)
            return None
        owner._phase6_force_sync_preview = True
        try:
            return owner.submit_update_intent("display", commit=True)
        finally:
            owner._phase6_force_sync_preview = False

def _compat_view(owner):
    view = getattr(owner, "final_scene_view", None)
    if view is None:
        view = Phase6FinalSceneView(owner.renderer)
    return view


def _phase6_remove_original_bend_surfaces(owner):
    return _compat_view(owner)._remove_original_bend_surfaces()


def _phase6_add_mesh_boundary_lines(owner, triangles, color):
    return _compat_view(owner)._add_mesh_boundary_lines(triangles, color)


def _phase6_draw_scene_bends(owner, scene, x_profile, y_profile, fold_guides=()):
    return _compat_view(owner)._draw_scene_bends(scene, x_profile, y_profile, fold_guides=fold_guides)


def _phase6_draw_scene_markings(owner, scene, x_profile, y_profile, fold_guides=()):
    return _compat_view(owner)._draw_scene_markings(scene, x_profile, y_profile, fold_guides=fold_guides)


def _phase6_configure_3d_only_figure(owner):
    return _configure_3d_only_figure(owner.renderer)


def _phase6_scale_current_3d_limits(owner, ratio):
    view = getattr(owner, "final_scene_view", None)
    if view is not None:
        return view.scale_current_3d_limits(ratio)
    return _scale_current_3d_limits(owner.renderer, ratio)


def _phase6_adjust_zoom_scale(owner, direction):
    view = getattr(owner, "final_scene_view", None)
    if view is not None:
        return view.adjust_zoom_scale(direction)
    old = float(getattr(owner, "_phase6_zoom_scale", 1.0) or 1.0)
    if str(direction).lower() == "up":
        new = max(_PHASE6_ZOOM_MIN, old * _PHASE6_ZOOM_STEP)
    elif str(direction).lower() == "down":
        new = min(_PHASE6_ZOOM_MAX, old / _PHASE6_ZOOM_STEP)
    else:
        return old
    owner._phase6_zoom_scale = new
    return new
