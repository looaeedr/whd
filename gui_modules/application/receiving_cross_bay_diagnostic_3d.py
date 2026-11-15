"""Original Receiving multi-Bay GUI: actual Engine world-mesh 3D view.

Only paints already-resolved Engine 3D triangles and unresolved surface
intersection lines. No material, Joint transforms, collision decisions,
manufacturing geometry or certified solid-penetration math live here.
"""
from __future__ import annotations

from dataclasses import dataclass

from phase6_final_scene_mesh_display import gridless_mesh_collection
from whd_theme import apply_mpl_dark_theme


# Presentation-only alternating Set/Bay colors; never geometry/Family policy.
_BAY_COLORS = ("#78a7db", "#c7a2df", "#88b6b3", "#f7c66f",
               "#b7d99a", "#dda9b5")


@dataclass(frozen=True)
class ReceivingCrossBay3DDisplayReceipt:
    """What this view actually painted, with physical identity preserved."""

    sheet_keys: tuple[str, ...]
    unresolved_segments: tuple
    missing_world_keys: tuple[str, ...]


def paint_receiving_cross_bay_3d_figure(figure, audit, *, status=""):
    """Paint only full physical world meshes from the exact collision audit.

    The Engine's world_triangles_by_bay has already applied canonical Bay
    Joint positions and validated every vertex. Refuse an unbound or partial
    drawing receipt; a missing real sheet is still shown as an explicit
    diagnostic blocker, not invented display geometry.
    """
    from mpl_toolkits.mplot3d.art3d import Line3DCollection

    groups = tuple(getattr(audit, "world_triangles_by_bay", ()) or ())
    bays = tuple(getattr(audit, "bay_ids", ()) or ())
    physical_keys = tuple(getattr(audit, "physical_keys_by_bay", ()) or ())
    if not groups or len(groups) != len(bays) or len(groups) != len(physical_keys):
        raise ValueError("RECEIVING_CROSS_BAY_3D_SOURCE_MESH_RECEIPT_MISSING")

    figure.clear()
    ax = figure.add_subplot(111, projection="3d")
    apply_mpl_dark_theme(figure, (ax,))
    ax.set_axis_off()
    ax.grid(False)
    painted_keys = []
    min_xyz = [float("inf")] * 3
    max_xyz = [float("-inf")] * 3
    for bay_index, group in enumerate(groups):
        if tuple(key for key, _ in group) != tuple(physical_keys[bay_index]):
            raise ValueError("RECEIVING_CROSS_BAY_3D_SOURCE_KEY_DRIFT")
        for key, triangles in group:
            if not triangles:
                raise ValueError("RECEIVING_CROSS_BAY_3D_EMPTY_PHYSICAL_SHEET")
            ax.add_collection3d(gridless_mesh_collection(
                triangles, facecolor=_BAY_COLORS[bay_index % len(_BAY_COLORS)],
                opacity=0.68,
            ))
            painted_keys.append(key)
            for triangle in triangles:
                for vertex in triangle:
                    for i in range(3):
                        min_xyz[i] = min(min_xyz[i], vertex[i])
                        max_xyz[i] = max(max_xyz[i], vertex[i])
    if not painted_keys:
        raise ValueError("RECEIVING_CROSS_BAY_3D_NO_PHYSICAL_MESH")

    segments = tuple(
        segment for pair in audit.unresolved for segment in pair.segments
    )
    if segments:
        ax.add_collection3d(Line3DCollection(
            segments, colors="#ff9900", linewidths=3.6, alpha=0.98,
        ))
    spans = [max(1.0, high-low) for low, high in zip(min_xyz, max_xyz)]
    for i, setter in enumerate((ax.set_xlim3d, ax.set_ylim3d, ax.set_zlim3d)):
        middle = (min_xyz[i] + max_xyz[i]) / 2.0
        setter(middle - spans[i] * 0.55, middle + spans[i] * 0.55)
    ax.set_box_aspect(spans)
    text = str(status or (
        f"{len(bays)} Bays | {audit.evaluated_pair_count} physical pairs"
    ))
    ax.text2D(0.01, 0.98, text, transform=ax.transAxes,
              ha="left", va="top", fontsize=9)
    return ReceivingCrossBay3DDisplayReceipt(
        sheet_keys=tuple(painted_keys),
        unresolved_segments=segments,
        missing_world_keys=tuple(audit.missing_world_keys),
    )


def open_receiving_cross_bay_3d_popup(parent, *, tk, ttk, audit, status):
    """Make a rotatable GUI view from an existing, exact-source Engine audit."""
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    # Render BEFORE publishing a window, so an invalid/empty source leaves
    # no misleading earlier success popup or half-rendered 3D surface.
    figure = Figure(figsize=(11, 6.5), dpi=100)
    receipt = paint_receiving_cross_bay_3d_figure(
        figure, audit, status=status,
    )
    popup = tk.Toplevel(parent)
    popup.title("受電箱｜跨連 3D 實體碰撞診斷（非製造放行）")
    popup.transient(parent)
    frame = ttk.Frame(popup, padding=6)
    frame.pack(fill=tk.BOTH, expand=True)
    canvas = FigureCanvasTkAgg(figure, master=frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text="橘線＝跨連未證實合法交線；無橘線不等於實體體積零穿透").pack(anchor=tk.W)
    ttk.Button(frame, text="關閉", command=popup.destroy).pack(anchor=tk.E)
    popup._phase6_cross_bay_3d_canvas = canvas
    popup._phase6_cross_bay_3d_receipt = receipt
    canvas.draw()
    return popup
