# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Final Scene renderer/runtime owner extracted in Phase 4 T6.

Owns Matplotlib renderer mutation and mutable 3D runtime state only.
It consumes immutable FinalSceneViewRequest plus pure projection helpers.
"""
from __future__ import annotations

import matplotlib.projections as _matplotlib_projections  # noqa: F401

from typing import Callable

from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from whd_theme import WHD_THEME, WHD_SEMANTIC_COLORS, apply_mpl_dark_theme
from phase6_final_scene_contracts import (
    AssemblyScenePart,
    AssemblySceneRenderData,
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
    _phase6_assembly_physical_dimension_lines,
    _phase6_assembly_part_presentation,
    _phase6_box_body_structure_meshes,
    _phase6_box_body_true_world_piece_meshes,
    format_operator_info_text,
    _phase6_place_assembly_triangles,
)


from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin
from phase6_final_scene_mesh_display import gridless_mesh_collection


class Phase6FinalSceneRenderer(Phase6FinalSceneRenderHelpersMixin):
    """Deep 3D view module for one authoritative manufacturing FinalScene."""

    _COLORS = {
        "box_body": ("#3b82f6", "#1e40af"),
        "head": ("#10b981", "#047857"),
        "tail": ("#0ea5e9", "#0369a1"),
        "door": ("#8b5cf6", "#5b21b6"),
        "base_plate": ("#f59e0b", "#92400e"),
        "indicator_box": ("#14b8a6", "#0f766e"),
        "indicator_door": ("#ec4899", "#9d174d"),
    }

    def __init__(
        self,
        renderer,
        *,
        number_text: Callable[[object], str] | None = None,
        error_reporter: Callable[[BaseException], object] | None = None,
    ):
        self.renderer = renderer
        self._number_text = number_text or _default_number_text
        self._error_reporter = error_reporter
        self.last_cutting_mesh = []
        self.last_cutting_material = None
        self.cutting_mesh_error = None
        self.zoom_scale = 1.0
        self.view_initialized = False
        self.base_renderer_render = None
        self.scroll_cid = None
        self.last_interference_diagnostic = None
        self.last_all_parts_collision_audit = None
        self._all_parts_collision_cache = None
        self.last_formed_ear_display_ids = ()
        self.last_receiving_ear_marking_segments = ()
        # Artist -> authoritative physical Part ID, populated ONLY from
        # rendered, visible FinalScene material. No mesh is rebuilt for picks.
        self._hole_pick_artists = []
        self._hole_double_click_handler = None
        self._hole_double_click_cid = None

    def set_hole_double_click_handler(self, handler):
        """Connect the original Hole Editor route to visible 3D sheet skins."""
        if handler is not None and not callable(handler):
            raise TypeError("3D Hole Editor callback must be callable")
        self._hole_double_click_handler = handler
        if self._hole_double_click_cid is not None:
            return
        canvas = getattr(self.renderer, "canvas", None)
        if canvas is not None and callable(getattr(canvas, "mpl_connect", None)):
            self._hole_double_click_cid = canvas.mpl_connect(
                "button_press_event", self.on_hole_mesh_double_click,
            )

    def on_hole_mesh_double_click(self, event):
        """Resolve an actual rendered mesh hit; never guess the selected part.

        Matplotlib projects Poly3DCollections into their final 2D visible
        paths before hit-testing. Its draw-time zorder selects the nearest
        visible surface when more than one projected sheet overlaps.
        """
        if (not getattr(event, "dblclick", False)
                or getattr(event, "button", None) != 1
                or getattr(event, "inaxes", None) is not self.renderer.ax3d
                or not callable(self._hole_double_click_handler)):
            return None
        hits = []
        for index, (artist, part_key) in enumerate(self._hole_pick_artists):
            if not artist.get_visible() or artist.axes is not self.renderer.ax3d:
                continue
            contains, _ = artist.contains(event)
            if contains:
                hits.append((artist.get_zorder(), index, part_key))
        if not hits:
            return None
        part_key = max(hits)[2]
        self._hole_double_click_handler(part_key)
        return part_key

    def render(self, request: FinalSceneViewRequest | None):
        # Never keep the pick IDs from a prior rendered Bay / visibility state.
        self._hole_pick_artists = []
        # Redraw/visibility changes must not reuse stale contact outlines.
        self.last_receiving_ear_marking_segments = ()
        if request is None:
            self.last_cutting_mesh = []
            self.last_cutting_material = None
            return []
        render_data = request.render_data
        assembly_parts = tuple(getattr(render_data, "assembly_parts", ()) or ())
        visible_raw = getattr(render_data, "visible_part_keys", None)
        visible_part_keys = (
            None if visible_raw is None
            else frozenset(str(key) for key in tuple(visible_raw or ()))
        )
        visible_piece_raw = getattr(render_data, "visible_box_body_piece_keys", None)
        visible_box_body_piece_keys = (
            None if visible_piece_raw is None
            else frozenset(str(key) for key in tuple(visible_piece_raw or ()))
        )
        if assembly_parts:
            self._remove_original_bend_surfaces()
            for line in list(getattr(self.renderer.ax3d, "lines", ())):
                try:
                    line.remove()
                except Exception:
                    pass
            triangles = []
            materials = []
            box_body_piece_dimension_lines = []
            physical_dimension_lines = []
            box_body_world = None
            box_body_collision_mesh = None
            interference_targets = []
            interference_points = []
            interference_segments = []
            interference_pairs = 0
            self.last_interference_diagnostic = None
            self.last_all_parts_collision_audit = None
            ax = self.renderer.ax3d
            # Manufacturing-model preview: axes/grid are visual noise, not measurements.
            # Keep physical dimensions as explicit part labels instead.
            grid = getattr(ax, "grid", None)
            if callable(grid):
                grid(False)
            hide_axes = getattr(ax, "set_axis_off", None)
            if callable(hide_axes):
                hide_axes()
            divider_in_view = any(
                str(getattr(p, "part_key", "") or "").startswith("box_body:divider:")
                and (visible_part_keys is None or str(p.part_key) in visible_part_keys)
                for p in assembly_parts
            )
            probe_parts = {
                str(getattr(item, "part_key", "")): item
                for item in tuple(getattr(render_data, "interference_probe_parts", ()) or ())
            }
            for part in assembly_parts:
                part_key = str(getattr(part, "part_key", ""))
                part_visible = visible_part_keys is None or part_key in visible_part_keys
                part_data = part.render_data
                if part_visible:
                    physical_dimension_lines.extend(
                        _phase6_assembly_physical_dimension_lines(part, thickness=request.thickness)
                    )
                diagnostic_relief_delta = None
                physical_piece_world = ()
                if getattr(part_data, "pieces", None):
                    piece_meshes = _phase6_box_body_structure_meshes(part_data, thickness=request.thickness)
                    physical_piece_world = _phase6_box_body_true_world_piece_meshes(
                        part, dimensions=request.finished_dimensions,
                        thickness=request.thickness,
                    )
                    local = [tri for _piece, piece_tris in piece_meshes for tri in piece_tris]
                    part_material = tuple(piece.render_data.material for piece in part_data.pieces)
                    if part_visible:
                        box_body_piece_dimension_lines.extend(_phase6_box_body_piece_dimension_lines(part_data))
                else:
                    part_material = part_data.material
                    fold_material = part_material
                    if (
                        bool(getattr(render_data, "ignore_fixed_corner_relief", False))
                        and str(getattr(part, "part_key", "")) in {"head", "tail"}
                    ):
                        from ae_engine.assembly_geometry import (
                            restore_unrelieved_endcap_material,
                            restored_endcap_relief_delta,
                        )
                        fold_material = restore_unrelieved_endcap_material(part_material)
                        diagnostic_relief_delta = restored_endcap_relief_delta(part_material)
                    local = _phase6_folded_mesh_from_polygon(
                        fold_material,
                        tuple(dict(seg) for seg in part.x_profile),
                        tuple(dict(seg) for seg in part.y_profile),
                        fold_guides=tuple(getattr(part_data, "fold_guides", ()) or ()),
                    )
                placement = str(getattr(part, "placement", "offset") or "offset")
                offset = getattr(part, "offset", (0.0, 0.0, 0.0))
                formed_surface_for_edges = None
                if placement in {"top", "head", "bottom", "tail"} and box_body_world:
                    from ae_engine.assembly_geometry import (
                        place_endcap_against_box_body,
                        thicken_triangle_surface,
                    )
                    # EndCaps are physical sheet, not a zero-thickness mid-surface.
                    # Shift the semantic mid-plane outward by T/2 so the inside
                    # skin mates the Box Body, then build both formed skins +
                    # boundary/fold walls from the shared folded surface.
                    mate_kwargs = {"sheet_thickness": request.thickness}
                    if bool(getattr(render_data, "preserve_endcap_core_origin", False)):
                        mate_kwargs["preserve_core_origin"] = True
                    placed_surface = place_endcap_against_box_body(
                        local, placement, box_body_world, offset, **mate_kwargs
                    )
                    formed_surface_for_edges = placed_surface
                    placed = thicken_triangle_surface(
                        placed_surface, request.thickness
                    )
                else:
                    placed = _phase6_place_assembly_triangles(
                        local, placement, request.finished_dimensions, offset
                    )
                if not placed:
                    continue
                if part_key.startswith("box_body:divider:"):
                    # The certified FW contact uses physical sheet skins.
                    # Display that same T-thick solid rather than the
                    # zero-thickness mid-surface (front is T/2 too far back).
                    # No geometry or manufacturing input is modified.
                    from ae_engine.assembly_geometry import thicken_triangle_surface
                    placed = thicken_triangle_surface(placed, request.thickness)
                placed_piece_meshes = ()
                if getattr(part_data, "pieces", None):
                    if physical_piece_world:
                        # Actual true-thickness piece skins; never re-center.
                        placed_piece_meshes = physical_piece_world
                    else:
                        rows = []
                        cursor = 0
                        for piece, piece_tris in piece_meshes:
                            count = len(piece_tris)
                            rows.append((piece, tuple(placed[cursor:cursor + count])))
                            cursor += count
                        placed_piece_meshes = tuple(rows)
                if part_key == "box_body":
                    box_body_world = tuple(placed)
                    if part_visible:
                        if getattr(part_data, "pieces", None) and not physical_piece_world:
                            self._draw_box_body_structure_bends(
                                part_data, thickness=request.thickness, local_reference=local,
                                placement=placement, dimensions=request.finished_dimensions, offset=offset,
                                visible_piece_keys=visible_box_body_piece_keys,
                            )
                        else:
                            self._draw_assembly_box_body_bends(
                                part_data.scene,
                                tuple(dict(seg) for seg in part.x_profile),
                                tuple(dict(seg) for seg in part.y_profile),
                                tuple(getattr(part_data, "fold_guides", ()) or ()),
                                local, placement, request.finished_dimensions, offset,
                            )
                    if bool(getattr(render_data, "show_interference", False)):
                        from ae_engine.assembly_geometry import thicken_triangle_surface
                        if getattr(part_data, "pieces", None):
                            collision = []
                            for _piece, piece_tris in placed_piece_meshes:
                                # Already true-thickness world meshes; applying
                                # thicken again creates false collision volumes.
                                collision.extend(
                                    piece_tris if physical_piece_world else
                                    thicken_triangle_surface(piece_tris, request.thickness)
                                )
                            box_body_collision_mesh = tuple(collision)
                        else:
                            box_body_collision_mesh = thicken_triangle_surface(
                                box_body_world, request.thickness
                            )
                    if getattr(part_data, "pieces", None):
                        if part_visible:
                            face, edge = self._COLORS.get(str(part.part_key), ("#64748b", "#334155"))
                            visible_rows = []
                            for piece, piece_placed in placed_piece_meshes:
                                piece_key = f"box_body:{str(getattr(piece, 'role', '') or '').strip()}"
                                if visible_box_body_piece_keys is not None and piece_key not in visible_box_body_piece_keys:
                                    continue
                                visible_rows.append(piece)
                                if not piece_placed:
                                    continue
                                poly = gridless_mesh_collection(
                                    piece_placed, facecolor=face,
                                    opacity=(min(0.17, float(request.alpha_bend))
                                             if divider_in_view else float(request.alpha_bend)),
                                )
                                ax.add_collection3d(poly)
                                # A box body is several distinct editable
                                # physical sheets, not one arbitrary "box_body".
                                self._hole_pick_artists.append((poly, piece_key))
                                piece_role = str(getattr(piece, "role", "") or "").strip()
                                # Mesh feature extraction can turn individually
                                # triangulated/nonplanar skins into a visible grid.
                                # A back panel remains an actual CUTTING solid, but
                                # has no additional mesh-derived wire overlay.
                                if piece_role != "back":
                                    self._draw_joint_marking_world_rows(piece.render_data)
                                triangles.extend(piece_placed)
                            if visible_rows:
                                materials.append(tuple(piece.render_data.material for piece in visible_rows))
                        continue
                    if not part_visible:
                        continue
                elif not part_visible:
                    continue
                elif (
                    bool(getattr(render_data, "show_interference", False))
                    and box_body_collision_mesh
                    and part_key in {"head", "tail"}
                ):
                    from ae_engine.assembly_geometry import (
                        detect_world_mesh_surface_interference,
                        place_endcap_against_box_body,
                        thicken_triangle_surface,
                    )
                    # Collision diagnostics must use the pre-solve EndCap probe,
                    # never the already-relieved display material.  We still probe
                    # only the fixed-relief delta so intended mating seams on the full
                    # sheet are not reported as broad false positives.
                    collision_target = ()
                    probe_part = probe_parts.get(part_key)
                    probe_data = getattr(probe_part, "render_data", None) if probe_part is not None else None
                    if probe_data is not None and getattr(probe_data, "material", None) is not None:
                        from ae_engine.assembly_geometry import restored_endcap_relief_delta
                        delta_material = restored_endcap_relief_delta(probe_data.material)
                        probe_x = tuple(dict(seg) for seg in getattr(probe_part, "x_profile", ()) or ())
                        probe_y = tuple(dict(seg) for seg in getattr(probe_part, "y_profile", ()) or ())
                        probe_guides = tuple(getattr(probe_data, "fold_guides", ()) or ())
                    elif bool(getattr(render_data, "ignore_fixed_corner_relief", False)):
                        delta_material = diagnostic_relief_delta
                        probe_x = tuple(dict(seg) for seg in part.x_profile)
                        probe_y = tuple(dict(seg) for seg in part.y_profile)
                        probe_guides = tuple(getattr(part_data, "fold_guides", ()) or ())
                    else:
                        delta_material = None
                        probe_x = probe_y = probe_guides = ()
                    if delta_material is not None and not getattr(delta_material, "is_empty", True):
                        delta_local = _phase6_folded_mesh_from_polygon(
                            delta_material, probe_x, probe_y, fold_guides=probe_guides,
                        )
                        probe_mate_kwargs = {"sheet_thickness": request.thickness}
                        if bool(getattr(render_data, "preserve_endcap_core_origin", False)):
                            probe_mate_kwargs["preserve_core_origin"] = True
                        delta_surface = place_endcap_against_box_body(
                            delta_local, placement, box_body_world, offset, **probe_mate_kwargs
                        )
                        collision_target = thicken_triangle_surface(
                            delta_surface, request.thickness
                        )
                    diagnostic = detect_world_mesh_surface_interference(
                        box_body_collision_mesh, collision_target
                    ) if collision_target else None
                    if diagnostic is not None and diagnostic.has_interference:
                        interference_targets.extend(diagnostic.target_triangles)
                        interference_points.extend(diagnostic.intersection_points)
                        interference_segments.extend(diagnostic.intersection_segments)
                        interference_pairs += int(diagnostic.pair_count)
                self._draw_joint_marking_world_rows(part_data)
                self._draw_assembly_scene_markings(
                    part_data.scene,
                    tuple(dict(seg) for seg in part.x_profile),
                    tuple(dict(seg) for seg in part.y_profile),
                    tuple(getattr(part_data, "fold_guides", ()) or ()),
                    local,
                    placement,
                    request.finished_dimensions,
                    offset,
                    joint_marking_signatures=self._joint_marking_flat_signatures(part_data),
                )
                face, edge = self._COLORS.get(str(part.part_key), ("#64748b", "#334155"))
                opacity = float(request.alpha_bend)
                # Outer Door is intentionally readable even when the shared
                # sheet transparency is lowered to inspect the cabinet internals.
                is_outer_door = (
                    part_key == "door" or
                    (part_key.startswith("door_c") and "_r" in part_key)
                )
                is_inner_panel = (
                    part_key.startswith("inner_door:") and part_key.endswith(":panel")
                )
                if is_outer_door or is_inner_panel:
                    opacity = 1.0
                divider_presentation = _phase6_assembly_part_presentation(part_key, opacity)
                if divider_presentation is not None:
                    face, edge, opacity = divider_presentation
                poly = gridless_mesh_collection(
                    placed, facecolor=face, opacity=opacity,
                )
                ax.add_collection3d(poly)
                self._hole_pick_artists.append((poly, part_key))
                if is_outer_door or is_inner_panel:
                    # CUTTING holes must be real material interiors, not
                    # tessellation outlines. Folded-door crease/BEND geometry
                    # must likewise remain visible after the opaque door skin
                    # is drawn; other parts intentionally keep smooth skins.
                    self._draw_cutting_hole_rims(
                        part_material, part.x_profile, part.y_profile,
                        tuple(getattr(part_data, "fold_guides", ()) or ()),
                        local_reference=local, placement=placement,
                        dimensions=request.finished_dimensions, offset=offset,
                    )
                    self._draw_assembly_box_body_bends(
                        part_data.scene,
                        tuple(dict(seg) for seg in part.x_profile),
                        tuple(dict(seg) for seg in part.y_profile),
                        tuple(getattr(part_data, "fold_guides", ()) or ()),
                        local, placement, request.finished_dimensions, offset,
                    )
                if formed_surface_for_edges is not None:
                    # Only source CUTTING inner rings get a drawn line.
                    # Never turn triangulation/normal changes into an overlay.
                    self._draw_endcap_cutting_hole_rims(
                        part_material, part.x_profile, part.y_profile,
                        tuple(getattr(part_data, "fold_guides", ()) or ()),
                        local, formed_surface_for_edges, placement, edge,
                    )
                triangles.extend(placed)
                materials.append(part_material)
            # #1503: show the already source-certified T2/BEND23 folded
            # fixing plates in the assembled 3D view. The geometry was built
            # upstream from physical FinalScene and passed as DISPLAY ONLY,
            # not added to the manufacturing part list/BOM or DXF export.
            # No triangle-grid edges or invented weld lines.
            self.last_formed_ear_display_ids = ()
            visible_ears = []
            for formed in tuple(getattr(render_data, "formed_fixing_plate_skins", ()) or ()):
                # Hide only EAR physical surfaces. Source-backed SIDE MARKING
                # below must remain visible while the owning side is visible.
                if not bool(getattr(render_data, "show_fixing_plate_mesh", True)):
                    continue
                if (not getattr(formed, "source_bend_verified", False)
                        or not getattr(formed, "actual_signed_forming_constructed", False)
                        or getattr(formed, "manufacturing_ready", True)
                        or getattr(formed, "weld_contact_verified", True)):
                    raise ValueError("EAR_3D_SOURCE_OR_MANUFACTURING_GATE_FAILED")
                skin_tris = tuple(
                    tuple(tuple(float(v) for v in point) for point in face.world)
                    for face in tuple(formed.mapped_world_skins or ())
                )
                if not skin_tris:
                    raise ValueError("EAR_3D_FORMED_SKIN_EMPTY")
                poly = gridless_mesh_collection(
                    skin_tris, facecolor="#f97316", opacity=0.92,
                )
                ax.add_collection3d(poly)
                triangles.extend(skin_tris)
                visible_ears.append(str(formed.part_id))
            self.last_formed_ear_display_ids = tuple(visible_ears)
            self.last_formed_pad_display_ids = ()
            visible_pads = []
            for pad in tuple(getattr(render_data, "formed_nfb_pad_skins", ()) or ()):
                if (pad.manufacturing_ready or pad.assembly_contact_certified
                        or not pad.source_flat_and_bend_verified
                        or not pad.actual_base_squares_present):
                    raise ValueError("PAD_3D_PREVIEW_SOURCE_OR_MFG_GATE_INVALID")
                triangles_pad = tuple(pad.world_triangles or ())
                if not triangles_pad:
                    raise ValueError("PAD_3D_PREVIEW_EMPTY_MESH")
                pad_artist = gridless_mesh_collection(
                    triangles_pad, facecolor="#a78bfa", opacity=0.92,
                )
                ax.add_collection3d(pad_artist)
                triangles.extend(triangles_pad)
                visible_pads.append(str(pad.part_id))
            self.last_formed_pad_display_ids = tuple(visible_pads)
            # EAR contact lines are MARKING on the mother SIDE plate, not
            # a mesh-grid overlay or an EAR CUTTING/BEND feature.  Only draw
            # when the physical box body and its actual side are visible.
            if visible_part_keys is None or "box_body" in visible_part_keys:
                self.last_receiving_ear_marking_segments = (
                    self._draw_receiving_ear_side_markings(
                        tuple(getattr(render_data, "formed_fixing_plate_skins", ()) or ()),
                        visible_side_piece_keys=visible_box_body_piece_keys,
                    )
                )
            # On-demand WHOLE ASSEMBLY physical audit, independent of legacy
            # EndCap restored-delta visualization. Include all side pieces,
            # divider, inner-door frames, head/tail and future generated parts.
            # Explicit toggle only: do not make ordinary navigation slower.
            unresolved_segments = ()
            if (
                bool(getattr(render_data, "show_interference", False))
                and request.finished_dimensions
                and any(
                    str(p.part_key) == "box_body"
                    and tuple(getattr(p.render_data, "pieces", ()) or ())
                    for p in assembly_parts
                )
            ):
                from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
                from ae_engine.assembly_all_parts_collision import (
                    audit_all_physical_part_pairs, collision_part_display_name,
                )
                # A renderer instance persists across 3D redraws: reuse a verified
                # result for the SAME immutable scene objects and user controls.
                scene_key = (
                    tuple((str(p.part_key), id(p), id(p.render_data)) for p in assembly_parts),
                    tuple(float(v) for v in request.finished_dimensions),
                    float(request.thickness),
                    visible_part_keys, visible_box_body_piece_keys,
                )
                if self._all_parts_collision_cache is not None and (
                    self._all_parts_collision_cache[0] == scene_key
                ):
                    audit = self._all_parts_collision_cache[1]
                else:
                    physical = _phase6_build_joint_world_geometry(
                        assembly_parts, request.finished_dimensions, request.thickness,
                    )
                    world_parts = physical["world_triangles_by_part"]
                    selected = (
                        {key for key in world_parts if key != "box_body"}
                        if visible_part_keys is None else
                        {key for key in world_parts if (
                            (key.startswith("box_body:") and "box_body" in visible_part_keys)
                            or key in visible_part_keys
                        )}
                    )
                    if visible_box_body_piece_keys is not None:
                        selected = {
                            key for key in selected
                            if not key.startswith("box_body:")
                            or key.startswith("box_body:divider:")
                            or key in visible_box_body_piece_keys
                        }
                    audit = audit_all_physical_part_pairs(
                        world_parts, visible_part_keys=selected,
                        certified_relief_diagnostics=tuple(
                            getattr(render_data, "collision_certification_diagnostics", ()) or ()
                        ),
                    )
                    self._all_parts_collision_cache = (scene_key, audit)
                self.last_all_parts_collision_audit = audit
                unresolved_segments = tuple(
                    segment for row in audit.unresolved for segment in row.segments
                )
                if unresolved_segments:
                    from mpl_toolkits.mplot3d.art3d import Line3DCollection
                    ax.add_collection3d(Line3DCollection(
                        unresolved_segments, colors="#ff9900",
                        linewidths=3.6, alpha=0.95,
                    ))
            if interference_segments:
                from mpl_toolkits.mplot3d.art3d import Line3DCollection
                from ae_engine.assembly_geometry import MeshInterferenceDiagnostic
                if interference_targets:
                    ax.add_collection3d(gridless_mesh_collection(
                        interference_targets, facecolor="#eab308", opacity=0.42,
                    ))
                ax.add_collection3d(Line3DCollection(
                    interference_segments, colors="#eab308", linewidths=2.5,
                    linestyles="solid", alpha=0.95,
                ))
                self.last_interference_diagnostic = MeshInterferenceDiagnostic(
                    tuple(interference_targets), tuple(interference_points),
                    interference_pairs, tuple(interference_segments)
                )
            else:
                from ae_engine.assembly_geometry import MeshInterferenceDiagnostic
                self.last_interference_diagnostic = MeshInterferenceDiagnostic((), (), 0, ())
            # Preserve the legacy RED certified-interference diagnostic.
            # Amber unverified crossings are a separate audit, not a forged
            # positive-volume collision result.
            self._draw_joint_diagnostic_overlays(render_data)
            if not triangles:
                raise ValueError("3D assembly CUTTING mesh is empty")
            vertices = [point for tri in triangles for point in tri]
            xlim, ylim, zlim = _phase6_fitted_limits_from_vertices(vertices)
            ax.set_xlim3d(*xlim); ax.set_ylim3d(*ylim); ax.set_zlim3d(*zlim)
            spans = [max(1e-9, lim[1] - lim[0]) for lim in (xlim, ylim, zlim)]
            try:
                ax.set_box_aspect(spans, zoom=1.05)
            except TypeError:
                ax.set_box_aspect(spans)
            if request.finished_dimensions and callable(getattr(ax, "text2D", None)):
                text = " × ".join(self._number_text(v) for v in request.finished_dimensions)
                warnings = tuple(getattr(render_data, "warnings", ()) or ())
                warning_text = "\n⚠ " + "；".join(str(getattr(w, "message", w)) for w in warnings) if warnings else ""
                diagnostic = self.last_interference_diagnostic
                collision_text = ""
                if bool(getattr(render_data, "show_interference", False)):
                    count = len(tuple(getattr(diagnostic, "intersection_segments", ()) or ()))
                    # PR #1756: RED is a pre-cut EndCap probe only, NOT proof
                    # of a finished part collision. Keep its wording intact.
                    collision_text = (
                        f"\n加工前截角交集：{count} 段（非成品碰撞）"
                        if count else
                        "\n加工前截角交集：無；成品碰撞請依3D驗證狀態判斷"
                    )
                    # PR #1757: independent FINAL physical-pair crossings.
                    # Orange is unresolved, not a manufactured penetration
                    # certificate; verified C relief may legitimately touch.
                    audit = self.last_all_parts_collision_audit
                    if audit is not None:
                        if audit.unresolved:
                            collision_text += (
                                f"\n⚠ 全板件配對 {audit.evaluated_pair_count} 組："
                                f"{len(audit.unresolved)} 組有未證實合法交線（橘色），不可判定為零碰撞"
                            )
                            collision_text += "".join(
                                f"\n  {collision_part_display_name(row.left)} ↔ "
                                f"{collision_part_display_name(row.right)}："
                                f"{row.pair_count} 組交線；"
                                f"X{row.region_xyz[0]} Y{row.region_xyz[1]} Z{row.region_xyz[2]} mm"
                                for row in audit.unresolved[:5]
                            )
                        else:
                            collision_text += (
                                f"\n全板件表面配對 {audit.evaluated_pair_count} 組："
                                f"無待確認交線；非實體體積零穿透證明"
                            )
                ax.text2D(
                    0.015, 0.985,
                    f"組合體 3D：W × H × D = {text} mm{warning_text}{collision_text}"
                    + (("\n" + "\n".join(box_body_piece_dimension_lines)) if box_body_piece_dimension_lines else "")
                    + (("\n" + "\n".join(physical_dimension_lines)) if physical_dimension_lines else "")
                    + (f"\n{request.unfolded_blank_text}" if request.unfolded_blank_text else ""),
                    transform=ax.transAxes, ha="left", va="top", color=WHD_THEME["text"],
                )
            self.last_cutting_mesh = triangles
            self.last_cutting_material = tuple(materials)
            return triangles
        if getattr(render_data, "pieces", None):
            meshes = _phase6_box_body_structure_meshes(render_data, thickness=request.thickness)
            triangles = [tri for _piece, piece_tris in meshes for tri in piece_tris]
            if not triangles:
                raise ValueError("3D multi-piece CUTTING mesh is empty")
            self._remove_original_bend_surfaces()
            for line in list(getattr(self.renderer.ax3d, "lines", ())):
                try:
                    line.remove()
                except Exception:
                    pass
            face, edge = self._COLORS.get(str(request.part_key), ("#64748b", "#334155"))
            for _piece, piece_tris in meshes:
                poly = gridless_mesh_collection(
                    piece_tris, facecolor=face, opacity=float(request.alpha_bend),
                )
                self.renderer.ax3d.add_collection3d(poly)
                role = str(getattr(_piece, "role", "") or "").strip()
                if role:
                    self._hole_pick_artists.append((poly, f"box_body:{role}"))
                # All Box Body pieces use smooth material skins.
                # Physical BEND comes from the manufacturing scene below,
                # never from mesh/normal-derived feature segments.
            self._draw_box_body_structure_bends(
                render_data, thickness=request.thickness
            )
            vertices = [point for tri in triangles for point in tri]
            xlim, ylim, zlim = _phase6_fitted_limits_from_vertices(vertices)
            ax = self.renderer.ax3d
            ax.set_xlim3d(*xlim); ax.set_ylim3d(*ylim); ax.set_zlim3d(*zlim)
            spans = [max(1e-9, lim[1] - lim[0]) for lim in (xlim, ylim, zlim)]
            try:
                ax.set_box_aspect(spans, zoom=1.05)
            except TypeError:
                ax.set_box_aspect(spans)
            dims = request.finished_dimensions
            if dims and callable(getattr(ax, "text2D", None)):
                text = " × ".join(self._number_text(v) for v in dims)
                warnings = tuple(getattr(render_data, "warnings", ()) or ())
                warning_text = "\n⚠ " + "；".join(str(getattr(w, "message", w)) for w in warnings) if warnings else ""
                corner_text = f"\n{request.corner_dimension_text}" if request.corner_dimension_text else ""
                piece_text = "\n".join(_phase6_box_body_piece_dimension_lines(render_data))
                ax.text2D(
                    0.015, 0.985,
                    f"折後包外：{text} mm{warning_text}{corner_text}" + (f"\n{piece_text}" if piece_text else ""),
                    transform=ax.transAxes, ha="left", va="top", color=WHD_THEME["text"]
                )
            self.last_cutting_mesh = triangles
            self.last_cutting_material = tuple(piece.render_data.material for piece in render_data.pieces)
            return triangles

        scene = render_data.scene
        material = render_data.material
        fold_guides = tuple(getattr(render_data, "fold_guides", ()) or ())
        part_key = str(request.part_key)
        fixed_plate_display = False
        x_profile, y_profile = request.x_profile, request.y_profile
        if (part_key.startswith("base_plate:fixing_plate:")
                and (getattr(render_data, "metadata", None) or {}).get("source_profile") == "large"):
            # #1503: the independent 3D tab previously reused blank editor
            # profiles, hence rendered the genuine BEND23 source as FLAT.
            # Consume the SAME source-verified signed +90 fold as assembly.
            # Only the on-screen mesh uses the T2 MID-skin hinge at y=22.
            # The original PartRenderData / CUTTING / DXF BEND at y=23 is
            # unchanged; do not introduce any bend compensation.
            from ae_engine.receiving_fixed_plate_formed_skins import (
                verified_receiving_fixing_plate_local_fold,
            )
            from ae_engine.assembly_geometry import (
                folded_mesh_with_flat_uv_from_polygon,
                thicken_triangle_surface,
            )
            hinge_y, x_profile, y_profile, physical_guides = (
                verified_receiving_fixing_plate_local_fold(render_data)
            )
            mapped = folded_mesh_with_flat_uv_from_polygon(
                material, x_profile, y_profile, fold_guides=physical_guides,
            )
            triangles = thicken_triangle_surface(
                tuple(face.local for face in mapped),
                float(render_data.metadata["thickness"]),
            )
            fold_guides = physical_guides
            fixed_plate_display = True
        if part_key == "box_body:left_side":
            # This independent 3D input sink must depict the FINISHED solid,
            # not a zero-thickness material midplane.  Use the same pure
            # formed/outside correction as the assembly collision mesh,
            # but fold the ACTIVE operator profile (never copy world assembly).
            from ae_engine.assembly_geometry import (
                folded_mesh_with_flat_uv_from_polygon, thicken_triangle_surface,
            )
            from ae_engine.assembly_geometry_folded_mesh import (
                fit_receiving_left_zl1_formed_outside,
            )
            mapped = folded_mesh_with_flat_uv_from_polygon(
                material, request.x_profile, request.y_profile,
                fold_guides=fold_guides,
            )
            formed = fit_receiving_left_zl1_formed_outside(
                request.x_profile, mapped,
                tuple(item.local for item in mapped),
                thickness=request.thickness, axis=2,
            )
            triangles = thicken_triangle_surface(formed, request.thickness)
        elif not fixed_plate_display:
            triangles = _phase6_folded_mesh_from_polygon(
                material, request.x_profile, request.y_profile,
                fold_guides=fold_guides,
            )
        if not triangles:
            raise ValueError("3D CUTTING mesh is empty")
        self._remove_original_bend_surfaces()
        for line in list(getattr(self.renderer.ax3d, "lines", ())):
            try:
                line.remove()
            except Exception:
                pass
        face, edge = self._COLORS.get(str(request.part_key), ("#64748b", "#334155"))
        part_key = str(request.part_key)
        is_door = (
            part_key == "door"
            or (part_key.startswith("door_c") and "_r" in part_key)
            or (part_key.startswith("inner_door:") and part_key.endswith(":panel"))
        )
        poly = gridless_mesh_collection(
            triangles, facecolor=face,
            opacity=1.0 if is_door else float(request.alpha_bend),
        )
        self.renderer.ax3d.add_collection3d(poly)
        self._hole_pick_artists.append((poly, part_key))
        if is_door:
            self._draw_cutting_hole_rims(
                material, request.x_profile, request.y_profile, fold_guides,
            )
        # 3D fixed-plate crease uses the signed MID-skin hinge. The DXF BEND
        # is deliberately 1 mm away at y=23 and must remain source-exact
        # in 2D/manufacturing, rather than be drawn as a false 3D hinge.
        if fixed_plate_display:
            p = self._map_xy(0., hinge_y, x_profile, y_profile, fold_guides)
            q = self._map_xy(float(render_data.metadata["source_flat_dimensions"][0]),
                             hinge_y, x_profile, y_profile, fold_guides)
            self.renderer.ax3d.plot(
                [p[0], q[0]], [p[1], q[1]], [p[2], q[2]],
                color="#2563eb", linewidth=1.15, alpha=0.95,
            )
        else:
            self._draw_scene_bends(scene, request.x_profile, request.y_profile, fold_guides=fold_guides)
        self._draw_scene_markings(scene, x_profile, y_profile, fold_guides=fold_guides)
        self._draw_operator_dimensions(request, triangles)
        vertices = [point for tri in triangles for point in tri]
        xlim, ylim, zlim = _phase6_fitted_limits_from_vertices(vertices)
        ax = self.renderer.ax3d
        ax.set_xlim3d(*xlim)
        ax.set_ylim3d(*ylim)
        ax.set_zlim3d(*zlim)
        spans = [max(1e-9, lim[1] - lim[0]) for lim in (xlim, ylim, zlim)]
        try:
            ax.set_box_aspect(spans, zoom=1.05)
        except TypeError:
            ax.set_box_aspect(spans)
        self.last_cutting_mesh = triangles
        self.last_cutting_material = material
        return triangles

    def configure_3d_only_figure(self):
        _configure_3d_only_figure(self.renderer)

    def scale_current_3d_limits(self, ratio):
        _scale_current_3d_limits(self.renderer, ratio)

    def adjust_zoom_scale(self, direction):
        old = float(self.zoom_scale or 1.0)
        if str(direction).lower() == "up":
            new = max(_PHASE6_ZOOM_MIN, old * _PHASE6_ZOOM_STEP)
        elif str(direction).lower() == "down":
            new = min(_PHASE6_ZOOM_MAX, old / _PHASE6_ZOOM_STEP)
        else:
            return old
        self.zoom_scale = new
        return new

    def on_scroll(self, event):
        if getattr(event, "inaxes", None) is not self.renderer.ax3d:
            return
        old = float(self.zoom_scale or 1.0)
        new = self.adjust_zoom_scale(getattr(event, "button", ""))
        if abs(new - old) <= 1e-12:
            return
        self.scale_current_3d_limits(new / old)
        self.renderer.canvas.draw_idle()

    def install(self, request_provider, *, after_render=None):
        self.zoom_scale = 1.0
        self.view_initialized = False
        self.configure_3d_only_figure()
        self.base_renderer_render = self.renderer.render
        # A request provider can enter a nested Tk event loop. The last
        # operator view must own the artists, diagnostics and canvas draw.
        self._view_render_generation = 0

        def render_3d_only():
            self._view_render_generation += 1
            generation = self._view_render_generation
            canvas = self.renderer.canvas
            requested_draw = getattr(canvas, "draw", None)
            ax = self.renderer.ax3d
            try:
                elev, azim = ax.elev, ax.azim
            except AttributeError:
                elev, azim = 30, -45
            ax.clear()
            self._hole_pick_artists = []
            ax2d = getattr(self.renderer, "ax2d", None)
            if ax2d is not None:
                ax2d.clear()
                ax2d.axis("off")
            apply_mpl_dark_theme(getattr(ax, "figure", None), (ax, ax2d))
            self.configure_3d_only_figure()
            try:
                request = request_provider()
                if generation != self._view_render_generation:
                    return None  # Superseded while querying FinalScene.
                self.render(request)
                if generation != self._view_render_generation:
                    return None
                self.cutting_mesh_error = None
            except Exception as exc:
                if generation != self._view_render_generation:
                    return None  # Do not publish an old error on a newer view.
                self.last_cutting_mesh = []
                self.last_cutting_material = None
                self.cutting_mesh_error = str(exc)
                reporter = self._error_reporter
                if callable(reporter):
                    try:
                        reporter(exc)
                    except Exception:
                        # Runtime diagnostics must never replace the render failure.
                        pass
                try:
                    ax.text2D(
                        0.5, 0.5, f"3D Final Part Geometry 載入失敗\n{exc}",
                        transform=ax.transAxes, ha="center", va="center", color=WHD_SEMANTIC_COLORS["error"],
                    )
                except Exception:
                    pass
            if generation != self._view_render_generation:
                return None
            try:
                if self.view_initialized:
                    ax.view_init(elev=elev, azim=azim)
                else:
                    ax.view_init(elev=_PHASE6_DEFAULT_VIEW[0], azim=_PHASE6_DEFAULT_VIEW[1])
                    self.view_initialized = True
            except Exception:
                pass
            scale = float(self.zoom_scale or 1.0)
            if abs(scale - 1.0) > 1e-12 and not self.cutting_mesh_error:
                self.scale_current_3d_limits(scale)
            if callable(after_render):
                after_render()
            if generation != self._view_render_generation:
                return None
            if callable(requested_draw):
                requested_draw()
            return None

        self.renderer.render = render_3d_only
        self.scroll_cid = self.renderer.canvas.mpl_connect("scroll_event", self.on_scroll)
        return self


_PHASE6_DEFAULT_VIEW = (50.0, -90.0)
_PHASE6_ZOOM_MIN = 0.35
_PHASE6_ZOOM_MAX = 3.0
_PHASE6_ZOOM_STEP = 0.85


def _configure_3d_only_figure(renderer):
    """Hide legacy 2D and let 3D use the full rectangular preview viewport."""
    import types

    ax2d = getattr(renderer, "ax2d", None)
    if ax2d is not None:
        ax2d.set_visible(False)
    ax = renderer.ax3d
    if callable(getattr(ax, "set_axis_off", None)):
        ax.set_axis_off()
    if not getattr(ax, "_phase6_rectangular_viewport", False) and callable(getattr(ax, "set_position", None)):
        def apply_rectangular_aspect(axis_self, position=None):
            if position is None:
                position = axis_self.get_position(original=True)
            axis_self._set_position(position, "active")
        ax.apply_aspect = types.MethodType(apply_rectangular_aspect, ax)
        ax._phase6_rectangular_viewport = True
    if callable(getattr(ax, "set_position", None)):
        ax.set_position([0.0, 0.02, 1.0, 0.96])


def _scale_current_3d_limits(renderer, ratio):
    ax = renderer.ax3d
    ratio = float(ratio)
    for getter, setter in (
        (ax.get_xlim3d, ax.set_xlim3d),
        (ax.get_ylim3d, ax.set_ylim3d),
        (ax.get_zlim3d, ax.set_zlim3d),
    ):
        lo, hi = getter()
        center = (lo + hi) / 2.0
        half = max(1e-9, (hi - lo) / 2.0) * ratio
        setter(center - half, center + half)



# Legacy helper compatibility. Production code uses Phase6FinalSceneView directly.


# Compatibility name retained for existing imports/tests. Runtime ownership is
# Phase6FinalSceneRenderer.
Phase6FinalSceneView = Phase6FinalSceneRenderer


__all__ = [
    "Phase6FinalSceneRenderer",
    "Phase6FinalSceneView",
    "AssemblyScenePart",
    "AssemblySceneRenderData",
    "_PHASE6_DEFAULT_VIEW",
    "_PHASE6_ZOOM_MIN",
    "_PHASE6_ZOOM_MAX",
    "_PHASE6_ZOOM_STEP",
    "_configure_3d_only_figure",
    "_scale_current_3d_limits",
]
