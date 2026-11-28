"""Standard wire-pull operator preview; Engine owns every physical result."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ae_engine import manufacturing_api as api
from ae_engine.contracts import WirePullBoxSpec
from gui_modules.drawing import render_drawing_scene
from gui_modules.rendering.transforms import phase6_2d_material_viewport
from phase6_project_controller import Phase6ProjectController
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

DIMENSIONS = (
    ('width', 'W 包外寬'), ('height', 'H 包外高'), ('depth', 'D 包外深'),
    ('thickness', 'T 板厚'), ('left_return_material_mm', '左內折料長'),
    ('right_return_material_mm', '右內折料長'),
)
ENDCAP_DIMENSIONS = tuple(
    (f'{role}_{edge}_material_mm', f'{label}{side}折料')
    for role, label in (('head', '封頭'), ('tail', '封尾'))
    for edge, side in (('left', '左'), ('right', '右'), ('bottom', '下'))
)
SOURCE_DIMENSIONS = DIMENSIONS + ENDCAP_DIMENSIONS
DISTANCES = (
    ('fixed_pitch', '固定孔最大中心距'), ('seal_offset', '封印距角'),
    ('anchor_break', '壁虎距邊分界'), ('anchor_near', '壁虎第一級距邊'),
    ('anchor_far', '壁虎第二級距邊'), ('anchor_extra', '壁虎增孔門檻'),
)
FLAGS = (('fixed', '固定孔'), ('seal', '封印孔'), ('anchor', '壁虎孔'),
         ('opposite_diagonal', '封印換對角'))
HOLE_KINDS = {'固定孔': 'fixed', '封印孔': 'seal', '壁虎孔': 'anchor'}
PART_LABELS = {'box_body':'箱身', 'head':'封頭', 'tail':'封尾', 'lid':'外蓋'}


class WirePullWindow:
    def __init__(self, host):
        self.controller = Phase6ProjectController(read_project=read_project,
                                                  write_project=write_project,
                                                  schema=PROJECT_SCHEMA)
        self.window = tk.Toplevel(host.root)
        self.window.title('標準拉線箱｜第一型')
        self.window.geometry('1050x680')
        self.window.minsize(850, 590)
        self.window.transient(host.root)
        self.window.protocol('WM_DELETE_WINDOW', self.window.destroy)
        self.fields = {}
        self.flags = {}
        self.proposal = None
        self.renders = ()
        self.physical = None
        self.axis = None
        # View-only selection; never part of a proposal or saved project.
        self._confirmed_cover_face = None
        self._draft_edits = {}
        self._confirmed_inputs = None
        self._saved_export = None
        self._position_readback = ('', '')
        self._size_readback = ('', '', '')
        self._options = api.wire_pull_default_hole_options()
        self._endcap_forms = (WirePullBoxSpec.head_form, WirePullBoxSpec.tail_form)
        left = ttk.Frame(self.window, padding=(8, 6))
        left.pack(side='left', fill='y')
        right = ttk.Frame(self.window, padding=12)
        right.pack(side='right', fill='both', expand=True)
        ttk.Label(left, text='尺寸／料長（mm）').grid(row=0, column=0, columnspan=2, sticky='w')
        for row, (key, label) in enumerate(DIMENSIONS + DISTANCES, 1):
            ttk.Label(left, text=label).grid(row=row, column=0, sticky='w', pady=0)
            value = getattr(self._options.defaults, key, getattr(WirePullBoxSpec, key, ''))
            self.fields[key] = tk.StringVar(self.window, value=str(value))
            ttk.Entry(left, textvariable=self.fields[key], width=13).grid(row=row, column=1, sticky='ew', pady=0)
        row = len(DIMENSIONS + DISTANCES) + 1
        fold_fields = ttk.Frame(left)
        fold_fields.grid(row=row, column=0, columnspan=2, sticky='ew')
        for role_index, label in enumerate(('封頭', '封尾')):
            ttk.Label(fold_fields, text=label+' 左／右／下').grid(row=role_index, column=0, sticky='w')
            for j, (key, _) in enumerate(ENDCAP_DIMENSIONS[role_index*3:role_index*3+3]):
                var = self.fields[key] = tk.StringVar(self.window, value=str(getattr(WirePullBoxSpec,key)))
                ttk.Entry(fold_fields, textvariable=var, width=5).grid(row=role_index, column=j+1, padx=1)
        row += 1
        self.endcap_status = tk.StringVar(self.window, value='封頭尾上折跟箱身邊框；正式出圖須經 Engine 驗證\nINSERT 零間隙；外蓋四邊 1 mm')
        ttk.Label(left, textvariable=self.endcap_status).grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        for index, (key, label) in enumerate(FLAGS):
            var = self.flags[key] = tk.BooleanVar(self.window, value=getattr(self._options, key))
            ttk.Checkbutton(left, text=label, variable=var).grid(row=row+1+index//2, column=index%2, sticky='w')
        self.reset_defaults_button = ttk.Button(left, text='恢復出廠預設', command=self.reset_factory_defaults)
        self.reset_defaults_button.grid(row=row+3, column=0, columnspan=2, sticky='ew', pady=(2, 0))
        self.status = tk.StringVar(self.window, value='請輸入包外及兩側折邊料長；尚未確認。')
        self.part_var = tk.StringVar(self.window)
        self.part_selector = ttk.Combobox(right, textvariable=self.part_var, state='readonly')
        self.part_selector.pack(fill='x')
        self.part_selector.bind('<<ComboboxSelected>>', lambda e: self._draw_part())
        self.canvas = tk.Canvas(right, bg='#20252b', highlightthickness=0, height=120)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self._draw_part())
        rear = ttk.LabelFrame(right, text='後側開口（mm；座標由 Engine 後側面定義）', padding=(4, 2))
        rear.pack(fill='x', pady=(4, 0))
        self.rear_opening_enabled = tk.BooleanVar(self.window, value=False)
        ttk.Checkbutton(rear, text='在箱身後面設定開口', variable=self.rear_opening_enabled).pack(side='left')
        self.rear_face_bounds = tk.StringVar(self.window, value='請先載入或輸入尺寸並預覽')
        ttk.Label(rear, textvariable=self.rear_face_bounds).pack(side='left', padx=5)
        self.rear_opening_fields = {}
        for key, label in (('left', 'U左'), ('bottom', 'V下'), ('right', 'U右'), ('top', 'V上')):
            ttk.Label(rear, text=label).pack(side='left')
            var = self.rear_opening_fields[key] = tk.StringVar(self.window)
            ttk.Entry(rear, textvariable=var, width=8).pack(side='left', padx=2)
        edit = ttk.Frame(right)
        edit.pack(fill='x', pady=(6, 0))
        ttk.Label(edit, text='孔組／XY(mm)').pack(side='left')
        self.group_var = tk.StringVar(self.window)
        self.group_selector = ttk.Combobox(edit, textvariable=self.group_var, state='readonly', width=18)
        self.group_selector.pack(side='left', padx=3)
        self.group_selector.bind('<<ComboboxSelected>>', lambda e: self._show_group_position())
        self.position = {axis: tk.StringVar(self.window) for axis in ('X', 'Y')}
        for axis, var in self.position.items():
            ttk.Label(edit, text=axis).pack(side='left')
            ttk.Entry(edit, textvariable=var, width=7).pack(side='left', padx=2)
        group_actions = ttk.Frame(right)
        group_actions.pack(fill='x', pady=(4, 0))
        self.move_button = ttk.Button(group_actions, text='移動孔組', command=self.move_group)
        self.move_button.pack(side='left', padx=3)
        self.remove_button = ttk.Button(group_actions, text='刪除孔組', command=self.remove_group)
        self.remove_button.pack(side='left', padx=2)
        self.group_faces = tk.StringVar(self.window)
        ttk.Label(group_actions, textvariable=self.group_faces, wraplength=360).pack(side='left', padx=3)
        add = ttk.Frame(right)
        add.pack(fill='x', pady=(4, 0))
        self.add_button = ttk.Button(add, text='新增孔組', command=self.add_group)
        self.add_button.pack(side='left')
        ttk.Label(add, text='用上方 XY').pack(side='left', padx=2)
        self.add_kind_var = tk.StringVar(self.window, value='固定孔')
        self.add_kind_selector = ttk.Combobox(add, textvariable=self.add_kind_var,
                                             values=tuple(HOLE_KINDS), state='readonly', width=8)
        self.add_kind_selector.pack(side='left', padx=3)
        ttk.Label(add, text='實體面').pack(side='left')
        self.add_face_var = tk.StringVar(self.window)
        self.add_face_selector = ttk.Combobox(add, textvariable=self.add_face_var,
                                             state='readonly', width=14)
        self.add_face_selector.pack(side='left', padx=3)
        size = ttk.Frame(right)
        size.pack(fill='x', pady=(4, 0))
        ttk.Label(size, text='孔組內實體板件').pack(side='left')
        self.member_var = tk.StringVar(self.window)
        self.member_selector = ttk.Combobox(size, textvariable=self.member_var,
                                            state='readonly', width=10)
        self.member_selector.pack(side='left', padx=3)
        self.member_selector.bind('<<ComboboxSelected>>', lambda e: self._show_member_size())
        self.size_button = ttk.Button(size, text='套用孔尺寸', command=self.resize_member, state='disabled')
        self.size_button.pack(side='left', padx=3)
        size_values = ttk.Frame(right)
        size_values.pack(fill='x', pady=(2, 0))
        self.size_fields, self.size_entries = {}, {}
        for key, label in (('diameter', 'Ø'), ('slot_width', '槽寬'), ('slot_length', '槽總長')):
            var = self.size_fields[key] = tk.StringVar(self.window)
            ttk.Label(size_values, text=label).pack(side='left')
            entry = self.size_entries[key] = ttk.Entry(size_values, textvariable=var, width=6, state='disabled')
            entry.pack(side='left', padx=2)
        choices = ttk.Frame(right)
        choices.pack(fill='x')
        ttk.Label(choices, text='避讓候選').pack(side='left')
        self.alternative_var = tk.StringVar(self.window)
        self.alternative_selector = ttk.Combobox(choices, textvariable=self.alternative_var, state='readonly', width=39)
        self.alternative_selector.pack(side='left', padx=3)
        self.choose_button = ttk.Button(choices, text='選用候選', command=self.choose_alternative)
        self.choose_button.pack(side='left')
        ttk.Label(right, textvariable=self.status, wraplength=680).pack(fill='x', pady=6)
        actions = ttk.Frame(right)
        actions.pack(fill='x')
        for index, (attr, label, command) in enumerate((
            ('preview_button','預覽 2D', self.preview), ('view3d_button','預覽 3D', self.view3d),
            ('confirm_button','確認設定', self.confirm), ('cancel_button','取消變更', self.cancel),
            ('save_button','儲存專案', self.save), ('save_as_button','另存新檔', lambda: self.save(save_as=True)),
            ('open_button','開啟專案', self.open),
            ('export_button','正式出圖 DXF', self.export_dxf),
        )):
            button = ttk.Button(actions, text=label, command=command)
            setattr(self, attr, button)
            button.grid(row=index//4, column=index%4, sticky='ew', padx=2, pady=2)
        self._mesh_window = None
        for var in (*self.fields.values(), *self.flags.values(), self.rear_opening_enabled,
                     *self.rear_opening_fields.values()):
            var.trace_add('write', self._invalidate_preview)

    def reset_factory_defaults(self):
        defaults = api.wire_pull_default_hole_options().defaults
        for key, _ in DISTANCES:
            self.fields[key].set(str(getattr(defaults, key)))
        self.status.set('已恢復六項孔距出廠預設，請重新預覽／確認。')

    def _invalidate_preview(self, *_):
        self._confirmed_cover_face = None
        self.proposal = None
        self.renders = ()
        self.physical = None
        self.canvas.delete('all')
        self.group_selector.configure(values=())
        self.group_var.set('')
        self.add_face_selector.configure(values=())
        self.add_face_var.set('')
        self._show_group_position()
        self.alternative_selector.configure(values=())
        self.alternative_var.set('')
        self._close_mesh()
        self.status.set('設定已變更，請重新預覽／確認。')

    def _close_mesh(self):
        if self._mesh_window is not None and self._mesh_window.winfo_exists():
            self._mesh_window.destroy()
        self._mesh_window = None
        self.axis = None

    def _source(self):
        spec = WirePullBoxSpec(**{key: float(self.fields[key].get()) for key, _ in SOURCE_DIMENSIONS},
                               head_form=self._endcap_forms[0], tail_form=self._endcap_forms[1])
        options = replace(self._options,
                          defaults=replace(self._options.defaults, **{
                              key: float(self.fields[key].get()) for key, _ in DISTANCES}),
                          **{key: var.get() for key, var in self.flags.items()})
        edits = dict(self._draft_edits)
        bounds = None
        if self.rear_opening_enabled.get():
            values = tuple(self.rear_opening_fields[key].get().strip()
                           for key in ('left', 'bottom', 'right', 'top'))
            if not all(values):
                raise ValueError('WIRE_PULL_REAR_OPENING_BOUNDS_REQUIRED')
            bounds = tuple(float(value) for value in values)
        edits['_rear_opening_bounds'] = bounds
        return spec, options, edits

    def _propose(self, spec, options, edits):
        edits = dict(edits)
        bounds = edits.pop('_rear_opening_bounds', None)
        return api.propose_wire_pull_holes_with_rear_opening(
            spec, options, flat_bounds=bounds, **edits)

    def _show_rear_face_bounds(self, spec):
        try:
            rear = next(face for face in api.resolve_standard_cabinet_topology(spec).part('box_body').mounting_faces
                        if face.face_id == 'rear')
            left, bottom, right, top = rear.flat_bounds
            self.rear_face_bounds.set('Engine rear 範圍：U %.3f…%.3f；V %.3f…%.3f'
                                      % (left, right, bottom, top))
        except (ValueError, TypeError, StopIteration):
            self.rear_face_bounds.set('尺寸有效後顯示 Engine 後側面範圍')

    def _retain_edits(self, proposal):
        self._draft_edits = {key: getattr(proposal, key) for key in
                             ('manual', 'overrides', 'additions', 'removed', 'sizes')}

    def _show_group_position(self):
        members = tuple(m for m in self.proposal.members if m.group_id == self.group_var.get()) if self.proposal else ()
        if members:
            for axis, value in zip(('X', 'Y'), members[0].world):
                self.position[axis].set(str(value))
        else:
            for var in self.position.values():
                var.set('')
        self._position_readback = tuple(var.get() for var in self.position.values())
        self.group_faces.set(' / '.join(f'{PART_LABELS.get(m.part_key, m.part_key)}：{m.face_id}' for m in members))
        keys = tuple(m.part_key for m in members)
        self.member_selector.configure(values=keys)
        if self.member_var.get() not in keys:
            self.member_var.set(keys[0] if keys else '')
        self._show_member_size()

    def _show_member_size(self):
        for key, var in self.size_fields.items():
            var.set('')
            self.size_entries[key].configure(state='disabled')
        self.size_button.configure(state='disabled')
        self._size_readback = tuple(var.get() for var in self.size_fields.values())
        if self.proposal is None or not self.group_var.get() or not self.member_var.get():
            return
        try:
            current = api.wire_pull_hole_member_size(self.proposal, self.group_var.get(), self.member_var.get())
        except ValueError as exc:
            self.status.set(str(exc))
            return
        for key, var in self.size_fields.items():
            value = getattr(current, key)
            if value is not None:
                var.set(str(value))
                self.size_entries[key].configure(state='normal')
        self.size_button.configure(state='normal')
        self._size_readback = tuple(var.get() for var in self.size_fields.values())

    def _show_proposal_choices(self, proposal):
        groups = tuple(dict.fromkeys(m.group_id for m in proposal.members))
        self.group_selector.configure(values=groups)
        if self.group_var.get() not in groups:
            self.group_var.set(groups[0] if groups else '')
        self._show_group_position()
        topology = api.resolve_standard_cabinet_topology(proposal.spec)
        faces = tuple(f.face_id for f in topology.part('box_body').mounting_faces)
        self.add_face_selector.configure(values=faces)
        if self.add_face_var.get() not in faces:
            self.add_face_var.set('')
        labels = tuple(f'{a.group_id}  X={a.xy[0]:g} Y={a.xy[1]:g}' for a in proposal.alternatives)
        self.alternative_selector.configure(values=labels)
        self.alternative_var.set('')

    def _present_candidate(self, proposal):
        if proposal.conflicts:
            self._close_mesh()
            self.physical = None
            self.renders = ()
            self.proposal = proposal
            self.canvas.delete('all')
            self._show_proposal_choices(proposal)
            self.status.set('WIRE_PULL_HOLE_CONFLICT: ' + '; '.join(proposal.conflicts))
            return False
        renders = api.confirm_wire_pull_holes(proposal.spec, proposal, manual=proposal.manual)
        self._show(proposal, renders)
        return True

    def move_group(self):
        if self.proposal is None or not self.group_var.get():
            self.status.set('請先預覽並選擇孔組。')
            return
        try:
            spec, options, edits = self._source()
            moves = dict(self.proposal.overrides)
            moves[self.group_var.get()] = tuple(float(self.position[a].get()) for a in ('X', 'Y'))
            edits['overrides'] = tuple(moves.items())
            proposal = self._propose(spec, options, edits)
            self._present_candidate(proposal)
            self._retain_edits(proposal)
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set(str(exc))

    def add_group(self):
        if self.proposal is None:
            self.status.set('請先預覽，再選孔類、實體面及 XY。')
            return
        try:
            spec, options, edits = self._source()
            kind = HOLE_KINDS.get(self.add_kind_var.get())
            if kind is None or not getattr(options, kind):
                raise ValueError('WIRE_PULL_HOLE_KIND_DISABLED_OR_UNSUPPORTED')
            face = self.add_face_var.get()
            if not face:
                raise ValueError('WIRE_PULL_HOLE_FACE_SOURCE_REQUIRED')
            group = 'added:' + kind + ':' + uuid4().hex
            addition = api.make_wire_pull_hole_addition(group, kind, face,
                              tuple(float(self.position[a].get()) for a in ('X', 'Y')))
            edits['additions'] = (*self.proposal.additions, addition)
            proposal = self._propose(spec, options, edits)
            self.group_var.set(group)
            self._present_candidate(proposal)
            self._retain_edits(proposal)
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set(str(exc))

    def remove_group(self):
        if self.proposal is None or not any(m.group_id == self.group_var.get() for m in self.proposal.members):
            self.status.set('WIRE_PULL_HOLE_GROUP_SOURCE_REQUIRED')
            return
        try:
            spec, options, edits = self._source()
            edits['removed'] = (*self.proposal.removed, self.group_var.get())
            proposal = self._propose(spec, options, edits)
            self._present_candidate(proposal)
            self._retain_edits(proposal)
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set(str(exc))

    def resize_member(self):
        if self.proposal is None:
            self.status.set('WIRE_PULL_HOLE_MEMBER_SOURCE_REQUIRED')
            return
        try:
            group, part = self.group_var.get(), self.member_var.get()
            current = api.wire_pull_hole_member_size(self.proposal, group, part)
            values = {}
            for key, var in self.size_fields.items():
                if getattr(current, key) is not None:
                    values[key] = float(var.get())
                elif var.get():
                    raise ValueError('WIRE_PULL_HOLE_SIZE_OVERRIDE_KIND_MISMATCH')
            spec, options, edits = self._source()
            override = api.make_wire_pull_hole_size_override(group, part, **values)
            sizes = {(s.group_id, s.part_key): s for s in self.proposal.sizes}
            sizes[(group, part)] = override
            edits['sizes'] = tuple(sizes.values())
            proposal = self._propose(spec, options, edits)
            self._present_candidate(proposal)
            self._retain_edits(proposal)
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set(str(exc))

    def choose_alternative(self):
        index = self.alternative_selector.current()
        if self.proposal is None or index < 0:
            self.status.set('請先選擇 Engine 避讓候選。')
            return
        try:
            current = self.proposal
            proposal = api.choose_wire_pull_hole_alternative(current.spec, current,
                              current.alternatives[index], manual=current.manual)
            self._present_candidate(proposal)
            self._retain_edits(proposal)
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set(str(exc))

    def _show(self, proposal, renders):
        if self.proposal != proposal:
            self._confirmed_cover_face = None
        self._close_mesh()
        self.physical = None
        self.proposal, self.renders = proposal, renders
        self._show_proposal_choices(proposal)
        labels = tuple(PART_LABELS.get(key, key) for key, _ in renders)
        self.part_selector.configure(values=labels)
        if self.part_var.get() not in labels:
            self.part_var.set(labels[0] if labels else '')
        self._draw_part()
        self.status.set(f'Engine 預覽：{len(proposal.members)} 個孔特徵；{self._cap_preview_label()}。')

    def _cap_preview_label(self):
        return '舊平板退修核對，非加工' if 'flat' in self._endcap_forms else '四折封頭尾；正式出圖依已儲存來源驗證'

    def _draw_part(self):
        self.canvas.delete('all')
        for key, render in self.renders:
            if PART_LABELS.get(key, key) == self.part_var.get():
                transform, *_ = phase6_2d_material_viewport(
                    render.material.bounds, self.canvas.winfo_width(), self.canvas.winfo_height(),
                    top_gutter=24, right_gutter=24, bottom_gutter=24, left_gutter=24)
                render_drawing_scene(self.canvas, render.scene, transform)
                break

    def preview(self):
        try:
            spec, options, edits = self._source()
            self._show_rear_face_bounds(spec)
            proposal = self._propose(spec, options, edits)
            return self._present_candidate(proposal)
        except (ValueError, TypeError, OverflowError) as exc:
            self._invalidate_preview()
            self.status.set(str(exc))
            return False

    def view3d(self):
        if self.proposal is None and not self.preview():
            return
        try:
            proposal = self.proposal
            physical = api.confirm_wire_pull_hole_topology(proposal.spec, proposal, manual=proposal.manual)
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set(str(exc))
            return
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from phase6_final_scene_mesh_display import gridless_mesh_collection
        self._close_mesh()
        self.physical = physical
        self._mesh_window = tk.Toplevel(self.window)
        self._mesh_window.title('標準拉線箱｜3D '+self._cap_preview_label())
        self._mesh_window.transient(self.window)
        figure = Figure(figsize=(6, 5))
        self.axis = figure.add_subplot(111, projection='3d')
        colors = {'box_body': '#8195ad', 'head': '#adbcc9', 'tail': '#adbcc9', 'lid': '#607e99'}
        artists = {}
        for part in physical.parts:
            artist = gridless_mesh_collection(
                part.world_triangles, facecolor=colors.get(part.part_key, '#8195ad'), opacity=1.0)
            self.axis.add_collection3d(artist)
            artists[part.part_key] = artist
        self.axis.set_xlim(*physical.outside_bounds[0])
        self.axis.set_ylim(*physical.outside_bounds[1])
        self.axis.set_zlim(*physical.outside_bounds[2])
        self.axis.view_init(elev=20, azim=35, vertical_axis='y')
        self.axis.set_xlabel('X (mm)')
        self.axis.set_ylabel('Y (mm)')
        self.axis.set_zlabel('Z (mm)')
        self.axis.set_box_aspect(tuple(hi-lo for lo, hi in physical.outside_bounds))  # display scaling only
        view = FigureCanvasTkAgg(figure, master=self._mesh_window)
        self._bind_cover_face_selection(physical, artists, colors, view)
        view.get_tk_widget().pack(fill='both', expand=True)
        view.draw()

    def _bind_cover_face_selection(self, physical, artists, colors, view):
        """Select the existing front lid from the confirmed Engine projection only."""
        window, axis = self._mesh_window, self.axis
        window.protocol('WM_DELETE_WINDOW', self._close_mesh)
        # The P1 public topology already returns lid/outer. No fabricated
        # opening plane or additional face; unsupported faces are not choices.
        lid = physical.part('lid')
        face = next((f for f in lid.mounting_faces
                     if f.part_key == lid.part_key and f.face_id == 'outer'), None)
        identity = (face.part_key, face.face_id) if face is not None else None
        toolbar = ttk.Frame(window, padding=(6, 4))
        toolbar.pack(fill='x')
        ttk.Label(toolbar, text='蓋板面（僅選取）').pack(side='left')
        labels = ('未選取', '前面（既有外蓋）') if identity is not None else ('未選取',)
        self._mesh_face_var = tk.StringVar(window, value=labels[0])
        self._mesh_face_selector = ttk.Combobox(toolbar, textvariable=self._mesh_face_var,
                                                values=labels, state='readonly', width=18)
        self._mesh_face_selector.pack(side='left', padx=4)
        selected = self._confirmed_cover_face if self._confirmed_cover_face == identity else None
        baseline = selected
        self._mesh_selected_cover_face = selected

        def live():
            return self._mesh_window is window and self.axis is axis

        def select(value):
            if not live() or (value is not None and value != identity):
                return
            self._mesh_selected_cover_face = value
            self._mesh_face_var.set(labels[1] if value is not None else labels[0])
            artist = artists[lid.part_key]
            artist.set_facecolor('#e8ad42' if value is not None else colors[lid.part_key])
            view.draw_idle()

        def from_list(_event):
            select(identity if self._mesh_face_selector.current() == 1 else None)

        def confirm_selection():
            nonlocal baseline
            if live():
                baseline = self._mesh_selected_cover_face
                self._confirmed_cover_face = baseline

        def cancel_selection():
            select(baseline)

        self._mesh_face_selector.bind('<<ComboboxSelected>>', from_list)
        self._mesh_confirm_face_button = ttk.Button(toolbar, text='確認選取', command=confirm_selection)
        self._mesh_confirm_face_button.pack(side='left', padx=2)
        self._mesh_cancel_face_button = ttk.Button(toolbar, text='取消選取', command=cancel_selection)
        self._mesh_cancel_face_button.pack(side='left', padx=2)
        press = None

        def on_press(event):
            nonlocal press
            press = ((event.x, event.y) if live() and event.inaxes is axis
                     and event.button == 1 else None)

        def on_release(event):
            nonlocal press
            start, press = press, None
            if (not live() or identity is None or start is None
                    or event.inaxes is not axis or event.button != 1
                    or abs(event.x-start[0]) > 4 or abs(event.y-start[1]) > 4):
                return
            # Same display hit-test approach as the existing FinalScene 3D
            # Hole Editor: use projected artist paths and draw-time z-order.
            hits = [(artist.get_zorder(), index, key)
                    for index, (key, artist) in enumerate(artists.items())
                    if artist.get_visible() and artist.axes is axis and artist.contains(event)[0]]
            if hits and max(hits)[2] == lid.part_key:
                select(identity)

        view.mpl_connect('button_press_event', on_press)
        view.mpl_connect('button_release_event', on_release)
        select(selected)

    def confirm(self):
        if not self.preview():
            return
        try:
            snapshot = api.build_wire_pull_project_snapshot(self.proposal.spec, self.proposal)
            self.controller.confirm_designer(snapshot)
            self._retain_edits(self.proposal)
            self._confirmed_inputs = deepcopy(self._source())
            self.status.set('已確認設定；'+self._cap_preview_label()+'。')
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set(str(exc))

    def _restore(self, proposal, renders):
        # Only replay the saved form, never infer or migrate a cap shape.
        self._endcap_forms = (proposal.spec.head_form, proposal.spec.tail_form)
        self.endcap_status.set(self._cap_preview_label()+"\nINSERT 零間隙；外蓋四邊 1 mm")
        for key, _ in SOURCE_DIMENSIONS:
            self.fields[key].set(str(float(getattr(proposal.spec, key))))
        for key, _ in DISTANCES:
            self.fields[key].set(str(float(getattr(proposal.options.defaults, key))))
        for key, var in self.flags.items():
            var.set(getattr(proposal.options, key))
        rear_bounds = api.wire_pull_rear_opening_bounds(proposal)
        self.rear_opening_enabled.set(rear_bounds is not None)
        for key, value in zip(('left', 'bottom', 'right', 'top'), rear_bounds or ('', '', '', '')):
            self.rear_opening_fields[key].set('' if value == '' else str(value))
        self._show_rear_face_bounds(proposal.spec)
        self._retain_edits(proposal)
        self._show(proposal, renders)
        self._confirmed_inputs = deepcopy(self._source())
        self.status.set('已還原確認的專案來源；'+self._cap_preview_label()+'。')

    def cancel(self):
        snapshot = self.controller.committed_snapshot()
        if snapshot is None:
            self._draft_edits = {}
            for key, _ in SOURCE_DIMENSIONS:
                self.fields[key].set(str(getattr(WirePullBoxSpec,key,'')))
            for key, _ in DISTANCES:
                self.fields[key].set(str(getattr(self._options.defaults, key)))
            for key, var in self.flags.items():
                var.set(getattr(self._options, key))
            self._invalidate_preview()
            self.status.set('未確認的設定已取消。')
            return
        proposal, renders = api.restore_wire_pull_project_snapshot(snapshot)
        self._restore(proposal, renders)

    def save(self, *, save_as=False):
        snapshot = self.controller.committed_snapshot()
        if snapshot is None:
            self.status.set('尚無確認設定，不能儲存。')
            return
        confirmed_inputs = deepcopy(self._confirmed_inputs)
        epoch = self.controller.project_load_epoch
        initial_path = self.controller.project_path
        path = None if save_as else initial_path
        if not path:
            path = filedialog.asksaveasfilename(parent=self.window, defaultextension='.p6fold',
                    initialfile=Path(self.controller.project_path or '拉線箱.p6fold').name,
                    filetypes=[('Phase6 折彎專案', '*.p6fold')])
        if path:
            try:
                if (self.controller.committed_snapshot() != snapshot
                        or self._confirmed_inputs != confirmed_inputs
                        or self.controller.project_load_epoch != epoch
                        or self.controller.project_path != initial_path):
                    raise ValueError('儲存期間專案已變更，請重新儲存。')
                target = self.controller.save(path, lambda: snapshot)
                self._saved_export = None
                source = api.inspect_wire_pull_saved_export(target, expected_snapshot=snapshot)
                self._saved_export = (Path(target).absolute(), source, deepcopy(snapshot),
                                      confirmed_inputs)
                self.status.set('已儲存專案；未確認變更不寫入。'+self._cap_preview_label()+'。')
            except (OSError, ValueError, TypeError, OverflowError) as exc:
                self.status.set(str(exc))

    def load(self, path, snapshot=None):
        if snapshot is None:
            snapshot = read_project(path)['snapshot']
        # Bind the on-disk revision to the exact snapshot Main Open read,
        # before replacing the current session. Never adopt a newer disk file
        # just because it has a valid standard topology.
        source = api.inspect_wire_pull_saved_export(path, expected_snapshot=snapshot)
        committed, proposal, renders = self.controller.load_wire_pull_preview(path, snapshot=snapshot)
        self._restore(proposal, renders)
        self._saved_export = (Path(path).absolute(), source, deepcopy(committed),
                              deepcopy(self._confirmed_inputs))

    def _assert_saved_export_current(self, witness):
        if witness is None:
            raise ValueError('請先確認並儲存專案，再正式出圖。')
        path, source, snapshot, inputs = witness
        if (not self.window.winfo_exists() or self._saved_export is not witness
                or not self.controller.project_path
                or Path(self.controller.project_path).absolute() != path
                or self.controller.committed_snapshot() != snapshot
                or self._source() != inputs
                or tuple(var.get() for var in self.position.values()) != self._position_readback
                or tuple(var.get() for var in self.size_fields.values()) != self._size_readback):
            raise ValueError('設定或專案已變更，請先確認並儲存，或取消變更。')

    def export_dxf(self):
        witness = self._saved_export
        try:
            self._assert_saved_export_current(witness)
            path, source, snapshot, _ = witness
            if api.inspect_wire_pull_saved_export(path, expected_snapshot=snapshot) != source:
                raise ValueError('WIRE_PULL_SAVED_SOURCE_CHANGED')
            if source.manufacturing_blocker is not None:
                raise ValueError(source.manufacturing_blocker)
            directory = filedialog.askdirectory(parent=self.window, title='選擇正式 DXF 輸出資料夾')
            if not directory:
                self.status.set('已取消出圖。')
                return

            def guard():
                self._assert_saved_export_current(witness)

            def save(overwrite):
                guard()
                return api.save_wire_pull_saved_project_dxf(path, directory,
                    expected_source_sha256=source.source_sha256, overwrite=overwrite,
                    pre_commit_guard=guard)

            try:
                outputs = save(False)
            except FileExistsError:
                if not messagebox.askyesno(parent=self.window, title='覆寫 DXF',
                                           message='輸出 DXF 已存在，是否覆寫？'):
                    self.status.set('已取消覆寫。')
                    return
                outputs = save(True)
            self.status.set(f'正式 DXF 出圖完成：{len(outputs)} 片；{directory}')
        except (OSError, ValueError, TypeError, OverflowError, tk.TclError) as exc:
            self.status.set(str(exc))

    def open(self):
        path = filedialog.askopenfilename(parent=self.window, filetypes=[('Phase6 折彎專案', '*.p6fold')])
        if path:
            try:
                self.load(path)
            except (OSError, ValueError, TypeError, OverflowError) as exc:
                self.status.set(str(exc))


def open_wire_pull_window(host, *, snapshot=None, path=None):
    previous = getattr(host, 'wire_pull_window', None)
    if snapshot is None and previous is not None and previous.window.winfo_exists():
        previous.window.lift()
        return previous
    window = WirePullWindow(host)
    try:
        if snapshot is not None:
            window.load(path, snapshot)
    except Exception:
        window.window.destroy()
        raise
    if previous is not None and previous.window.winfo_exists():
        previous.window.destroy()
    host.wire_pull_window = window
    # Keep legacy Save/DXF commands unreachable during the preview project.
    window.window.update_idletasks()
    window.window.grab_set()
    return window
