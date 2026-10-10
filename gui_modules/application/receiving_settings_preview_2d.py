"""2D orthographic *assembly* view of committed Receiving FinalScene geometry.

The shared formed FinalScene geometry and world placements remain authoritative:
nothing is flattened into individual manufacturing sheet drawings.
"""
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from whd_theme import apply_mpl_dark_theme

_LABELS = {"head": "封頭", "tail": "封尾", "box_body": "箱身", "door": "門",
           "base_plate": "底板", "inner_door": "內門", "indicator_box": "指示燈盒",
           "left_side": "左側板", "right_side": "右側板", "back": "背板",
           "divider": "中隔"}
_COLORS = {"head": "#7db6e8", "tail": "#7db6e8", "box_body": "#b6c9d9",
           "door": "#f7c66f", "inner_door": "#c7a2df", "back": "#88b6b3",
           "left_side": "#b6c9d9", "right_side": "#b6c9d9",
           "divider": "#b7d99a"}


def _role_group(key):
    key = str(key)
    if key.startswith("box_body:"):
        key = key.split(":", 1)[1]
    for role in ("inner_door", "indicator_box", "indicator_door",
                 "base_plate", "door", "left_side", "right_side",
                 "back", "divider"):
        if key.startswith(role):
            return role
    return key


def _assembly_world_meshes(request):
    """Reuse the exact formed-mesh and placement helpers of FinalSceneRenderer.

    Compute once per committed geometry refresh. Hover/selection never remesh.
    The returned meshes are grouped by original assembled part, not by sheet tile.
    """
    from phase6_final_scene_projection import (
        _phase6_folded_mesh_from_polygon, _phase6_box_body_structure_meshes,
        _phase6_place_assembly_triangles,
    )
    from ae_engine.assembly_geometry import (
        place_endcap_against_box_body, thicken_triangle_surface,
    )

    box_body_world = None
    for part in tuple(getattr(request.render_data, "assembly_parts", ()) or ()):
        data = part.render_data
        pieces = tuple(getattr(data, "pieces", ()) or ())
        if pieces:
            meshes = tuple(_phase6_box_body_structure_meshes(
                data, thickness=request.thickness))
            local = [triangle for _piece, mesh in meshes for triangle in mesh]
        else:
            meshes = ()
            local = _phase6_folded_mesh_from_polygon(
                data.material, tuple(dict(x) for x in part.x_profile),
                tuple(dict(y) for y in part.y_profile),
                fold_guides=tuple(getattr(data, "fold_guides", ()) or ()),
            )
        placement = str(getattr(part, "placement", "offset") or "offset")
        offset = getattr(part, "offset", (0, 0, 0))
        if placement in {"top", "head", "bottom", "tail"} and box_body_world:
            kwargs = {"sheet_thickness": request.thickness}
            if getattr(request.render_data, "preserve_endcap_core_origin", False):
                kwargs["preserve_core_origin"] = True
            placed = thicken_triangle_surface(
                place_endcap_against_box_body(
                    local, placement, box_body_world, offset, **kwargs),
                request.thickness,
            )
        else:
            placed = _phase6_place_assembly_triangles(
                local, placement, request.finished_dimensions, offset)
        if str(part.part_key) == "box_body":
            box_body_world = tuple(placed)
        if not placed:
            continue
        if not pieces:
            yield (_role_group(part.part_key), str(part.part_key), tuple(placed))
            continue
        cursor = 0
        for piece, piece_mesh in meshes:
            count = len(piece_mesh)
            world_piece = tuple(placed[cursor:cursor + count])
            cursor += count
            if world_piece:
                role = _role_group(piece.role)
                yield (role, str(piece.key), world_piece)


def _projected_outline(triangles):
    """Orthographic front elevation (world X / height Y), no sheet layout.

    Preserve silhouette, free boundaries and formed creases; omit triangulation
    diagonals shared by coplanar faces. Identical depth projections are deduped.
    """
    edges = defaultdict(list)
    for triangle in triangles:
        if len(triangle) != 3:
            continue
        a, b, c = (tuple(float(n) for n in point) for point in triangle)
        ab = tuple(b[i] - a[i] for i in range(3))
        ac = tuple(c[i] - a[i] for i in range(3))
        normal = (ab[1]*ac[2]-ab[2]*ac[1],
                  ab[2]*ac[0]-ab[0]*ac[2],
                  ab[0]*ac[1]-ab[1]*ac[0])
        size = sqrt(sum(v*v for v in normal))
        if size <= 1e-9:
            continue
        normal = tuple(v / size for v in normal)
        for start, end in ((a, b), (b, c), (c, a)):
            pa, pb = tuple(round(x, 5) for x in start), tuple(round(x, 5) for x in end)
            if pa != pb:
                edges[tuple(sorted((pa, pb)))].append(normal)
    projected = set()
    for (start, end), normals in edges.items():
        if len(normals) > 1 and all(
            abs(sum(normals[0][i]*n[i] for i in range(3))) > .9999
            for n in normals[1:]
        ):
            continue
        p1, p2 = (start[0], start[1]), (end[0], end[1])
        if p1 != p2:
            projected.add(tuple(sorted((p1, p2))))
    return tuple(sorted(projected))


