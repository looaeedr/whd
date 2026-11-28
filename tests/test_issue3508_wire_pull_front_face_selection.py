"""P2 front selection is a view-only transaction over the P1 Engine result."""
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import ezdxf
from matplotlib.colors import to_rgba
from mpl_toolkits.mplot3d import proj3d
import pytest

from ae_engine import WirePullBoxSpec, manufacturing_api as api
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def _fingerprints(folder):
    return {p.name: (sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in folder.iterdir() if p.is_file()}


def _choose(root, win, index):
    win._mesh_face_selector.current(index)
    win._mesh_face_selector.event_generate('<<ComboboxSelected>>')
    root.update()


def _click_face(root, win, face):
    # Project a point on the real Engine face onto the existing TkAgg canvas;
    # no fake artist hit, direct selection callback or substituted mesh.
    u0, v0, u1, v1 = face.flat_bounds
    point = tuple(a + (u1-u0)/2*b + (v1-v0)/2*c for a, b, c in
                  zip(face.world_origin, face.u_direction, face.v_direction))
    axis = win.axis
    view = axis.figure.canvas
    x, y, _ = proj3d.proj_transform(*point, axis.get_proj())
    x, y = axis.transData.transform((x, y))
    widget = view.get_tk_widget()
    x, y = round(x), widget.winfo_height()-round(y)
    widget.event_generate('<ButtonPress-1>', x=x, y=y)
    widget.event_generate('<ButtonRelease-1>', x=x, y=y)
    root.update()


@pytest.mark.requires_tk_display
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_front_face_list_3d_cancel_and_p1_source_unchanged(tmp_path, monkeypatch):
    import gui
    spec = WirePullBoxSpec(637, 411, 223, 3)
    hole = CircleFeature(4., FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(400., 200.),
                         source_type='MANUAL_TEST')
    mark = replace(hole, layer='MARKING', diameter=2., offset=Vec2(420., 220.))
    manual = (('box_body', (hole, mark)),)
    proposal = api.propose_wire_pull_holes(spec, manual=manual)
    assert not proposal.conflicts
    assert {member.kind for member in proposal.members} == {'fixed', 'seal', 'anchor'}
    source_topology = api.resolve_standard_cabinet_topology(spec)
    topology = api.confirm_wire_pull_hole_topology(spec, proposal, manual=proposal.manual)
    assert tuple(p.part_key for p in topology.parts) == ('box_body', 'head', 'tail', 'lid')
    assert topology.joint_graph == source_topology.joint_graph
    assert not topology.manufacturing_verified
    front = topology.part('lid').mounting_faces[0]
    assert (front.part_key, front.face_id) == ('lid', 'outer')
    assert {j.joint_id for j in topology.joints if j.joint_id.startswith('lid:')} == {
        'lid:front_left_return', 'lid:front_right_return'}
    # Existing P1 project and its four admitted saved-source DXFs are fixtures,
    # not a new export grant. Reopen each before operating any selection.
    snapshot = api.build_wire_pull_project_snapshot(spec, proposal)
    project = write_project(tmp_path/'wire.p6fold', {'schema': PROJECT_SCHEMA, 'snapshot': snapshot})
    project_bytes = project.read_bytes()
    saved_source = api.inspect_wire_pull_saved_export(project, expected_snapshot=snapshot)
    assert saved_source.manufacturing_blocker is None
    out = tmp_path/'existing_output'
    result = api.save_wire_pull_saved_project_dxf(
        project, out, expected_source_sha256=saved_source.source_sha256)
    for key, path in result.items():
        doc = ezdxf.readfile(path)
        assert doc.header['$INSUNITS'] == 4 and not doc.audit().errors
        assert api.verify_saved_part_render_data_dxf(topology.part(key).render_data, path).ok
    old = _fingerprints(out)
    assert len(old) == 4
    print('BEFORE DXF SHA256/mtime:', old)
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root)
        root.update()
        monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: str(project))
        host.fold_designer_app.project_file_menu.invoke(0)
        root.update()
        win = host.wire_pull_window
        assert win.window.winfo_viewable()
        assert win.proposal == proposal
        assert win.controller.committed_snapshot() == snapshot
        old_source = win._source()
        old_witness = win._saved_export
        old_part = win.part_var.get()
        old_group = win.group_var.get()
        old_member = win.member_var.get()
        win.view3d_button.invoke()
        root.update()
        assert win.physical == topology
        assert len(win.axis.collections) == 4
        old_artists = tuple(win.axis.collections)
        old_artist = old_artists[-1]
        base_color = old_artist.get_facecolor()[0].copy()
        assert tuple(win._mesh_face_selector['values']) == ('未選取', '前面（既有外蓋）')
        assert win._mesh_selected_cover_face is None
        assert win._mesh_face_selector.current() == 0
        # List -> existing physical lid artist, not a newly rendered plate.
        _choose(root, win, 1)
        assert win._mesh_selected_cover_face == (front.part_key, front.face_id)
        assert win.axis.collections[-1] is old_artist
        assert tuple(old_artist.get_facecolor()[0]) == pytest.approx(to_rgba('#e8ad42'))
        win._mesh_cancel_face_button.invoke()
        root.update()
        assert win._mesh_selected_cover_face is None
        assert win._mesh_face_selector.current() == 0
        assert tuple(old_artist.get_facecolor()[0]) == pytest.approx(tuple(base_color))
        # Real click -> list. Confirm updates only the session's selection;
        # cancelling a later deselection returns to the previous front choice.
        _click_face(root, win, front)
        assert win._mesh_selected_cover_face == ('lid', 'outer')
        assert win._mesh_face_selector.current() == 1
        win._mesh_confirm_face_button.invoke()
        _choose(root, win, 0)
        assert win._mesh_selected_cover_face is None
        win._mesh_cancel_face_button.invoke()
        root.update()
        assert win._mesh_selected_cover_face == ('lid', 'outer')
        assert win._mesh_face_selector.current() == 1
        # A back-facing box_body hit is not silently promoted to a front lid.
        _choose(root, win, 0)
        rear = next(f for f in topology.part('box_body').mounting_faces if f.face_id == 'rear')
        win.axis.view_init(elev=20, azim=215, vertical_axis='y')
        win.axis.figure.canvas.draw()
        _click_face(root, win, rear)
        assert win._mesh_selected_cover_face is None
        assert win._mesh_face_selector.current() == 0
        win._mesh_cancel_face_button.invoke()
        root.update()
        assert win._mesh_selected_cover_face == ('lid', 'outer')
        # No source mutation or extra part, bend, hole, marking, export grant.
        assert win._source() == old_source
        assert win.proposal == proposal and win.proposal.manual == proposal.manual
        assert win.physical == topology
        assert tuple(win.axis.collections) == old_artists
        assert win.controller.committed_snapshot() == snapshot
        assert win._saved_export is old_witness
        assert (win.part_var.get(), win.group_var.get(), win.member_var.get()) == (
            old_part, old_group, old_member)
        assert project.read_bytes() == project_bytes
        assert read_project(project)['snapshot'] == snapshot
        assert api.inspect_wire_pull_saved_export(project, expected_snapshot=snapshot) == saved_source
        after = api.confirm_wire_pull_hole_topology(win.proposal.spec, win.proposal, manual=win.proposal.manual)
        assert after == topology
        assert not after.manufacturing_verified
        with pytest.raises(ValueError, match='CABINET_FAMILY_NOT_IMPLEMENTED'):
            api.save_part_render_data_dxf(after.part('lid').render_data, Path(result['lid']), overwrite=True)
        assert _fingerprints(out) == old
        print('AFTER DXF SHA256/mtime:', _fingerprints(out))
        # Close an unconfirmed view-only change; opening again restores baseline.
        _choose(root, win, 0)
        win._close_mesh()
        win.view3d_button.invoke()
        root.update()
        assert win._mesh_selected_cover_face == ('lid', 'outer')
        # Change the actual source: old view/selection is no longer applicable.
        win.fields['width'].set('638')
        root.update()
        assert win._mesh_window is None
        assert win._confirmed_cover_face is None
        assert win.controller.committed_snapshot() == snapshot
        assert _fingerprints(out) == old
    finally:
        root.destroy()
