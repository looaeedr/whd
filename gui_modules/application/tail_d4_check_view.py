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
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from ae_engine import manufacturing_api


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
    save_dxf,
):
    """Open a native Tk CHECK-only view: 2D, assembled 3D, upper, both roots."""
    if not body_world or len(placed_world)!=len(check.shell_faces):
        raise ValueError("TAIL_D4_CHECK_GUI_NATIVE_WORLD_SOURCE_REQUIRED")
    win=tk.Toplevel(parent)
    win.title("WHD 封尾 Ø4 CHECK_NOT_CNC — 不能加工")
    win.geometry("1480x940")
    toolbar=ttk.Frame(win)
    toolbar.pack(fill=tk.X,padx=8,pady=(6,3))
    ttk.Label(toolbar,text=(
        "封尾 Ø4｜真 Factory／專案來源｜"
        +first_axis.upper()+"/"+first_axis.upper()
        +"｜CHECK_NOT_CNC｜R2_MODEL_UNRESOLVED｜箱體交會未驗收"
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
    assembly_ax.view_init(elev=25,azim=-56)
    assembly_ax.set_title("原生箱身＋封尾 Ø4 T2 殼（非密合證明）",fontsize=10)
    assembly_ax.set_xlabel("World X");assembly_ax.set_ylabel("World Y")
    assembly_ax.set_zlabel("World Z")

    # Center world-X section through the true source upper Fold domains.
    # The Y/Z coordinates come directly from the assembled T mesh.
    all_x=[p[0] for tri in placed_world for p in tri]
    center=(min(all_x)+max(all_x))/2
    st=manufacturing_api.project_operator_tail_d4_source_stations(flat)
    n=len(check.source_uv)
    upper_mesh=tuple(
        tri for face,tri in zip(check.shell_faces,placed_world)
        if all(check.source_uv[v%n][1]>=st.upper_start-1e-6
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
            tri for face,tri in zip(check.shell_faces,placed_world)
            if all(abs(check.source_uv[v%n][0]-apex[0])<=26.
                   and abs(check.source_uv[v%n][1]-apex[1])<=26.
                   for v in face)
        )
        if corner_mesh:
            ax.add_collection3d(Poly3DCollection(
                corner_mesh,facecolors="#0284c7",
                edgecolors="#164e63",linewidths=.13,alpha=.74,
            ))
            _fit_equal_3d(ax,corner_mesh)
        ax.view_init(elev=25,azim=-54)
        ax.set_title(name+"：真正同源 Ø4 槽底放大",fontsize=10)
        ax.set_xlabel("World X");ax.set_ylabel("World Y")
        ax.set_zlabel("World Z")
    figure.suptitle(
        "WHD #3317 Ø4 CHECK_NOT_CNC — 原始料四個真孔；"
        "定位不表示箱體免避空／V 面密合合格",fontsize=11,
    )
    figure.tight_layout(rect=(0,0,1,.97))
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
    return win