def projected_assembly_parts(request):
    """World-positioned part outlines, including real holes and join edges."""
    return tuple(
        (role, key, _projected_outline(triangles))
        for role, key, triangles in _assembly_world_meshes(request)
    )


class CommittedPreviewError(ValueError):
    """A setting was committed, but its new preview could not resolve."""


def refresh_committed_preview(view, request_provider):
    try:
        view.draw_geometry(tuple(request_provider()))
    except Exception as exc:
        view.invalidate(str(exc))
        raise CommittedPreviewError(str(exc)) from exc


class ReceivingSettingsPreview2D:
    def __init__(self, parent, *, tk, ttk, requests, panel=None, common_box=False):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        self.common_box = bool(common_box)
        self.figure = Figure(figsize=(10, 6.2), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=.01, right=.99, bottom=.01, top=.99)
        apply_mpl_dark_theme(self.figure, (self.ax,))
        self.visibility = {}
        self._visibility_buttons = {}
        self._tk, self._ttk = tk, ttk
        self._filters = ttk.LabelFrame(parent, text="顯示零件", padding=4)
        self._filters.pack(fill=tk.X)
        self.status = tk.StringVar(master=parent, value="")
        ttk.Label(parent, textvariable=self.status).pack(anchor=tk.W)
        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.panel = panel
        self.requests = tuple(requests)
        self.tiles = []
        self.hover = None
        self.geometry_draw_count = 0
        self.canvas_draw_count = 0
        self.overlay_blit_count = 0
        self._background = None
        self.overlay_count = 0
        self._home = None
        self._drag = None
        self.canvas.mpl_connect("draw_event", self._on_draw)
        self.canvas.mpl_connect("button_press_event", self._press)
        self.canvas.mpl_connect("button_release_event", self._release)
        self.canvas.mpl_connect("motion_notify_event", self._motion)
        self.canvas.mpl_connect("scroll_event", self._scroll)
        self.draw_geometry()

    def draw_geometry(self, requests=None):
        from matplotlib.collections import LineCollection
        from matplotlib.patches import Rectangle
        self.status.set("")
        if requests is not None:
            self.requests = tuple(requests)
        self._background = None
        self.ax.clear()
        apply_mpl_dark_theme(self.figure, (self.ax,))
        self.tiles.clear()
        self._current_roles = []
        projected = [projected_assembly_parts(request) for request in self.requests]
        # Offset whole bays only when needed; never spread out their sheet parts.
        previous_right = None
        all_bounds = []
        for bay_index, parts in enumerate(projected):
            all_points = [point for _role, _key, edges in parts for edge in edges for point in edge]
            if not all_points:
                continue
            left = min(p[0] for p in all_points)
            right = max(p[0] for p in all_points)
            width = max(right - left, 1.0)
            gap = max(25.0, width * .06)
            shift = 0 if previous_right is None else max(0, previous_right + gap - left)
            previous_right = right + shift
            for role, key, edges in parts:
                self._current_roles.append(role)
                if not edges:
                    continue
                moved = tuple(((a[0]+shift, a[1]), (b[0]+shift, b[1]))
                              for a, b in edges)
                points = [point for edge in moved for point in edge]
                x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
                y0, y1 = min(p[1] for p in points), max(p[1] for p in points)
                edge_artist = LineCollection(moved,
                    colors=_COLORS.get(role, "#9eb6cd"), linewidths=.95)
                self.ax.add_collection(edge_artist)
                # Select/highlight at the actual projected assembly position.
                pad = max(2.0, min(width*.012, 12.0))
                rect = Rectangle((x0-pad, y0-pad),
                    max(x1-x0+2*pad, 12), max(y1-y0+2*pad, 12),
                    facecolor="none", edgecolor="#41464e", linewidth=1,
                    animated=True)
                self.ax.add_patch(rect)
                self.tiles.append((bay_index, role, key, rect, (edge_artist,)))
                all_bounds.extend(((x0, y0), (x1, y1)))
        self._sync_visibility_controls()
        self.ax.set_aspect("equal", adjustable="box")
        if all_bounds:
            x0, x1 = min(p[0] for p in all_bounds), max(p[0] for p in all_bounds)
            y0, y1 = min(p[1] for p in all_bounds), max(p[1] for p in all_bounds)
            mx, my = max(20, (x1-x0)*.04), max(20, (y1-y0)*.04)
            self.ax.set_xlim(x0-mx, x1+mx)
            self.ax.set_ylim(y0-my, y1+my)
        else:
            self.ax.set_xlim(0, 1)
            self.ax.set_ylim(0, 1)
        self.ax.set_axis_off()
        self._home = (self.ax.get_xlim(), self.ax.get_ylim())
        self.geometry_draw_count += 1
        self.update_visibility()

    def invalidate(self, message):
        """Discard stale visual data when the committed source fails to resolve."""
        self.requests = ()
        self.tiles.clear()
        self._background = None
        self.ax.clear()
        self.ax.set_axis_off()
        self._home = (self.ax.get_xlim(), self.ax.get_ylim())
        self._sync_visibility_controls()
        self.status.set("設定已提交；2D 預覽失敗：" + str(message))
        self.canvas.draw_idle()

    def _sync_visibility_controls(self):
        roles = tuple(dict.fromkeys(self._current_roles))
        for role in roles:
            if role not in self.visibility:
                var = self._tk.BooleanVar(master=self._filters, value=True)
                self.visibility[role] = var
                label = _LABELS.get(role, f"板件{len(self.visibility)}")
                button = self._ttk.Checkbutton(self._filters, text=label, variable=var,
                                              command=self.update_visibility)
                button.pack(side=self._tk.LEFT, padx=4)
                self._visibility_buttons[role] = button
        for role, button in self._visibility_buttons.items():
            button.configure(state="normal" if role in roles else "disabled")

    def update_visibility(self):
        self._background = None
        for _bay, role, _key, rect, artists in self.tiles:
            visible = self.visibility[role].get()
            rect.set_visible(visible)
            for artist in artists:
                artist.set_visible(visible)
        self.update_overlay()

    def _enabled_role(self, role):
        kind = getattr(self.panel, "_receiving_kind", None)
        return ((kind=="head_features" and role=="head") or
                (kind=="tail_features" and role=="tail") or
                (kind=="back_panel_mode" and role=="back") or
                (kind=="inner_door_layers" and role.startswith("inner_door")))

    def update_overlay(self):
        pending = getattr(self.panel, "_receiving_pending", ())
        matches = getattr(self.panel, "_receiving_matches", ())
        for bay, role, key, rect, _artists in self.tiles:
            enabled = self._enabled_role(role)
            rect.set_facecolor("#2563eb" if enabled and bay in pending else
                               "#334155" if enabled and bay in matches else "none")
            rect.set_alpha(.25 if enabled and bay in pending else .18 if enabled and bay in matches else 1)
            rect.set_edgecolor("#facc15" if enabled and bay==self.hover else
                               "#60a5fa" if enabled and bay in pending else "#41464e")
        self.overlay_count += 1
        self._paint_overlay()

    def _on_draw(self, _event):
        self.canvas_draw_count += 1
        self._background = self.canvas.copy_from_bbox(self.ax.bbox)
        self._paint_overlay()

    def _paint_overlay(self):
        if self._background is None:
            self.canvas.draw_idle()
            return
        self.canvas.restore_region(self._background)
        for _bay, _role, _key, rect, _artists in self.tiles:
            if rect.get_visible():
                self.ax.draw_artist(rect)
        self.canvas.blit(self.ax.bbox)
        self.overlay_blit_count += 1

    def _hit(self, event):
        if event.inaxes is not self.ax or event.xdata is None or event.ydata is None:
            return None
        for bay, role, _key, rect, _artists in self.tiles:
            if rect.get_visible() and self._enabled_role(role) and rect.get_bbox().contains(event.xdata,event.ydata):
                return bay
        return None

    def _press(self, event):
        if event.button == 1:
            bay = self._hit(event)
            if bay is not None and self.panel is not None:
                self.panel._receiving_select_bay(bay)
        elif event.button == 2 and event.inaxes is self.ax:
            self._drag = (event.x,event.y,self.ax.get_xlim(),self.ax.get_ylim())

    def _release(self, _event):
        self._drag = None

    def _motion(self, event):
        if self._drag and event.inaxes is self.ax and event.xdata is not None:
            x,y,xlim,ylim=self._drag
            dx = (x-event.x)*(xlim[1]-xlim[0])/self.ax.bbox.width
            dy = (y-event.y)*(ylim[1]-ylim[0])/self.ax.bbox.height
            self._background = None
            self.ax.set_xlim(xlim[0]+dx,xlim[1]+dx)
            self.ax.set_ylim(ylim[0]+dy,ylim[1]+dy)
            self.canvas.draw_idle()
            return
        hover=self._hit(event)
        if hover != self.hover:
            self.hover=hover
            self.update_overlay()

    def zoom(self, factor, center=None):
        self._background = None
        xlim,ylim=self.ax.get_xlim(),self.ax.get_ylim()
        cx,cy=center or ((xlim[0]+xlim[1])/2,(ylim[0]+ylim[1])/2)
        self.ax.set_xlim(*(cx+(x-cx)*factor for x in xlim))
        self.ax.set_ylim(*(cy+(y-cy)*factor for y in ylim))
        self.canvas.draw_idle()

    def _scroll(self, event):
        if event.inaxes is self.ax:
            self.zoom(.8 if event.button=="up" else 1.25,(event.xdata,event.ydata))

    def reset_view(self):
        self._background = None
        self.ax.set_xlim(self._home[0])
        self.ax.set_ylim(self._home[1])
        self.canvas.draw_idle()
