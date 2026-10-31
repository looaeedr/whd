# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

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


def receiving_base_source_display_warnings(snapshot, cabinet_family):
    """Explain unresolved physical sources, never demand obsolete manual fields.

    Current #1502 may uniquely derive a CENTER/LEFT physical base from
    committed NFB CSV and source geometry without receiving_base_plate.
    The same canonical resolver used by production must decide; do not
    mistake an absent legacy manual mapping for absent material.
    """
    if cabinet_family != "受電箱":
        return ()
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    try:
        resolved = receiving_base_plate_values(snapshot)
    except (ValueError, TypeError, KeyError) as exc:
        return (
            "受電箱實體底板來源驗證失敗：" + str(exc)
            + "；不可冒用通用底板或假畫固定片打標線",
        )
    if resolved is None:
        return (
            "受電箱實體底板尚未配置或來源不足：請核對目前 NFB "
            "CSV／已提交層別及原實體板件來源；"
            "未證實來源前不顯示底板與固定片打標線",
        )
    return ()


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
        # Cache only the immutable, optional display mesh for identical
        # source. Do not re-fold two/four EARs on every Tk Configure event.
        self._formed_ear_display_cache = None
        self.last_formed_ear_display_blocker = None
        self._formed_pad_display_cache = None
        self.last_formed_pad_display_blocker = None

    def _formed_pad_assembly_preview(self, snapshot, visible_set, assembly_parts):
        """Cached, source-matched PAD physical skins; DISPLAY ONLY, no MFG."""
        if snapshot.get("model") not in ("受電箱","RECEIVING") or (
                snapshot.get("nfb_config_submitted") is not True):
            self.last_formed_pad_display_blocker = None
            return ()
        try:
            from ae_engine.receiving_nfb_pad_preview_cache import (
                pad_preview_source_fingerprint,
            )
            # Source CSV, editable shared tooling, and actual Base Plate
            # CUTTING material all invalidate a formerly valid cached mesh.
            source_key = pad_preview_source_fingerprint(snapshot,assembly_parts)
        except (ValueError, TypeError, OSError, KeyError) as exc:
            self.last_formed_pad_display_blocker = str(exc)
            self._formed_pad_display_cache = None
            return ()
        cached=self._formed_pad_display_cache
        if cached is None or cached[0]!=source_key:
            try:
                from ae_engine.receiving_nfb_pad_assembly_preview import (
                    build_committed_pad_assembly_display,
                )
                all_skins=build_committed_pad_assembly_display(snapshot,assembly_parts)
                if any(skin.manufacturing_ready or skin.assembly_contact_certified
                       for skin in all_skins):
                    raise ValueError("PAD_DISPLAY_MFG_OR_CONTACT_GATE_INVALID")
                blocker=None
            except (ValueError, TypeError, OSError, KeyError, AttributeError) as exc:
                all_skins=()
                blocker=str(exc)
            self._formed_pad_display_cache=(source_key,all_skins,blocker)
        else:
            all_skins,blocker=cached[1:]
        self.last_formed_pad_display_blocker=blocker
        return tuple(
            skin for skin in all_skins if skin.parent_base_id in visible_set
        )

    def _pad_display_warnings(self):
        """Surface a PAD failure; a blank 3D must not masquerade as complete."""
        reason = self.last_formed_pad_display_blocker
        if not reason:
            return ()
        return ("PAD 3D 來源／貼合檢查未通過：" + str(reason)
                + "；已隱藏未驗證的墊高片，正式製造輸出仍禁止",)

    def _ear_display_warnings(self):
        """Explain a hidden EAR without treating display as MFG approval."""
        reason = self.last_formed_ear_display_blocker
        if not reason:
            return ()
        return (
            "EAR 3D 來源檢查未通過：" + str(reason)
            + "；已隱藏未驗證的固定片，正式加工仍須獨立驗證",
        )

    def _formed_ear_assembly_preview(self, snapshot, visible_set):
        """Source-backed world skins, NEVER extra manufacturing assembly parts.

        Failure leaves the cabinet 3D usable without painting an uncertified
        EAR. No padding, DXF intermediates, new PartSpec, or production gate.
        """
        if snapshot.get("model") not in ("受電箱", "RECEIVING") or snapshot.get("nfb_config_submitted") is not True:
            self.last_formed_ear_display_blocker = None
            return ()
        import hashlib
        from ae_engine.receiving_base_fixing_plate_geometry import SOURCE_DXF_SHA256
        source_key = hashlib.sha256(
            (SOURCE_DXF_SHA256 + repr(snapshot)).encode("utf-8")
        ).hexdigest()
        cached = self._formed_ear_display_cache
        if cached is None or cached[0] != source_key:
            try:
                from ae_engine.receiving_tier_ear_assembly_xy import (
                    resolve_receiving_tier_ear_mating_xy,
                )
                from ae_engine.receiving_fixed_plate_formed_skins import (
                    build_receiving_formed_fixing_plate_skins,
                )
                owners = resolve_receiving_tier_ear_mating_xy(snapshot)
                if len(owners) not in (2, 4):
                    raise ValueError("EAR_ASSEMBLY_DISPLAY_OWNER_COUNT_INVALID")
                formed = tuple(build_receiving_formed_fixing_plate_skins(
                    snapshot, entry.ear_id,
                ) for entry in owners)
                if (len({row.part_id for row in formed}) != len(formed)
                        or {row.base_part_id for row in formed}
                           != {entry.parent_base_id for entry in owners}
                        or any(row.manufacturing_ready or row.weld_contact_verified
                               or not row.source_bend_verified for row in formed)):
                    raise ValueError("EAR_ASSEMBLY_DISPLAY_SOURCE_INCONSISTENT")
                blocker = None
            except (ValueError, TypeError) as exc:
                formed = ()
                blocker = str(exc)
            self._formed_ear_display_cache = (source_key, formed, blocker)
        else:
            formed, blocker = cached[1:]
        self.last_formed_ear_display_blocker = blocker
        # Display-only EAR visibility is independent of Base Plate visibility.
        # Its own show_fixing_plate_mesh switch is applied by the 3D renderer.
        # Never suppress the EAR when a parent plate is hidden: this is also
        # needed to inspect weld contact surfaces with the plate out of view.
        return tuple(formed)

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
        collision_certification_diagnostics=(),
        selected_joint_id=None,
        preserve_endcap_core_origin=False,
        formed_fixing_plate_skins=(),
        show_fixing_plate_mesh=True,
        formed_nfb_pad_skins=(),
        warnings=(),
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
            collision_certification_diagnostics=collision_certification_diagnostics,
            selected_joint_id=selected_joint_id,
            preserve_endcap_core_origin=preserve_endcap_core_origin,
            formed_fixing_plate_skins=formed_fixing_plate_skins,
            show_fixing_plate_mesh=show_fixing_plate_mesh,
            formed_nfb_pad_skins=formed_nfb_pad_skins,
            warnings=warnings,
            render_data_cls=render_data_cls,
        )

    def query_assembly_render_data(self):
        dependencies = self.dependencies
        # Geometry publication is owned by the update scheduler/executor.  A
        # display-only assembly redraw must consume the committed/cache-resolved
        # geometry without forcing a second live-sync publication.
        resolved = dependencies.resolve_geometry()

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
            for part in resolved.parts if part.placement != "standalone"
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
        # Preserve the historical two-value visibility contract. The optional
        # display-only EAR switch is carried separately on the result.
        show_fixing_plate_mesh = bool(getattr(visibility, "show_fixing_plate_mesh", True))
        visible_set = set(visible_part_keys)
        visible_probe_parts = tuple(
            part
            for part in tuple(dependencies.interference_probe_parts() or ())
            if str(getattr(part, "part_key", "")) in visible_set
        )
        cabinet_family = dependencies.cabinet_family()
        # UI-only warning follows canonical #1502 source resolution, which
        # may derive a plate from submitted CSV without legacy manual config.
        source_warning = receiving_base_source_display_warnings(
            snapshot, cabinet_family,
        )
        formed_ear_skins = (
            self._formed_ear_assembly_preview(snapshot, visible_set)
            if cabinet_family == "受電箱" else ()
        )
        formed_pad_skins = (
            self._formed_pad_assembly_preview(snapshot, visible_set, parts)
            if cabinet_family == "受電箱" else ()
        )
        visible_warnings = tuple(source_warning) + (
            self._ear_display_warnings() if cabinet_family == "受電箱" else ()
        ) + (
            self._pad_display_warnings() if cabinet_family == "受電箱" else ()
        )
        return self.make_assembly_scene_render_data(
            assembly_parts=parts,
            visible_part_keys=visible_part_keys,
            visible_box_body_piece_keys=visible_box_body_piece_keys,
            show_interference=bool(dependencies.show_interference()),
            ignore_fixed_corner_relief=False,
            interference_probe_parts=visible_probe_parts,
            joint_diagnostics=(),
            collision_certification_diagnostics=tuple(
                getattr(resolved, "diagnostics", ()) or ()
            ),
            selected_joint_id=None,
            preserve_endcap_core_origin=(cabinet_family == "受電箱"),
            warnings=visible_warnings,
            formed_fixing_plate_skins=formed_ear_skins,
            show_fixing_plate_mesh=show_fixing_plate_mesh,
            formed_nfb_pad_skins=formed_pad_skins,
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
                # Assembly must use the canonical cabinet's W/H/D, never
                # the previously selected single Door's W/H (2D tuple).
                # Passing dimensions(None) silently reused active_part_key,
                # then true-world Box Body mesh crashed on return to Assembly.
                finished_dimensions=dimensions("box_body"),
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
            thickness=(
                float(render_data.metadata["thickness"])
                if active_part.startswith("base_plate:fixing_plate:")
                and isinstance(getattr(render_data, "metadata", None), dict)
                and "thickness" in render_data.metadata
                else thickness
            ),
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
