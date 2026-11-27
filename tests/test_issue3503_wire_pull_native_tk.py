"""First standard wire-pull operator entry, real Tk and real .p6fold."""
import os
import tkinter as tk
from tkinter import filedialog

import pytest

from ae_engine import manufacturing_api as api, WirePullBoxSpec
from phase6_project_file import read_project


@pytest.mark.requires_tk_display
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_standard_toolbar_preview_confirm_cancel_save_and_reopen(tmp_path, monkeypatch):
    import gui
    path = tmp_path / 'wire.p6fold'
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root)
        root.update()
        old = host.project_controller.committed_snapshot()
        old_path = host.project_controller.project_path
        menu = host.fold_designer_app.project_file_menu
        index = next(i for i in range(menu.index('end')+1)
                     if menu.type(i) == 'command' and menu.entrycget(i, 'label') == '標準拉線箱')
        menu.invoke(index)
        root.update()
        win = host.wire_pull_window
        assert win.window.winfo_viewable()
        assert win.window.grab_current() == win.window
        assert all(win.fields[key].get() == '' for key in ('width','height','depth','thickness','left_return_material_mm','right_return_material_mm'))
        for key, val in dict(width=637, height=1200, depth=223, thickness=3,
                             left_return_material_mm=27, right_return_material_mm=34,
                             fixed_pitch=450, seal_offset=110, anchor_break=1050,
                             anchor_near=110, anchor_far=160, anchor_extra=1850).items():
            win.fields[key].set(str(val))
        win.preview_button.invoke(); root.update()
        assert win.proposal is not None and not win.proposal.conflicts
        assert win.canvas.find_all()
        assert win.controller.committed_snapshot() is None
        win.confirm_button.invoke(); root.update()
        committed = win.controller.committed_snapshot()
        assert committed['model'] == '拉線箱'
        proposal, renders = api.restore_wire_pull_project_snapshot(committed)
        assert proposal.spec == WirePullBoxSpec(637,1200,223,3,27,34,'flat','flat')
        assert vars(proposal.options.defaults) == dict(fixed_pitch=450, seal_offset=110,
            anchor_break=1050, anchor_near=110, anchor_far=160, anchor_extra=1850)
        assert dict(renders) == dict(win.renders)
        win.view3d_button.invoke(); root.update()
        assert win.physical.outside_bounds == ((-318.5,318.5),(-600.,600.),(-111.5,111.5))
        assert win.physical.manufacturing_verified is False
        assert len(win.axis.collections) == 4
        assert win._mesh_window.winfo_viewable()
        assert all(j.clearance_policy == 'ZERO' for j in win.physical.joints)
        win.flags['seal'].set(False)
        win.preview_button.invoke(); root.update()
        assert not any(m.kind == 'seal' for m in win.proposal.members)
        assert win.controller.committed_snapshot() == committed
        win.cancel_button.invoke(); root.update()
        assert win.flags['seal'].get()
        assert any(m.kind == 'seal' for m in win.proposal.members)
        win.fields['width'].set('800')
        win.preview_button.invoke(); root.update()
        assert win.proposal.spec.width == 800
        win.cancel_button.invoke(); root.update()
        assert win.fields['width'].get() == '637.0'
        assert win.controller.committed_snapshot() == committed
        # Drive a conflicting real pair through the Tk edit controls, then
        # explicitly select the Engine-proposed same-face alternative.
        seal = next(m for m in win.proposal.members if m.kind == 'seal' and m.part_key == 'box_body')
        fixed = next(m for m in win.proposal.members if m.kind == 'fixed' and m.face_id == seal.face_id)
        win.group_var.set(seal.group_id)
        win.group_selector.event_generate('<<ComboboxSelected>>')
        for axis, value in zip(('X','Y'), fixed.world):
            win.position[axis].set(str(value))
        win.move_button.invoke(); root.update()
        assert win.proposal.conflicts and win.proposal.alternatives
        assert 'WIRE_PULL_HOLE_CONFLICT' in win.status.get()
        assert win.controller.committed_snapshot() == committed
        win.confirm_button.invoke(); root.update()
        assert win.controller.committed_snapshot() == committed
        win.alternative_selector.current(0)
        alternative = win.proposal.alternatives[0]
        win.choose_button.invoke(); root.update()
        assert not win.proposal.conflicts
        assert win.controller.committed_snapshot() == committed
        assert all(m.world[:2] == alternative.xy for m in win.proposal.members if m.group_id == alternative.group_id)
        win.confirm_button.invoke(); root.update()
        committed = win.controller.committed_snapshot()
        proposal, renders = api.restore_wire_pull_project_snapshot(committed)
        assert proposal.overrides
        assert dict(renders) == dict(win.renders)
        monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **kw:str(path))
        win.save_button.invoke(); root.update()
        assert path.is_file()
        assert read_project(path)['snapshot'] == committed
        assert read_project(path)['final_geometry'] == {}
        saved = path.read_bytes()
        # Editing and invalid confirmation must leave the committed project
        # and file untouched. Closing or cancelling is not an implicit save.
        win.fields['thickness'].set('0')
        win.confirm_button.invoke(); root.update()
        assert 'WIRE_PULL_INVALID_DIMENSION' in win.status.get()
        assert win.controller.committed_snapshot() == committed
        win.cancel_button.invoke(); root.update()
        assert path.read_bytes() == saved
        win.window.destroy(); root.update()
        assert host.project_controller.committed_snapshot() == old
        assert host.project_controller.project_path == old_path
    finally:
        root.destroy()
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root)
        root.update()
        before = host.project_controller.committed_snapshot()
        monkeypatch.setattr(filedialog,'askopenfilename',lambda **kw:str(path))
        host.fold_designer_app.project_file_menu.invoke(0); root.update()
        win = host.wire_pull_window
        assert win.window.winfo_viewable()
        assert win.controller.committed_snapshot() == committed
        assert win.controller.loaded_baseline_snapshot() == committed
        assert win.controller.project_load_epoch == 1
        assert win.proposal == proposal
        assert dict(win.renders) == dict(renders)
        assert host.project_controller.committed_snapshot() == before
        assert host.project_controller.project_path is None
        invalid = tmp_path/'invalid.p6fold'
        invalid.write_text('{bad json', encoding='utf-8')
        monkeypatch.setattr(filedialog,'askopenfilename',lambda **kw:str(invalid))
        win.open_button.invoke(); root.update()
        assert win.controller.committed_snapshot() == committed
        assert win.controller.project_load_epoch == 1
        assert win.controller.project_path == str(path)
        assert dict(win.renders) == dict(renders)
    finally:
        root.destroy()
