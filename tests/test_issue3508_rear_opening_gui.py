from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import tkinter as tk

import pytest

from ae_engine import WirePullBoxSpec, manufacturing_api as api
from ae_engine.contracts import EndCapPartSpec, ManufacturingContext
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application.wire_pull_window import WirePullWindow
from phase6_project_file import PROJECT_SCHEMA, write_project


def _files(path):
    return {item.name: (sha256(item.read_bytes()).hexdigest(), item.stat().st_mtime_ns)
            for item in path.iterdir() if item.is_file()}


def _seed_real_dxfs(path):
    path.mkdir()
    for index, key in enumerate(('box_body', 'head', 'tail', 'lid')):
        mark = CircleFeature(2, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(100, 100), layer='MARKING')
        spec = EndCapPartSpec(width=500 + index * 20, height=600, depth=200, thickness=2,
                              frame_width=25, model_name='金庫型', is_tail=key == 'tail', holes=(mark,))
        render = api.build_part_render_data(spec, ManufacturingContext(resource_root=Path.cwd()))
        output = path / f'{key}.dxf'
        api.save_part_render_data_dxf(render, output, verify_reopen=True)
        assert api.verify_saved_part_render_data_dxf(render, output).ok


@pytest.mark.requires_tk_display
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_rear_opening_gui_confirm_cancel_reopen_preserves_four_dxf(tmp_path, monkeypatch):
    spec = WirePullBoxSpec(637, 411, 223, 3)
    rear = next(face for face in api.resolve_standard_cabinet_topology(spec).part('box_body').mounting_faces
                if face.face_id == 'rear')
    left, bottom, right, top = rear.flat_bounds
    cx, cy = (left + right) / 2, (bottom + top) / 2
    hole = CircleFeature(4, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(cx + 65, cy))
    marking = replace(hole, layer='MARKING', offset=Vec2(cx - 65, cy))
    original = api.propose_wire_pull_holes(spec, manual=(('box_body', (hole, marking)),))
    source = tmp_path / 'source.p6fold'
    write_project(source, {'schema': PROJECT_SCHEMA,
                           'snapshot': api.build_wire_pull_project_snapshot(spec, original)})
    dxf_dir = tmp_path / 'existing-dxf'
    _seed_real_dxfs(dxf_dir)
    before_dxf = _files(dxf_dir)

    root = tk.Tk()
    root.withdraw()
    try:
        host = type('Host', (), {'root': root})()
        window = WirePullWindow(host)
        window.load(source)
        assert window.rear_face_bounds.get().startswith('Engine rear 範圍：')
        assert not window.rear_opening_enabled.get()
        window.rear_opening_enabled.set(True)
        for key, value in zip(('left', 'bottom', 'right', 'top'),
                              (cx - 50, cy - 40, cx + 50, cy + 40)):
            window.rear_opening_fields[key].set(str(value))
        window.confirm()
        confirmed = window.controller.committed_snapshot()
        assert dict(window.proposal.manual)['box_body'][:2] == (hole, marking)
        assert api.wire_pull_rear_opening_bounds(window.proposal) == pytest.approx(
            (cx - 50, cy - 40, cx + 50, cy + 40))

        window.rear_opening_fields['left'].set(str(cx - 45))
        window.preview()
        window.cancel()
        assert window.controller.committed_snapshot() == confirmed
        assert api.wire_pull_rear_opening_bounds(window.proposal) == pytest.approx(
            (cx - 50, cy - 40, cx + 50, cy + 40))

        monkeypatch.setattr('gui_modules.application.wire_pull_window.filedialog.asksaveasfilename',
                            lambda **kwargs: str(source))
        window.save(save_as=True)
        assert window.status.get().startswith('已儲存專案')
        window.window.destroy()
        window = WirePullWindow(host)
        window.load(source)
        assert window.rear_opening_enabled.get()
        assert api.wire_pull_rear_opening_bounds(window.proposal) == pytest.approx(
            (cx - 50, cy - 40, cx + 50, cy + 40))

        monkeypatch.setattr('gui_modules.application.wire_pull_window.filedialog.askdirectory',
                            lambda **kwargs: str(dxf_dir))
        window.export_dxf()
        assert window.status.get() == 'WIRE_PULL_REAR_COVER_JOINT_UNVERIFIED'
        assert _files(dxf_dir) == before_dxf
        window.window.destroy()
    finally:
        root.destroy()


@pytest.mark.requires_tk_display
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_rear_opening_gui_replaces_old_bounds_before_new_dimension_validation(tmp_path):
    old_spec = WirePullBoxSpec(843, 411, 223, 3)
    old_bounds = (970, 150, 1030, 210)
    original = api.propose_wire_pull_holes_with_rear_opening(
        old_spec, flat_bounds=old_bounds)
    source = tmp_path / 'old-opening.p6fold'
    write_project(source, {'schema': PROJECT_SCHEMA,
                           'snapshot': api.build_wire_pull_project_snapshot(old_spec, original)})

    root = tk.Tk()
    root.withdraw()
    try:
        host = type('Host', (), {'root': root})()
        window = WirePullWindow(host)
        window.load(source)
        window.fields['width'].set('637')
        new_bounds = (400, 150, 500, 210)
        for key, value in zip(('left', 'bottom', 'right', 'top'), new_bounds):
            window.rear_opening_fields[key].set(str(value))
        assert window.preview(), window.status.get()
        assert not window.proposal.conflicts
        assert window.proposal.spec.width == 637
        assert api.wire_pull_rear_opening_bounds(window.proposal) == pytest.approx(new_bounds)

        window.confirm()
        committed = window.controller.committed_snapshot()
        window.fields['width'].set('700')
        window.preview()
        window.cancel()
        assert window.controller.committed_snapshot() == committed
        assert window.proposal.spec.width == 637
        assert api.wire_pull_rear_opening_bounds(window.proposal) == pytest.approx(new_bounds)

        window.save()
        window.load(source)
        assert window.proposal.spec.width == 637
        assert api.wire_pull_rear_opening_bounds(window.proposal) == pytest.approx(new_bounds)
        window.window.destroy()
    finally:
        root.destroy()


@pytest.mark.requires_tk_display
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_rear_opening_gui_labels_u_and_v_bounds_in_coordinate_order():
    root = tk.Tk()
    root.withdraw()
    try:
        host = type('Host', (), {'root': root})()
        window = WirePullWindow(host)
        for key, value in dict(width=637, height=411, depth=223, thickness=3,
                               left_return_material_mm=25, right_return_material_mm=25).items():
            window.fields[key].set(str(value))
        assert window.preview(), window.status.get()
        assert 'U 239.000…870.000；V 0.000…411.000' in window.rear_face_bounds.get()
        window.window.destroy()
    finally:
        root.destroy()
