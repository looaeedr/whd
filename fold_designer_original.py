import tkinter as tk
from tkinter import ttk
import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.projections import register_projection
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.patches as patches
import math
import sys
import os

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

mpl.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'Heiti TC', 'sans-serif']
mpl.rcParams['axes.unicode_minus'] = False

# ==========================================
# 基礎輔助工具
# ==========================================
def get_int(val):
    try: return int(round(float(val)))
    except (ValueError, TypeError): return 0

def bind_overwrite(entry):
    def on_focus_in(event):
        entry.after(50, lambda: entry.select_range(0, tk.END))
    def on_key(event):
        if event.char and event.char.isprintable():
            try:
                if entry.select_present():
                    entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
                    entry.insert(tk.INSERT, event.char)
                    return "break" 
            except Exception: pass
    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<Key>", on_key)

def auto_generate_ico():
    ico_path = "mycad.ico"
    if os.path.exists(ico_path): return True
    if not HAS_PIL: return False
    try:
        size = 512
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        bg_color, border_color = (10, 25, 47, 255), (23, 42, 69, 255)
        draw.rounded_rectangle([16, 16, 496, 496], radius=48, fill=bg_color, outline=border_color, width=6)
        
        grid_color = (23, 42, 69, 150)
        for x in range(32, 480, 32): draw.line([x, 32, x, 480], fill=grid_color, width=1)
        for y in range(32, 480, 32): draw.line([32, y, 480, y], fill=grid_color, width=1)

        scale, cx, cy = 1.65, 256, 275
        def proj(x, y, z): return (int(cx + (x - y) * 0.8660254 * scale), int(cy + (x + y) * 0.5 * scale - z * scale))

        b1, b2, b3, b4 = proj(-70, -60, 0), proj(70, -60, 0), proj(70, 60, 0), proj(-70, 60, 0)
        l1, l2, l3, l4 = b1, b4, proj(-70, 60, 80), proj(-70, -60, 80)
        r1, r2, r3, r4 = b2, b3, proj(70, 60, 80), proj(70, -60, 80)

        draw.polygon([l1, l2, l3, l4], fill=(27, 54, 93, 240), outline=(0, 240, 255, 255), width=4)
        draw.polygon([b1, b2, b3, b4], fill=(17, 34, 64, 240), outline=(0, 240, 255, 255), width=4)
        draw.polygon([r1, r2, r3, r4], fill=(32, 74, 135, 240), outline=(0, 240, 255, 255), width=4)

        circle_pts = [proj(70, 24 * math.cos(math.radians(d)), 24 * math.sin(math.radians(d)) + 40) for d in range(0, 361, 10)]
        draw.polygon(circle_pts, fill=bg_color, outline=(0, 240, 255, 255), width=4)
        draw.line([proj(70, -38, 40), proj(70, 38, 40)], fill=(239, 68, 68, 255), width=2)
        draw.line([proj(70, 0, 12), proj(70, 0, 68)], fill=(239, 68, 68, 255), width=2)

        d_s, d_e = proj(112, -60, 0), proj(112, -60, 80)
        draw.line([proj(70, -60, 0), d_s], fill=(79, 124, 172, 180), width=2)
        draw.line([proj(70, -60, 80), d_e], fill=(79, 124, 172, 180), width=2)
        draw.line([d_s, d_e], fill=(255, 159, 28, 255), width=3)
        draw.line([d_e, (d_e[0]-8, d_e[1]+10)], fill=(255, 159, 28, 255), width=3)
        draw.line([d_e, (d_e[0]+8, d_e[1]+10)], fill=(255, 159, 28, 255), width=3)
        draw.line([d_s, (d_s[0]-8, d_s[1]-10)], fill=(255, 159, 28, 255), width=3)
        draw.line([d_s, (d_s[0]+8, d_s[1]-10)], fill=(255, 159, 28, 255), width=3)

        mx, my = (d_s[0] + d_e[0]) // 2 + 20, (d_s[1] + d_e[1]) // 2
        draw.line([(mx-6, my-10), (mx-6, my+10)], fill=(255, 159, 28, 255), width=3)
        draw.line([(mx+6, my-10), (mx+6, my+10)], fill=(255, 159, 28, 255), width=3)
        draw.line([(mx-6, my), (mx+6, my)], fill=(255, 159, 28, 255), width=3)

        img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return True
    except: return False

