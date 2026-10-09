"""2D presentation of committed Receiving physical DrawingScenes.

Tile transforms are display layout only. Selection never asks the geometry
provider for another request and never constructs a folded mesh.
"""
from __future__ import annotations

from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive
from whd_theme import apply_mpl_dark_theme

_LABELS = {"head": "封頭", "tail": "封尾", "box_body": "箱身", "door": "門",
           "base_plate": "底板", "inner_door": "內門", "indicator_box": "指示燈盒",
           "left_side": "左側板", "right_side": "右側板", "back": "背板",
           "divider": "中隔"}
_COLORS = {"CUTTING": "#30d158", "BEND": "#0a84ff", "MARKING": "#8e8e93",
           "BLIND_HOLE": "#ff453a", "DATUM": "#bf5af2"}


def _role_group(key):
    for role in ("inner_door", "indicator_box", "indicator_door", "base_plate", "door"):
        if key.startswith(role):
            return role
    return key


def physical_drawings(request):
    """Expand physical box pieces without re-solving their manufacturing data."""
    for part in request.render_data.assembly_parts:
        pieces = tuple(getattr(part.render_data, "pieces", ()) or ())
        if pieces:
            for piece in pieces:
                yield str(piece.role), str(piece.key), piece.render_data
        else:
            yield _role_group(str(part.part_key)), str(part.part_key), part.render_data


class CommittedPreviewError(ValueError):
    """A setting was committed, but its new preview could not resolve."""


def refresh_committed_preview(view, request_provider):
    try:
        view.draw_geometry(tuple(request_provider()))
    except Exception as exc:
        view.invalidate(str(exc))
        raise CommittedPreviewError(str(exc)) from exc


class ReceivingSettingsPreview2D:
    def __init__(self, parent, *, tk, ttk, requests, panel=None):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
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
        from matplotlib.patches import Circle, Rectangle
        self.status.set("")
        if requests is not None:
            self.requests = tuple(requests)
        self._background = None
        self._sync_visibility_controls()
        self.ax.clear()
        apply_mpl_dark_theme(self.figure, (self.ax,))
        self.tiles.clear()
        # One column per Bay; each physical sheet is its own labelled 2D tile.
        # Use actual material bounds only to fit the immutable drawing on screen.
        for bay_index, request in enumerate(self.requests):
            for ordinal, (role, key, data) in enumerate(physical_drawings(request)):
                x0, y0, x1, y1 = map(float, data.material.bounds)
                width, height = max(x1-x0, 1), max(y1-y0, 1)
                scale = min(260 / width, 210 / height)
                ox, oy = bay_index * 310 + 25 - x0*scale, -ordinal*270 - y0*scale
                def xy(point):
                    return ox + point.x*scale, oy + point.y*scale
                artists = []
                for primitive in data.scene.primitives:
                    color = _COLORS.get(primitive.layer)
                    if color is None:
                        continue
                    if isinstance(primitive, PolylinePrimitive):
                        points = list(primitive.points)
                        if primitive.closed and points:
                            points.append(points[0])
                        if len(points) >= 2:
                            xs, ys = zip(*(xy(point) for point in points))
                            artists.extend(self.ax.plot(xs, ys, color=color, linewidth=1))
                    elif isinstance(primitive, LinePrimitive):
                        p1, p2 = xy(primitive.p1), xy(primitive.p2)
                        artists.extend(self.ax.plot((p1[0],p2[0]),(p1[1],p2[1]),
                            color=color, linewidth=1, linestyle="--" if primitive.layer=="BEND" else "-"))
                    elif isinstance(primitive, CirclePrimitive):
                        artist = Circle(xy(primitive.center), primitive.radius*scale,
                                        fill=False, edgecolor=color, linewidth=1)
                        self.ax.add_patch(artist)
                        artists.append(artist)
                rect = Rectangle((bay_index*310+10, -ordinal*270-15), 290, 245,
                                 facecolor="none", edgecolor="#41464e", linewidth=1,
                                 animated=True)
                self.ax.add_patch(rect)
                label = _LABELS.get(role, "箱身板件" if role=="box_body" else
                                    "內門" if role.startswith("inner_door") else
                                    "門" if role.startswith("door") else "板件")
                text = self.ax.text(bay_index*310+15, -ordinal*270+237,
                                    f"第{bay_index+1}連｜{label}", color="#d1d5db", fontsize=8)
                self.tiles.append((bay_index, role, key, rect, tuple(artists)+(text,)))
        self.ax.set_aspect("equal", adjustable="box")
        self.ax.autoscale_view()
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
        roles = tuple(dict.fromkeys(role for request in self.requests
                                    for role, _, _ in physical_drawings(request)))
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
