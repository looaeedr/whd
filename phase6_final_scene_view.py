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
    _phase6_profile_base_index,
    _phase6_profile_geometry,
    _phase6_fold_mask_for_cross_coordinate,
    _phase6_profile_map_with_guides,
    _phase6_profile_map,
    _phase6_profile_flat_map,
    _phase6_folded_mesh_from_polygon,
    _phase6_mesh_feature_segments,
    _phase6_fitted_limits_from_vertices,
    _phase6_scene_fold_boundaries,
    _phase6_profile_to_scene_boundaries,
    _phase6_fold_ownership_exemptions,
    _default_number_text,
    _phase6_folded_outside_envelope,
    _phase6_profile_operator_fold_values,
    _phase6_contract_profile_rows,
    _phase6_box_body_piece_world_mapper,
    _phase6_box_body_piece_dimension_lines,
    _phase6_box_body_structure_meshes,
    format_operator_info_text,
    _phase6_triangle_bounds,
    _phase6_place_assembly_triangles,
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
    """Owner-free Final Scene orchestration over explicit typed ports."""

    def __init__(
        self,
        *,
        dependencies: FinalSceneDependencies,
        renderer: Phase6FinalSceneRenderer | None = None,
    ):
        if not isinstance(dependencies, FinalSceneDependencies):
            raise TypeError("dependencies must be FinalSceneDependencies")
        if renderer is not None and not isinstance(
            renderer, Phase6FinalSceneRenderer
        ):
            raise TypeError("renderer must be Phase6FinalSceneRenderer or None")
        self.dependencies = dependencies
        self.renderer = renderer

    def _require_renderer(self) -> Phase6FinalSceneRenderer:
        renderer = self.renderer
        if renderer is None:
            raise RuntimeError("Final Scene renderer is not connected")
        return renderer

    def query_final_render_data(self):
        deps = self.dependencies
        key = str(deps.active_part() or "")
        if not key:
            raise ValueError("no active part")

        if deps.is_physical_piece_key(key):
            return deps.physical_piece_render_data(key)

        user_joint_parts = {
            str(value or "")
            for value in tuple(deps.user_joint_parts() or ())
            if str(value or "")
        }
        if (
            key in {"box_body", "head", "tail"}
            or key.startswith("box_body:divider:")
            or key in user_joint_parts
        ):
            resolved = deps.resolve_geometry()
            return resolved.part(key).render_data

        render_data = deps.scene_query(
            key,
            deps.scene_payload_for_part(key),
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
        dependencies = self.dependencies
        resolved = dependencies.resolve_geometry()
        dependencies.publish_live_state(force=True)

        part_cls = dependencies.assembly_part_cls
        parts = tuple(
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
        )

        corner_text = dependencies.corner_dimension_text
        corner_texts = {
            part.part_key: corner_text(part.render_data)
            for part in parts
        }
        dependencies.assembly_corner_text_sink(corner_texts)

        snapshot = dict(dependencies.input_snapshot() or {})
        settings = dict(dependencies.settings_values() or {})
        thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
        formed_text = dependencies.formed_size_text
        blank_text = dependencies.blank_text
        dimensions = dependencies.operator_dimensions
        refresh_box_body = dependencies.refresh_box_body_piece_info
        for part in parts:
            dependencies.assembly_part_text_sink(
                "formed",
                part.part_key,
                formed_text(
                    part.render_data,
                    part_key=part.part_key,
                    x_profile=part.x_profile,
                    y_profile=part.y_profile,
                    thickness=thickness,
                    finished_dimensions=dimensions(part.part_key),
                ),
            )
            dependencies.assembly_part_text_sink(
                "blank",
                part.part_key,
                blank_text(part.render_data, part_key=part.part_key),
            )
            if part.part_key == "box_body" and callable(refresh_box_body):
                refresh_box_body(part.render_data)

        visibility = dependencies.assembly_visibility(parts)
        visible_part_keys = tuple(visibility[0] or ())
        visible_box_body_piece_keys = visibility[1]
        visible_set = set(visible_part_keys)
        visible_probe_parts = tuple(
            part
            for part in tuple(dependencies.interference_probe_parts() or ())
            if str(getattr(part, "part_key", "")) in visible_set
        )
        cabinet_family = dependencies.cabinet_family()
        return self.make_assembly_scene_render_data(
            assembly_parts=parts,
            visible_part_keys=visible_part_keys,
            visible_box_body_piece_keys=visible_box_body_piece_keys,
            show_interference=bool(dependencies.show_interference()),
            ignore_fixed_corner_relief=False,
            interference_probe_parts=visible_probe_parts,
            joint_diagnostics=(),
            selected_joint_id=None,
            preserve_endcap_core_origin=(cabinet_family == "受電箱"),
            render_data_cls=dependencies.assembly_render_data_cls,
        )

    def build_request(self):
        dependencies = self.dependencies
        active_part = str(dependencies.active_part() or "")
        if not active_part:
            return None

        snapshot = dict(dependencies.input_snapshot() or {})
        settings = dict(dependencies.settings_values() or {})
        thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
        alpha_bend = float(dependencies.alpha_bend())
        dimensions = dependencies.operator_dimensions
        view_mode = str(dependencies.display_mode() or "single")

        if view_mode == "assembly":
            provider = dependencies.assembly_render_provider
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
                unfolded_blank_text=dependencies.assembly_blank_text(
                    assembly_render_data
                ),
            )

        provider = dependencies.final_render_provider
        render_data = (
            provider()
            if callable(provider)
            else self.query_final_render_data()
        )
        if getattr(render_data, "pieces", None):
            x_profile, y_profile = (), ()
        else:
            x_profile, y_profile = dependencies.active_mesh_profiles(
                render_data.material
            )
        return FinalSceneViewRequest(
            render_data=render_data,
            x_profile=tuple(dict(segment) for segment in x_profile),
            y_profile=tuple(dict(segment) for segment in y_profile),
            part_key=active_part,
            alpha_bend=alpha_bend,
            finished_dimensions=dimensions(None),
            thickness=thickness,
            corner_dimension_text=dependencies.corner_dimension_text(
                render_data
            ),
            unfolded_blank_text=dependencies.blank_text(
                render_data,
                part_key=active_part,
            ),
        )

    def render_cutting_mesh(self):
        request_provider = self.dependencies.request_provider
        request = (
            request_provider()
            if callable(request_provider)
            else self.build_request()
        )
        return self._require_renderer().render(request)

    def on_scroll(self, event):
        return self._require_renderer().on_scroll(event)

    def install_renderer(self):
        request_provider = self.dependencies.request_provider
        renderer = self._require_renderer()
        renderer.install(
            request_provider if callable(request_provider) else self.build_request,
            after_render=self.dependencies.after_render,
        )
        return renderer

    def render_committed(self):
        return self.dependencies.render_committed()

    def set_preview_enabled(self, enabled):
        return self.dependencies.set_preview_enabled(bool(enabled))

    def refresh_preview(self):
        return self.dependencies.refresh_preview()


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