# ==========================================
# 模組 1：資料中心 (AppState)
# ==========================================
class AppState:
    def __init__(self):
        self.w, self.h, self.d = 500, 600, 200
        self.enable_y = True
        self.symmetric = True
        
        self.alpha_bend = 0.6  
        self.alpha_face = 0.2  
        self.ui_text_scale = 1.0
        
        self.struct_mode = 'standard' # 新增結構模式切換：'standard' (標準) / 'vault' (金庫)
        
        # 標準十字型折彎資料
        self.profiles = {
            'X': [{'angle': 90, 'len': 25}, {'angle': -90, 'len': 200}, {'angle': -90, 'len': 500}, {'angle': 90, 'len': 200}, {'len': 25}],
            'Y': [{'angle': -90, 'len': 25}, {'angle': -90, 'len': 600}, {'len': 25}]
        }
        
        # ★ 金庫型 (三件式) 折彎資料
        self.profiles_vault = {
            '箱身': [{'angle': 90, 'len': 25}, {'angle': -90, 'len': 200}, {'angle': -90, 'len': 500}, {'angle': 90, 'len': 200}, {'len': 25}],
            '封頭': [{'angle': -90, 'len': 25}, {'angle': -90, 'len': 600}, {'len': 25}],
            '封尾': [{'angle': -90, 'len': 25}, {'angle': -90, 'len': 600}, {'len': 25}]
        }
        
        self.active_bend = 'X'
        
        self.faces = ['正面', '背面', '頂面', '底面', '左面', '右面']
        self.holes = {f: [] for f in self.faces}
        self.holes['正面'] = [{'type': '方孔', 'name': '螢幕', 'x': 250, 'y': 100, 'd1': 200, 'd2': 80}]
        self.active_face = '正面'

