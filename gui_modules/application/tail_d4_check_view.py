# -*- coding: utf-8 -*-
"""#3317 read-only true-source Ø4 CHECK preview in an actual Tk window.

The Engine has already sourced/verified the exact CUTTING, original holes,
finite BEND and T2 shell. This module paints the SAME resolved source and
the native assembled world mesh: it never builds CUTTING, a new bend, a
manufacuring request, R/BA, or an artificial connecting shell face.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from matplotlib import font_manager
from matplotlib.text import Text
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from ae_engine import manufacturing_api



def _native_world_y_up(ax, *, elev, azim):
    """View only: never reorder WHD X/Y/Z coordinates or mesh winding."""
    try:
        ax.view_init(elev=elev, azim=azim, vertical_axis="y")
    except TypeError as exc:
        # A Z-up fallback would silently misrepresent the assembled cabinet.
        raise ValueError(
            "TAIL_D4_CHECK_REQUIRES_MATPLOTLIB_Y_UP_VIEW"
        ) from exc


def _use_available_cjk_font(figure):
    """Find an installed face by family, never a platform-specific font path."""
    installed={entry.name for entry in font_manager.fontManager.ttflist}
    for name in (
        "Noto Sans CJK TC", "Noto Sans CJK SC", "Microsoft JhengHei",
        "PingFang TC", "WenQuanYi Zen Hei", "Source Han Sans TC",
        "AR PL UMing TW",
    ):
        if name in installed:
            for label in figure.findobj(match=Text):
                label.set_fontfamily(name)
            return name
    return None


def _cross_section_world_x(triangles, x_center):
    """Actual triangular shell-plane intersections; no fitted curves."""
    lines=[]
    for tri in triangles:
        cross=[]
        for i,j in ((0,1),(1,2),(2,0)):
            a=tri[i];b=tri[j];da=a[0]-x_center;db=b[0]-x_center
            if abs(da)<1e-7 and abs(db)<1e-7:
                cross.extend((a,b))
            elif abs(da)<1e-7:
                cross.append(a)
            elif abs(db)<1e-7:
                cross.append(b)
            elif da*db<0:
                t=-da/(db-da)
                cross.append(tuple(a[k]+t*(b[k]-a[k]) for k in range(3)))
        unique=[]
        for p in cross:
            if not any(sum((p[k]-q[k])**2 for k in range(3))<1e-12
                       for q in unique):
                unique.append(p)
        if len(unique)>=2:
            # A face exactly coplanar with section can give three points;
            # show the longest true edge, never interpolate a guessed arc.
            pair=max(((p,q) for i,p in enumerate(unique)
                      for q in unique[i+1:]),
                     key=lambda pq:sum((pq[0][k]-pq[1][k])**2
                                       for k in range(3)))
            lines.append(pair)
    return tuple(lines)


def _fit_equal_3d(ax, triangles):
    points=[p for tri in triangles for p in tri]
    if not points:
        return
    spans=[(min(p[k] for p in points),max(p[k] for p in points))
           for k in range(3)]
    centers=[sum(p)/2 for p in spans]
    half=max(max(b-a for a,b in spans)/2,1.)
    for limits,center in ((ax.set_xlim,centers[0]),
                          (ax.set_ylim,centers[1]),
                          (ax.set_zlim,centers[2])):
        limits(center-half,center+half)


def show_tail_d4_check_window(
    parent, *, flat, check, body_world, placed_world, first_axis,
    save_dxf, assembly_check, world_source_faces=None,
    world_source_uv=None, world_candidate=None,
):
    """Open a native Tk CHECK-only view: 2D, assembled 3D, upper, both roots."""
    # The candidate world shell has one UV-source triplet PER displayed
    # triangle. Unlike old CHECK shell_faces, these are not local
    # +/-T vertex indices and must never be used for local placement.
    source_faces=(check.shell_faces if world_source_faces is None
                  else tuple(world_source_faces))
    source_uv=(check.source_uv if world_source_uv is None
               else tuple(world_source_uv))
    if (not body_world or len(placed_world)!=len(source_faces)
            or not source_uv
            or any(len(face)!=3 or any(
                not isinstance(i,int) or i<0 or i>=len(source_uv)
                for i in face
            ) for face in source_faces)):
        if world_candidate is None and world_source_faces is None:
            # The original source faces include outer-skin offset indices.
            if not body_world or len(placed_world)!=len(check.shell_faces):
                raise ValueError("TAIL_D4_CHECK_GUI_NATIVE_WORLD_SOURCE_REQUIRED")
        else:
            raise ValueError("TAIL_D4_CHECK_GUI_WORLD_UV_SOURCE_MISMATCH")
    if world_candidate is not None and (
        world_source_faces is None or world_source_uv is None
        or tuple(placed_world)!=tuple(world_candidate["v_solid"])
        or source_faces!=tuple(world_candidate["v_solid_source_ids"])
        or source_uv!=tuple(world_candidate["v_source_uv"])
        or world_candidate["manufacturing_approved"]
    ):
        raise ValueError("TAIL_D4_CHECK_GUI_WORLD_CANDIDATE_UNTRUSTED")
    if (assembly_check.body_triangle_count != len(body_world)
            or assembly_check.tail_triangle_count != len(placed_world)
            or assembly_check.manufacturing_approved):
        raise ValueError("TAIL_D4_CHECK_GUI_ASSEMBLY_SOURCE_MISMATCH")
    evidence_note=(
        "｜下方 V 候選／原有開邊 %d／新增 %d"
        % (world_candidate["v_world_open_edges"],
           world_candidate["v_extra_world_open_edges"])
        if world_candidate is not None else ""
    )
    win=tk.Toplevel(parent)
    win.title("WHD 封尾 Ø4 CHECK_NOT_CNC — 不能加工")
    win.geometry("1480x940")
    toolbar=ttk.Frame(win)
    toolbar.pack(fill=tk.X,padx=8,pady=(6,3))
    ttk.Label(toolbar,text=(
        "封尾 Ø4｜真 Factory／專案來源｜"
        +first_axis.upper()+"/"+first_axis.upper()
        +"｜CHECK_NOT_CNC｜R2_MODEL_UNRESOLVED｜裝配體積未驗收"
        +evidence_note
    )).pack(side=tk.LEFT)
    def save():
        filename=filedialog.asksaveasfilename(
            parent=win,title="另存 Ø4 看圖 CHECK DXF（不得加工）",
            defaultextension=".dxf",
            filetypes=[("AutoCAD ASCII DXF", "*.dxf")],
            initialfile="tail_d4_"+first_axis+"_CHECK_NOT_CNC.dxf",
        )
        if not filename:
            return
        try:
            save_dxf(filename)
        except (ValueError,TypeError,OSError) as exc:
            messagebox.showerror("Ø4 CHECK 來源未通過",str(exc),parent=win)
        else:
            messagebox.showinfo("Ø4 CHECK", "已產生非加工看圖 DXF",parent=win)
    ttk.Button(toolbar,text="另存看圖 DXF（非加工）",command=save).pack(
        side=tk.RIGHT,padx=4,
    )
    figure=Figure(figsize=(14.5,8.6),dpi=100)
    grid=figure.add_gridspec(2,3,height_ratios=(1,1),hspace=.22,wspace=.25)
    flat_ax=figure.add_subplot(grid[0,0])
    assembly_ax=figure.add_subplot(grid[0,1:],projection="3d")
    section_ax=figure.add_subplot(grid[1,0])
    left_ax=figure.add_subplot(grid[1,1],projection="3d")
    right_ax=figure.add_subplot(grid[1,2],projection="3d")
    for primitive in flat.result_scene.primitives:
        if isinstance(primitive,manufacturing_api.TailD4PreviewPolylinePrimitive) and primitive.layer=="CUTTING":
            xy=[(p.x,p.y) for p in primitive.points]
            if primitive.closed:xy.append(xy[0])
            flat_ax.plot([v[0] for v in xy],[v[1] for v in xy],
                         color="#0378aa",linewidth=.9)
        elif isinstance(primitive,manufacturing_api.TailD4PreviewCirclePrimitive) and primitive.layer=="CUTTING":
            flat_ax.add_patch(Circle((primitive.center.x,primitive.center.y),
                             primitive.radius,fill=False,
                             edgecolor="#0378aa",linewidth=1.))
        elif isinstance(primitive,manufacturing_api.TailD4PreviewLinePrimitive) and primitive.layer=="BEND":
            flat_ax.plot((primitive.p1.x,primitive.p2.x),
                         (primitive.p1.y,primitive.p2.y),
                         color="#b7791f",linewidth=.9,linestyle="--")
    flat_ax.set_title("2D 真 CUTTING／原孔／有限 BEND 參考",fontsize=10)
    flat_ax.set_aspect("equal",adjustable="box")
    flat_ax.set_xlabel("X mm");flat_ax.set_ylabel("Y mm")
    flat_ax.grid(alpha=.2)

    # The already verified T shell is rendered in its ACTUAL native world
    # coordinates. Box Body is the Engine's own physical mesh, not a box().
    assembly_ax.add_collection3d(Poly3DCollection(
        body_world,facecolors="#6b7280",edgecolors="none",alpha=.04,
    ))
    assembly_ax.add_collection3d(Poly3DCollection(
        placed_world,facecolors="#0284c7",edgecolors="none",alpha=.43,
    ))
    _fit_equal_3d(assembly_ax,tuple(body_world)+tuple(placed_world))
    for first,last in assembly_check.crossing_segments:
        assembly_ax.plot(
            (first[0],last[0]),(first[1],last[1]),(first[2],last[2]),
            color="#d97706",linewidth=.9,
        )
    _native_world_y_up(assembly_ax,elev=18,azim=-32)
    assembly_ax.set_title(
        "實際箱身＋Ø4：非共面穿越 %d 對／%d 段；非體積證明" % (
            assembly_check.crossing_pair_count,
            len(assembly_check.crossing_segments),
        ),fontsize=10,
    )
    assembly_ax.set_xlabel("World X");assembly_ax.set_ylabel("World Y")
    assembly_ax.set_zlabel("World Z")

    # Center world-X section through the true source upper Fold domains.
    # The Y/Z coordinates come directly from the assembled T mesh.
    all_x=[p[0] for tri in placed_world for p in tri]
    center=(min(all_x)+max(all_x))/2
    st=manufacturing_api.project_operator_tail_d4_source_stations(flat)
    n=len(source_uv)
    upper_mesh=tuple(
        tri for face,tri in zip(source_faces,placed_world)
        if all(source_uv[v%n][1]>=st.upper_start-1e-6
               for v in face)
    )
    sections=_cross_section_world_x(upper_mesh,center)
    for a,b in sections:
        section_ax.plot((a[2],b[2]),(a[1],b[1]),
                        color="#075985",linewidth=1.)
    section_ax.set_title("上方兩折：真 T 殼 world-X 中央剖面",fontsize=10)
    section_ax.set_xlabel("World Z mm");section_ax.set_ylabel("World Y mm")
    section_ax.set_aspect("equal",adjustable="datalim")
    section_ax.grid(alpha=.2)

    for corner,ax in zip(flat.opening_source_points_xy,(left_ax,right_ax)):
        name,_lo,apex,_hi=corner
        corner_mesh=tuple(
            tri for face,tri in zip(source_faces,placed_world)
            if all(abs(source_uv[v%n][0]-apex[0])<=26.
                   and abs(source_uv[v%n][1]-apex[1])<=26.
                   for v in face)
        )
        if corner_mesh:
            ax.add_collection3d(Poly3DCollection(
                corner_mesh,facecolors="#0284c7",
                edgecolors="#164e63",linewidths=.13,alpha=.74,
            ))
            _fit_equal_3d(ax,corner_mesh)
        _native_world_y_up(
            ax,elev=20,azim=54 if ax is left_ax else -54,
        )
        ax.set_title(name+"：真正同源 Ø4 槽底放大",fontsize=10)
        ax.set_xlabel("World X");ax.set_ylabel("World Y")
        ax.set_zlabel("World Z")
    volume_message=(
        "Body 非封閉：體積干涉無法驗證"
        if not assembly_check.body_edges_manifold_closed
        else "體積干涉未由表面穿越證實"
    )
    # Amber lines are confirmed surface crossings, NOT certified volume
    # penetration. Coplanar mates and isolated single-point touches are not
    # counted by this detector; no unmeasured material is inferred.
    regions=dict(assembly_check.crossing_regions)
    uv=assembly_check.crossing_tail_uv_bounds
    world=assembly_check.crossing_world_bounds
    if uv is not None and world is not None:
        location=(
            "命中 Tail UV x %.2f..%.2f / y %.2f..%.2f mm；"
            "world Y %.2f..%.2f mm；"
            "左槽 %d／右槽 %d／其他 %d 個命中面"
        ) % (
            uv[0][0],uv[0][1],uv[1][0],uv[1][1],
            world[1][0],world[1][1],
            regions.get("bottom_left",0),regions.get("bottom_right",0),
            regions.get("other",0),
        )
    else:
        location="目前未找到可回溯的 Tail UV 命中面"
    figure.suptitle(
        "WHD #3317 Ø4 CHECK_NOT_CNC — Y 向上；"
        +volume_message+"；切面密合仍未驗收",fontsize=11,
    )
    # Inspection-only annotation; no changes to actual physical triangles.
    figure.text(
        .50,.012,location+"；橘線=非共面表面穿越，非體積證明",
        ha="center",fontsize=9,
    )
    win._tail_d4_cjk_font=_use_available_cjk_font(figure)
    figure.tight_layout(rect=(0,.035,1,.95))
    canvas=FigureCanvasTkAgg(figure,master=win)
    canvas.get_tk_widget().pack(fill=tk.BOTH,expand=True)
    canvas.draw()
    win._tail_d4_check_figure=figure
    win._tail_d4_check_canvas=canvas
    # Inspectable exact Engine sources for native GUI regression, never
    # manufacturing or project state; destroyed with the CHECK window.
    win._tail_d4_check_flat=flat
    win._tail_d4_check_shell=check
    win._tail_d4_check_body_world=body_world
    win._tail_d4_check_placed_world=placed_world
    win._tail_d4_check_world_source_faces=source_faces
    win._tail_d4_check_world_source_uv=source_uv
    win._tail_d4_check_world_candidate=world_candidate
    win._tail_d4_assembly_check=assembly_check
    return win
