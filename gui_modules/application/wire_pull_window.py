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
        self._draft_edits = {}
        self._confirmed_inputs = None
        self._saved_export = None
        self._position_readback = ('', '')
        self._size_readback = ('', '', '')
        self._options = api.wire_pull_default_hole_options()
        left = ttk.Frame(self.window, padding=12)
        left.pack(side='left', fill='y')
        right = ttk.Frame(self.window, padding=12)
        right.pack(side='right', fill='both', expand=True)
        ttk.Label(left, text='尺寸／料長（mm）').grid(row=0, column=0, columnspan=2, sticky='w')
        for row, (key, label) in enumerate(DIMENSIONS + DISTANCES, 1):
            ttk.Label(left, text=label).grid(row=row, column=0, sticky='w', pady=2)
            value = getattr(self._options.defaults, key, '')
            self.fields[key] = tk.StringVar(self.window, value=str(value))
            ttk.Entry(left, textvariable=self.fields[key], width=13).grid(row=row, column=1, sticky='ew', pady=2)
        row = len(DIMENSIONS + DISTANCES) + 1
        ttk.Label(left, text='平板封頭尾 INSERT 零間隙\n外蓋四邊 1 mm；厚向貼合').grid(row=row, column=0, columnspan=2, sticky='w', pady=5)
        for index, (key, label) in enumerate(FLAGS):
            var = self.flags[key] = tk.BooleanVar(self.window, value=getattr(self._options, key))
            ttk.Checkbutton(left, text=label, variable=var).grid(row=row+1+index//2, column=index%2, sticky='w')
        self.reset_defaults_button = ttk.Button(left, text='恢復出廠預設', command=self.reset_factory_defaults)
        self.reset_defaults_button.grid(row=row+3, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        self.status = tk.StringVar(self.window, value='請輸入包外及兩側折邊料長；尚未確認。')
        self.part_var = tk.StringVar(self.window)
        self.part_selector = ttk.Combobox(right, textvariable=self.part_var, state='readonly')
        self.part_selector.pack(fill='x')
        self.part_selector.bind('<<ComboboxSelected>>', lambda e: self._draw_part())
        self.canvas = tk.Canvas(right, bg='#20252b', highlightthickness=0, height=120)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self._draw_part())
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
        for var in (*self.fields.values(), *self.flags.values()):
            var.trace_add('write', self._invalidate_preview)

    def reset_factory_defaults(self):
        defaults = api.wire_pull_default_hole_options().defaults
        for key, _ in DISTANCES:
            self.fields[key].set(str(getattr(defaults, key)))
        self.status.set('已恢復六項孔距出廠預設，請重新預覽／確認。')

    def _invalidate_preview(self, *_):
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
        spec = WirePullBoxSpec(**{key: float(self.fields[key].get()) for key, _ in DIMENSIONS},
                               head_form='flat', tail_form='flat')
        options = replace(self._options,
                          defaults=replace(self._options.defaults, **{
                              key: float(self.fields[key].get()) for key, _ in DISTANCES}),
                          **{key: var.get() for key, var in self.flags.items()})
        return spec, options, dict(self._draft_edits)

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
            proposal = api.propose_wire_pull_holes(spec, options, **edits)
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
            proposal = api.propose_wire_pull_holes(spec, options, **edits)
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
            proposal = api.propose_wire_pull_holes(spec, options, **edits)
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
            proposal = api.propose_wire_pull_holes(spec, options, **edits)
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
        self._close_mesh()
        self.physical = None
        self.proposal, self.renders = proposal, renders
        self._show_proposal_choices(proposal)
        labels = tuple(PART_LABELS.get(key, key) for key, _ in renders)
        self.part_selector.configure(values=labels)
        if self.part_var.get() not in labels:
            self.part_var.set(labels[0] if labels else '')
        self._draw_part()
        self.status.set(f'Engine 預覽：{len(proposal.members)} 個孔特徵；出圖須確認並儲存。')

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
            proposal = api.propose_wire_pull_holes(spec, options, **edits)
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
        self._mesh_window.title('標準拉線箱｜同源 3D 預覽')
        self._mesh_window.transient(self.window)
        figure = Figure(figsize=(6, 5))
        self.axis = figure.add_subplot(111, projection='3d')
        colors = {'box_body': '#8195ad', 'head': '#adbcc9', 'tail': '#adbcc9', 'lid': '#607e99'}
        for part in physical.parts:
            self.axis.add_collection3d(gridless_mesh_collection(
                part.world_triangles, facecolor=colors.get(part.part_key, '#8195ad'), opacity=1.0))
        self.axis.set_xlim(*physical.outside_bounds[0])
        self.axis.set_ylim(*physical.outside_bounds[1])
        self.axis.set_zlim(*physical.outside_bounds[2])
        self.axis.view_init(elev=20, azim=35, vertical_axis='y')
        self.axis.set_xlabel('X (mm)')
        self.axis.set_ylabel('Y (mm)')
        self.axis.set_zlabel('Z (mm)')
        self.axis.set_box_aspect(tuple(hi-lo for lo, hi in physical.outside_bounds))  # display scaling only
        view = FigureCanvasTkAgg(figure, master=self._mesh_window)
        view.get_tk_widget().pack(fill='both', expand=True)
        view.draw()

    def confirm(self):
        if not self.preview():
            return
        try:
            snapshot = api.build_wire_pull_project_snapshot(self.proposal.spec, self.proposal)
            self.controller.confirm_designer(snapshot)
            self._retain_edits(self.proposal)
            self._confirmed_inputs = deepcopy(self._source())
            self.status.set('已確認設定；儲存專案後可申請正式出圖。')
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set(str(exc))

    def _restore(self, proposal, renders):
        for key, _ in DIMENSIONS:
            self.fields[key].set(str(float(getattr(proposal.spec, key))))
        for key, _ in DISTANCES:
            self.fields[key].set(str(float(getattr(proposal.options.defaults, key))))
        for key, var in self.flags.items():
            var.set(getattr(proposal.options, key))
        self._retain_edits(proposal)
        self._show(proposal, renders)
        self._confirmed_inputs = deepcopy(self._source())
        self.status.set('已還原確認的專案來源；正式出圖須以已存來源驗證。')

    def cancel(self):
        snapshot = self.controller.committed_snapshot()
        if snapshot is None:
            self._draft_edits = {}
            for key, _ in DIMENSIONS:
                self.fields[key].set('')
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
                self.status.set('已儲存確認的專案；未確認變更不寫入。')
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