# ==========================================
# 模組 2：繪圖引擎 (Renderer)
# ==========================================
class Renderer:
    def __init__(self, ax3d, ax2d, state, canvas):
        self.ax3d = ax3d; self.ax2d = ax2d
        self.state = state; self.canvas = canvas

    def calc_profile(self, segs):
        if not segs: return [], [], 0
        u, z = 0, 0
        raw_u, raw_z = [u], [z]
        angles, current_angle = [], 0
        
        for seg in segs:
            angles.append(current_angle)
            l = seg['len']
            rad = math.radians(current_angle)
            u += l * math.cos(rad); z += l * math.sin(rad)
            raw_u.append(u); raw_z.append(z)
            if 'angle' in seg: current_angle -= seg['angle']

        base_idx = len(segs) // 2
        base_len = segs[base_idx]['len'] if segs else 0
        base_angle_rad = math.radians(angles[base_idx]) if base_idx < len(angles) else 0

        rotated_u, rotated_z = [], []
        for i in range(len(raw_u)):
            ru = raw_u[i] * math.cos(-base_angle_rad) - raw_z[i] * math.sin(-base_angle_rad)
            rz = raw_u[i] * math.sin(-base_angle_rad) + raw_z[i] * math.cos(-base_angle_rad)
            rotated_u.append(ru); rotated_z.append(rz)

        u_center = (rotated_u[base_idx] + rotated_u[base_idx+1]) / 2.0
        z_base = rotated_z[base_idx]
        return [val - u_center for val in rotated_u], [val - z_base for val in rotated_z], base_len

    def get_hole_3d(self, face, h_obj):
        W, H, D = self.state.w, self.state.h, self.state.d
        cx, cy, d1, d2 = h_obj['x'], h_obj['y'], h_obj['d1'], h_obj.get('d2', 0)
        pts2d = []
        if h_obj['type'] == '圓孔':
            r = max(d1 / 2, 0.1)
            for deg in range(0, 361, 15): pts2d.append((cx + r*math.cos(math.radians(deg)), cy + r*math.sin(math.radians(deg))))
        else:
            pts2d = [(cx-d1/2, cy-d2/2), (cx+d1/2, cy-d2/2), (cx+d1/2, cy+d2/2), (cx-d1/2, cy+d2/2), (cx-d1/2, cy-d2/2)]

        px, py, pz = [], [] ,[]
        for lx, ly in pts2d:
            if face == '正面':   rx, ry, rz = -W/2 + lx, -H/2, ly
            elif face == '背面': rx, ry, rz = W/2 - lx, H/2, ly
            elif face == '左面': rx, ry, rz = -W/2, H/2 - lx, ly
            elif face == '右面': rx, ry, rz = W/2, -H/2 + lx, ly
            elif face == '頂面': rx, ry, rz = -W/2 + lx, -H/2 + ly, D
            elif face == '底面': rx, ry, rz = -W/2 + lx, H/2 - ly, 0
            else: continue
            px.append(rx); py.append(ry); pz.append(rz)
        return px, py, pz

    def render(self):
        text_scale = max(1.0, float(getattr(self.state, 'ui_text_scale', 1.0) or 1.0))
        try: elev, azim = self.ax3d.elev, self.ax3d.azim
        except AttributeError: elev, azim = 30, -45

        self.ax3d.clear(); self.ax2d.clear(); self.ax2d.axis('off')
        w, h, d = self.state.w, self.state.h, self.state.d
        all_x, all_y, all_z = [0], [0], [0]

        # 共用擠出繪圖函式，大幅簡化邏輯
        def draw_extrusion(u, z, ext1, ext2, axis_flag, active_flag, f_color, e_color, shift_y=0):
            if not u: return
            xc, yc, zc, xe, ye, ze = [], [], [], [], [], []
            for i in range(len(u)):
                if axis_flag == 'X':
                    xc.append(u[i]); yc.append(ext1 + shift_y); zc.append(z[i])
                    xe.append(u[i]); ye.append(ext2 + shift_y); ze.append(z[i])
                else:
                    xc.append(ext1); yc.append(u[i] + shift_y); zc.append(z[i])
                    xe.append(ext2); ye.append(u[i] + shift_y); ze.append(z[i])
                    
            self.ax3d.plot(xc, yc, zc, color=e_color, linewidth=2.5)
            self.ax3d.plot(xe, ye, ze, color=e_color, linewidth=2.5)
            for i in range(len(xc)): self.ax3d.plot([xc[i], xe[i]], [yc[i], ye[i]], [zc[i], ze[i]], color='#94a3b8', linestyle=':', linewidth=1.5)

            verts = []
            for i in range(len(xc)-1): 
                verts.append([(xc[i], yc[i], zc[i]), (xc[i+1], yc[i+1], zc[i+1]), (xe[i+1], ye[i+1], ze[i+1]), (xe[i], ye[i], ze[i])])
            
            a_val = self.state.alpha_bend if active_flag else self.state.alpha_bend * 0.7
            self.ax3d.add_collection3d(Poly3DCollection(verts, alpha=a_val, facecolor=f_color, edgecolor=e_color, linewidths=0.5))
            all_x.extend(xc + xe); all_y.extend(yc + ye); all_z.extend(zc + ze)

        # ★ 繪製主體 (根據模式自動切換)
        if self.state.struct_mode == 'standard':
            ux, zx, bx = self.calc_profile(self.state.profiles['X'])
            uy, zy, by = self.calc_profile(self.state.profiles['Y'])
            draw_extrusion(ux, zx, -by/2, by/2, 'X', self.state.active_bend == 'X', '#3b82f6', '#1e40af')
            if self.state.enable_y:
                draw_extrusion(uy, zy, -bx/2, bx/2, 'Y', self.state.active_bend == 'Y', '#10b981', '#047857')
        else:
            # 金庫模式
            ux, zx, _ = self.calc_profile(self.state.profiles_vault['箱身'])
            uy1, zy1, _ = self.calc_profile(self.state.profiles_vault['封頭'])
            uy2, zy2, _ = self.calc_profile(self.state.profiles_vault['封尾'])
            
            # 箱身 (藍色)：沿 Y 軸 (深度) 擠出
            draw_extrusion(ux, zx, -h/2, h/2, 'X', self.state.active_bend == '箱身', '#3b82f6', '#1e40af')
            # 封頭 (綠色)：配置在 Y 軸最前端
            draw_extrusion(uy1, zy1, -w/2, w/2, 'Y', self.state.active_bend == '封頭', '#10b981', '#047857', shift_y=-h/2)
            # 封尾 (青色)：配置在 Y 軸最末端
            draw_extrusion(uy2, zy2, -w/2, w/2, 'Y', self.state.active_bend == '封尾', '#0ea5e9', '#0369a1', shift_y=h/2)

        # 繪製半透明空間外框與開孔
        box_faces = {
            '正面': [(-w/2, -h/2, 0), (w/2, -h/2, 0), (w/2, -h/2, d), (-w/2, -h/2, d)],
            '背面': [(w/2, h/2, 0), (-w/2, h/2, 0), (-w/2, h/2, d), (w/2, h/2, d)],
            '左面': [(-w/2, h/2, 0), (-w/2, -h/2, 0), (-w/2, -h/2, d), (-w/2, h/2, d)],
            '右面': [(w/2, -h/2, 0), (w/2, h/2, 0), (w/2, h/2, d), (w/2, -h/2, d)],
            '頂面': [(-w/2, -h/2, d), (w/2, -h/2, d), (w/2, h/2, d), (-w/2, h/2, d)],
            '底面': [(-w/2, h/2, 0), (w/2, h/2, 0), (w/2, -h/2, 0), (-w/2, -h/2, 0)]
        }

        for face, holes in self.state.holes.items():
            if not self.state.enable_y and face not in ['正面', '背面'] and self.state.struct_mode == 'standard': continue
            is_active = (face == self.state.active_face)
            
            if is_active or len(holes) > 0:
                 f_alpha = self.state.alpha_face if is_active else self.state.alpha_face * 0.5
                 f_color = '#cbd5e1' if is_active else 'gray'
                 poly = Poly3DCollection([box_faces[face]], alpha=f_alpha, facecolor=f_color, edgecolor='none')
                 self.ax3d.add_collection3d(poly)
            
            for hole in holes:
                hx, hy, hz = self.get_hole_3d(face, hole)
                self.ax3d.plot(hx, hy, hz, color='red' if is_active else '#475569', linewidth=2.5 if is_active else 1.5)

        self.ax3d.plot([0], [0], [0], marker='+', color='black', markersize=10)
        max_b = max(max(all_x)-min(all_x), max(all_y)-min(all_y), max(all_z)-min(all_z)) if len(all_x)>1 else 100
        if max_b == 0: max_b = 100
        self.ax3d.set_xlim(-max_b/2, max_b/2); self.ax3d.set_ylim(-max_b/2, max_b/2); self.ax3d.set_zlim(0, max_b)
        self.ax3d.view_init(elev=elev, azim=azim)
        self.ax3d.tick_params(axis='both', labelsize=9*text_scale)
        self.ax3d.zaxis.set_tick_params(labelsize=9*text_scale)

        # -----------------------------------
        # 2. 2D 展開圖渲染
        # -----------------------------------
        face = self.state.active_face
        fw, fh = w, d
        if face in ['頂面', '底面']: fw, fh = w, h
        elif face in ['左面', '右面']: fw, fh = h, d

        self.ax2d.plot([0, fw, fw, 0, 0], [0, 0, fh, fh, 0], color='black', linewidth=2)
        oy, ox = -fh*0.1, -fw*0.1
        self.ax2d.annotate('', xy=(0, oy), xytext=(fw, oy), arrowprops=dict(arrowstyle='<|-|>', color='gray'))
        self.ax2d.text(fw/2, oy*1.8, f"W = {fw}", ha='center', va='top', fontsize=10*text_scale, fontweight='bold')
        self.ax2d.annotate('', xy=(ox, 0), xytext=(ox, fh), arrowprops=dict(arrowstyle='<|-|>', color='gray'))
        self.ax2d.text(ox*1.8, fh/2, f"H = {fh}", ha='right', va='center', rotation=90, fontsize=10*text_scale, fontweight='bold')

        for hole in self.state.holes[face]:
            cx, cy, d1, d2 = hole['x'], hole['y'], hole['d1'], hole.get('d2', 0)
            if hole['type'] == '圓孔':
                self.ax2d.add_patch(patches.Circle((cx, cy), max(d1/2, 0.1), edgecolor='red', facecolor='none', linewidth=2))
            else:
                self.ax2d.add_patch(patches.Rectangle((cx-d1/2, cy-d2/2), max(d1, 0.1), max(d2, 0.1), edgecolor='red', facecolor='none', linewidth=2))
            cs = max(fw, fh) * 0.03
            self.ax2d.plot([cx-cs, cx+cs], [cy, cy], color='blue', linewidth=1)
            self.ax2d.plot([cx, cx], [cy-cs, cy+cs], color='blue', linewidth=1)
            self.ax2d.text(cx+cs, cy+cs, f"({cx},{cy})", color='blue', fontsize=8*text_scale)

        self.ax2d.set_aspect('equal') 
        self.ax2d.set_xlim(ox*4, fw - ox*2); self.ax2d.set_ylim(oy*4, fh - oy*2)
        self.ax2d.set_title(f"【{face}】 CAD 展開標註圖", color='#b91c1c', fontweight='bold', fontsize=12*text_scale)
        self.canvas.draw()

# ==========================================
# 模組 3：折彎介面 (BendingUI) 
# ==========================================
class BendingUI:
    def __init__(self, parent, state, update_cb):
        self.state = state; self.update_cb = update_cb
        self.nb = ttk.Notebook(parent); self.nb.pack(fill=tk.X, pady=5)
        self.nb.bind("<<NotebookTabChanged>>", self.on_tab)
        self.container = ttk.Frame(parent); self.container.pack(fill=tk.BOTH, expand=True)
        self.controls = []; self.entry_grid = []; self.tabs = []
        self.rebuild_tabs()

    def rebuild_tabs(self):
        """根據結構模式動態重建分頁"""
        for tab in self.nb.tabs(): self.nb.forget(tab)
        self.tabs.clear()
        
        if self.state.struct_mode == 'standard':
            keys = ['X', 'Y']
            labels = [" X 軸折彎 ", " Y 軸折彎 "]
        else:
            keys = ['箱身', '封頭', '封尾']
            labels = [" 📦 箱身 ", " 🧢 封頭 ", " 🧢 封尾 "]
            
        for k, lbl in zip(keys, labels):
            self.nb.add(ttk.Frame(self.nb), text=lbl)
            self.tabs.append(k)
            
        if self.state.active_bend not in self.tabs:
            self.state.active_bend = self.tabs[0]
            
        self.nb.select(self.tabs.index(self.state.active_bend))
        self.render()

    def get_active_dict(self):
        return self.state.profiles if self.state.struct_mode == 'standard' else self.state.profiles_vault

    def on_tab(self, e):
        idx = self.nb.index("current")
        if 0 <= idx < len(self.tabs):
            self.state.active_bend = self.tabs[idx]
            self.render(); self.update_cb()

    def apply_mirror(self, idx, key):
        if not self.state.symmetric: return
        try:
            val = get_int(self.controls[idx][key].get())
            m_idx = len(self.controls) - 1 - idx if key == 'len' else len(self.controls) - 2 - idx
            if 0 <= m_idx < len(self.controls) and m_idx != idx and key in self.controls[m_idx]:
                self.controls[m_idx][key].set(str(val))
        except: pass
        self.save(); self.update_cb()

    def navigate_grid(self, event, r, c):
        key = event.keysym; max_r = len(self.entry_grid) - 1
        if key == "Up" and r > 0: (self.entry_grid[r-1][c] or self.entry_grid[r-1][1]).focus_set()
        elif key == "Down" and r < max_r: (self.entry_grid[r+1][c] or self.entry_grid[r+1][1]).focus_set()
        elif key == "Left" and c == 1: self.entry_grid[r][0].focus_set()
        elif key == "Right" and c == 0: self.entry_grid[r][1].focus_set()

    def render(self):
        for w in self.container.winfo_children(): w.destroy()
        self.controls.clear(); self.entry_grid.clear()
        segs = self.get_active_dict()[self.state.active_bend]

        ttk.Button(self.container, text="⬆️ 新增前折", command=lambda: self.add(0)).grid(row=0, column=0, columnspan=7, pady=5)
        
        for i, seg in enumerate(segs):
            ttk.Label(self.container, text=f"{i+1}.").grid(row=i+1, column=0)
            ctrl = {}; row_entries = [None, None]

            if i < len(segs) - 1:
                ttk.Label(self.container, text="折角:").grid(row=i+1, column=1)
                ang_var = tk.StringVar(value=str(get_int(seg.get('angle', 0))))
                e1 = ttk.Entry(self.container, textvariable=ang_var, width=5)
                e1.grid(row=i+1, column=2)
                bind_overwrite(e1)
                e1.bind("<Up>", lambda e, r=i, c=0: self.navigate_grid(e, r, c))
                e1.bind("<Down>", lambda e, r=i, c=0: self.navigate_grid(e, r, c))
                e1.bind("<Left>", lambda e, r=i, c=0: self.navigate_grid(e, r, c))
                e1.bind("<Right>", lambda e, r=i, c=0: self.navigate_grid(e, r, c))
                ang_var.trace_add("write", lambda *a, idx=i: self.apply_mirror(idx, 'angle'))
                ctrl['angle'] = ang_var
                row_entries[0] = e1

            ttk.Label(self.container, text="長度:").grid(row=i+1, column=3)
            len_var = tk.StringVar(value=str(get_int(seg['len'])))
            e2 = ttk.Entry(self.container, textvariable=len_var, width=5)
            e2.grid(row=i+1, column=4)
            bind_overwrite(e2)
            e2.bind("<Up>", lambda e, r=i, c=1: self.navigate_grid(e, r, c))
            e2.bind("<Down>", lambda e, r=i, c=1: self.navigate_grid(e, r, c))
            e2.bind("<Left>", lambda e, r=i, c=1: self.navigate_grid(e, r, c))
            e2.bind("<Right>", lambda e, r=i, c=1: self.navigate_grid(e, r, c))
            len_var.trace_add("write", lambda *a, idx=i: self.apply_mirror(idx, 'len'))
            ctrl['len'] = len_var
            row_entries[1] = e2

            ttk.Button(self.container, text="刪除", width=4, command=lambda idx=i: self.remove(idx)).grid(row=i+1, column=6, padx=5)
            self.controls.append(ctrl)
            self.entry_grid.append(row_entries)

        ttk.Button(self.container, text="⬇️ 新增後折", command=lambda: self.add(-1)).grid(row=len(segs)+1, column=0, columnspan=7, pady=5)

    def save(self):
        new_segs = []
        for ctrl in self.controls:
            l = get_int(ctrl['len'].get())
            if 'angle' in ctrl: new_segs.append({'len': l, 'angle': get_int(ctrl['angle'].get())})
            else: new_segs.append({'len': l})
        self.get_active_dict()[self.state.active_bend] = new_segs

    def add(self, pos):
        self.save(); segs = self.get_active_dict()[self.state.active_bend]
        if pos == 0: segs.insert(0, {'angle': 90, 'len': 50})
        else:
            if segs: segs[-1]['angle'] = -90
            segs.append({'len': 50})
        self.render(); self.update_cb()

    def remove(self, idx):
        self.save(); segs = self.get_active_dict()[self.state.active_bend]
        segs.pop(idx)
        if segs and 'angle' in segs[-1]: del segs[-1]['angle']
        self.render(); self.update_cb()

# ==========================================
# 模組 4：開孔介面 (HolesUI)
# ==========================================
class HolesUI:
    def __init__(self, parent, state, update_cb):
        self.state = state; self.update_cb = update_cb
        self.nb = ttk.Notebook(parent); self.nb.pack(fill=tk.X, pady=5)
        for f in self.state.faces: self.nb.add(ttk.Frame(self.nb), text=f" {f} ")
        self.nb.bind("<<NotebookTabChanged>>", self.on_tab)
        self.container = ttk.Frame(parent); self.container.pack(fill=tk.BOTH, expand=True)
        self.controls = []; self.entry_grid = []; self.render()

    def on_tab(self, e):
        self.state.active_face = self.state.faces[self.nb.index("current")]
        self.render(); self.update_cb()

    def navigate_grid(self, event, r, c):
        key = event.keysym; max_r = len(self.entry_grid) - 1
        if key == "Up" and r > 0: self.entry_grid[r-1][c].focus_set()
        elif key == "Down" and r < max_r: self.entry_grid[r+1][c].focus_set()
        elif key == "Left" and c > 0: self.entry_grid[r][c-1].focus_set()
        elif key == "Right" and c < len(self.entry_grid[r]) - 1: self.entry_grid[r][c+1].focus_set()

    def render(self):
        for w in self.container.winfo_children(): w.destroy()
        self.controls.clear(); self.entry_grid.clear()
        holes = self.state.holes[self.state.active_face]
        headers = ["類", "名稱", "X", "Y", "徑/寬", "高(方)"]
        for col, text in enumerate(headers): ttk.Label(self.container, text=text, font=("Arial", 9, "bold")).grid(row=0, column=col, pady=5)

        for i, h in enumerate(holes):
            t_var = tk.StringVar(value=h['type'])
            cb = ttk.Combobox(self.container, textvariable=t_var, values=['圓孔', '方孔'], width=5, state="readonly")
            cb.grid(row=i+1, column=0, padx=2); cb.bind("<<ComboboxSelected>>", lambda e: self.save_and_update())

            n_var = tk.StringVar(value=h.get('name', f'孔{i+1}'))
            e_name = ttk.Entry(self.container, textvariable=n_var, width=8)
            e_name.grid(row=i+1, column=1, padx=2); bind_overwrite(e_name)

            v_dict = {'x': tk.StringVar(value=str(h['x'])), 'y': tk.StringVar(value=str(h['y'])), 'd1': tk.StringVar(value=str(h['d1'])), 'd2': tk.StringVar(value=str(h.get('d2',0)))}
            row_entries = []
            
            for col_idx, key in enumerate(['x', 'y', 'd1', 'd2'], start=2):
                e = ttk.Entry(self.container, textvariable=v_dict[key], width=5)
                e.grid(row=i+1, column=col_idx, padx=2); bind_overwrite(e)
                e.bind("<Up>", lambda event, r=i, c=col_idx-2: self.navigate_grid(event, r, c))
                e.bind("<Down>", lambda event, r=i, c=col_idx-2: self.navigate_grid(event, r, c))
                e.bind("<Left>", lambda event, r=i, c=col_idx-2: self.navigate_grid(event, r, c))
                e.bind("<Right>", lambda event, r=i, c=col_idx-2: self.navigate_grid(event, r, c))
                v_dict[key].trace_add("write", lambda *a: self.save_and_update())
                row_entries.append(e)

            ttk.Button(self.container, text="刪除", width=4, command=lambda idx=i: self.remove(idx)).grid(row=i+1, column=6, padx=5)
            v_dict['type'], v_dict['name'] = t_var, n_var
            self.controls.append(v_dict); self.entry_grid.append(row_entries)

        ttk.Button(self.container, text="➕ 新增開孔", command=self.add).grid(row=len(holes)+1, column=0, columnspan=7, pady=10)

    def save_and_update(self):
        new_holes = []
        for c in self.controls: new_holes.append({'type': c['type'].get(), 'name': c['name'].get(), 'x': get_int(c['x'].get()), 'y': get_int(c['y'].get()), 'd1': get_int(c['d1'].get()), 'd2': get_int(c['d2'].get())})
        self.state.holes[self.state.active_face] = new_holes
        self.update_cb()

    def add(self):
        self.save_and_update()
        self.state.holes[self.state.active_face].append({'type': '圓孔', 'name': '新孔', 'x': 50, 'y': 50, 'd1': 20, 'd2': 0})
        self.render(); self.update_cb()

    def remove(self, idx):
        self.save_and_update()
        self.state.holes[self.state.active_face].pop(idx)
        self.render(); self.update_cb()

# ==========================================
# 模組 5：主程式控制器 (MainApp)
# ==========================================
class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("雙重架構設計系統：標準型與金庫型")
        self.root.geometry("1450x1000")
        
        try:
            if os.path.exists("mycad.ico"): self.root.iconbitmap("mycad.ico")
        except Exception: pass

        self.state = AppState(); self._job = None
        self.left = ttk.Frame(root, width=550, padding=10); self.left.pack(side=tk.LEFT, fill=tk.Y)
        self.right = ttk.Frame(root, padding=10); self.right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(8, 9))
        # Some embedded/test harnesses can reload matplotlib.projections after
        # mplot3d was first imported. Re-register at the point of use so a
        # standalone Phase6 designer cold-start always owns the 3D projection.
        register_projection(Axes3D)
        gs = self.fig.add_gridspec(2, 1, height_ratios=[2, 1], hspace=0.3)
        self.renderer = Renderer(self.fig.add_subplot(gs[0], projection='3d'), self.fig.add_subplot(gs[1]), self.state, FigureCanvasTkAgg(self.fig, master=self.right))
        self.renderer.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 1. 空間與連動約束
        f_top = ttk.LabelFrame(self.left, text="📦 結構模式與空間約束", padding=5); f_top.pack(fill=tk.X, pady=5)
        self.v_w, self.v_h, self.v_d = tk.StringVar(value=str(self.state.w)), tk.StringVar(value=str(self.state.h)), tk.StringVar(value=str(self.state.d))
        self.v_sy, self.v_ey = tk.BooleanVar(value=self.state.symmetric), tk.BooleanVar(value=self.state.enable_y)

        r1 = ttk.Frame(f_top); r1.pack(fill=tk.X)
        for lbl, var in zip(["W:", "H:", "D:"], [self.v_w, self.v_h, self.v_d]):
            ttk.Label(r1, text=lbl).pack(side=tk.LEFT)
            e = ttk.Entry(r1, textvariable=var, width=5)
            e.pack(side=tk.LEFT, padx=(0,10)); bind_overwrite(e)
        
        r2 = ttk.Frame(f_top); r2.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(r2, text="對稱折彎", variable=self.v_sy).pack(side=tk.LEFT, padx=(0,10))
        ttk.Checkbutton(r2, text="啟用 Y 軸面", variable=self.v_ey).pack(side=tk.LEFT, padx=(0,10))
        
        ttk.Separator(r2, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # ★ 雙重架構模式切換 (Radio Buttons)
        ttk.Label(r2, text="結構:").pack(side=tk.LEFT, padx=(0,5))
        self.v_mode = tk.StringVar(value=self.state.struct_mode)
        ttk.Radiobutton(r2, text="標準十字型", variable=self.v_mode, value='standard').pack(side=tk.LEFT, padx=(0,5))
        ttk.Radiobutton(r2, text="金庫型(三件)", variable=self.v_mode, value='vault').pack(side=tk.LEFT)

        for v in [self.v_w, self.v_h, self.v_d, self.v_sy, self.v_ey]: v.trace_add("write", self.queue_update)
        self.v_mode.trace_add("write", self.on_mode_change)

        # 2. 3D 視覺調整
        f_vis = ttk.LabelFrame(self.left, text="👁️ 3D 視覺調整", padding=5); f_vis.pack(fill=tk.X, pady=5)
        self.v_a_bend = tk.DoubleVar(value=self.state.alpha_bend); self.v_a_face = tk.DoubleVar(value=self.state.alpha_face)
        ttk.Label(f_vis, text="折彎透視:").grid(row=0, column=0, sticky='e', padx=5, pady=2)
        ttk.Scale(f_vis, from_=0.1, to=1.0, variable=self.v_a_bend, command=self.queue_update).grid(row=0, column=1, sticky='ew')
        ttk.Label(f_vis, text="面板透視:").grid(row=1, column=0, sticky='e', padx=5, pady=2)
        ttk.Scale(f_vis, from_=0.0, to=1.0, variable=self.v_a_face, command=self.queue_update).grid(row=1, column=1, sticky='ew')
        f_vis.columnconfigure(1, weight=1)

        # 3. 模組分頁
        self.main_nb = ttk.Notebook(self.left); self.main_nb.pack(fill=tk.BOTH, expand=True, pady=10)
        tab1, tab2 = ttk.Frame(self.main_nb), ttk.Frame(self.main_nb)
        self.main_nb.add(tab1, text=" ⚙️ 模組一：折彎路徑 "); self.main_nb.add(tab2, text=" 🔲 模組二：六面開孔 ")
        
        self.bend_ui = BendingUI(tab1, self.state, self.queue_update)
        self.holes_ui = HolesUI(tab2, self.state, self.queue_update)
        self.do_update()

    def on_mode_change(self, *args):
        self.state.struct_mode = self.v_mode.get()
        self.bend_ui.rebuild_tabs()  # 自動切換 X/Y 或 箱身/封頭/封尾 標籤
        self.queue_update()

    def queue_update(self, *args):
        if self._job: self.root.after_cancel(self._job)
        self._job = self.root.after(50, self.do_update)

    def do_update(self):
        self.state.w, self.state.h, self.state.d = get_int(self.v_w.get()), get_int(self.v_h.get()), get_int(self.v_d.get())
        self.state.symmetric, self.state.enable_y = self.v_sy.get(), self.v_ey.get()
        self.state.alpha_bend = self.v_a_bend.get(); self.state.alpha_face = self.v_a_face.get()
        self.renderer.render()

if __name__ == "__main__":
    auto_generate_ico()
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()