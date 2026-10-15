"""A dense sheet must not rebuild its bend chain for every mesh vertex."""
from functools import partial
import os

import pytest
from shapely.geometry import Point, box

from ae_engine import assembly_geometry as geometry
from ae_engine import assembly_geometry_folded_mesh as folding
from ae_engine.manufacturing_render_data import FoldGuide


def sample():
    material = box(0, 0, 100, 80)
    for x in (30, 50, 70):
        material = material.difference(Point(x, 40).buffer(4, resolution=32))
    x_profile = [{'len': 20, 'angle': 90}, {'len': 60, 'core': 'W'}, {'len': 20}]
    y_profile = [{'len': 15, 'angle': -90}, {'len': 50, 'core': 'D'}, {'len': 15}]
    guides = (FoldGuide('x', 20, 10, 60), FoldGuide('y', 15, 25, 75))
    return material, x_profile, y_profile, guides


@pytest.mark.parametrize('mapped', [False, True])
def test_dense_sheet_prepares_bend_geometry_per_mask_not_per_vertex(monkeypatch, mapped):
    material, xp, yp, guides = sample()
    original = folding._profile_geometry
    calls = []
    def counted(profile, **kwargs):
        calls.append(1)
        return original(profile, **kwargs)
    monkeypatch.setattr(folding, '_profile_geometry', counted)
    monkeypatch.setattr(geometry, '_profile_geometry', counted)
    build = geometry.folded_mesh_with_flat_uv_from_polygon if mapped else folding.folded_mesh_from_polygon
    result = build(material, xp, yp, fold_guides=guides)
    assert len(result) > 100
    # Two axes with at most four enabled-fold masks each, plus base profiles.
    assert len(calls) <= 10, f'{len(calls)} bend-chain builds for {len(result)} triangles'


@pytest.mark.parametrize('mapped', [False, True])
def test_prepared_mapping_preserves_every_uv_vertex_hole_and_finite_bend(monkeypatch, mapped):
    material, xp, yp, guides = sample()
    build = geometry.folded_mesh_with_flat_uv_from_polygon if mapped else folding.folded_mesh_from_polygon
    prepared = build(material, xp, yp, fold_guides=guides)
    def legacy_mapper(profile, *, axis, fold_guides, geometry):
        return partial(folding._profile_map_with_guides, profile=profile, axis=axis, fold_guides=fold_guides)
    monkeypatch.setattr(folding, '_prepare_profile_mapper', legacy_mapper)
    monkeypatch.setattr(geometry, '_prepare_profile_mapper', legacy_mapper)
    reference = build(material, xp, yp, fold_guides=guides)
    assert prepared == reference


@pytest.mark.parametrize('mapped', [False, True])
def test_new_mesh_uses_current_angles_lengths_and_guide_spans(monkeypatch, mapped):
    material, xp, yp, guides = sample()
    build = geometry.folded_mesh_with_flat_uv_from_polygon if mapped else folding.folded_mesh_from_polygon
    before = build(material, xp, yp, fold_guides=guides)
    xp[0]['angle'] = -90
    xp[1]['len'] = 55
    guides = (FoldGuide('x', 20, 30, 50),)
    after = build(material, xp, yp, fold_guides=guides)
    assert after != before
    def legacy_mapper(profile, *, axis, fold_guides, geometry):
        return partial(folding._profile_map_with_guides, profile=profile, axis=axis, fold_guides=fold_guides)
    monkeypatch.setattr(folding, '_prepare_profile_mapper', legacy_mapper)
    monkeypatch.setattr(geometry, '_prepare_profile_mapper', legacy_mapper)
    assert after == build(material, xp, yp, fold_guides=guides)


@pytest.fixture
def _receiving_switch_deadlock_guard(monkeypatch):
    """Fail an unattended modal or stalled real-Tk operation with its stage."""
    import faulthandler
    import signal
    from tkinter import messagebox

    stage = {"name": "initialize"}
    def checkpoint(name):
        stage["name"] = name
        print("WHD_SWITCH_STAGE=" + name, flush=True)

    def unexpected_dialog(*args, **kwargs):
        raise AssertionError(
            f"unexpected interactive dialog at {stage['name']}: "
            f"args={args!r} kwargs={kwargs!r}"
        )
    for name in ("showwarning", "showerror", "showinfo", "askyesno",
                 "askokcancel", "askretrycancel", "askquestion"):
        monkeypatch.setattr(messagebox, name, unexpected_dialog)

    # Dump the true Tk/Python stack even if the main thread is inside Tcl.
    faulthandler.dump_traceback_later(40, repeat=False)
    alarm_available = hasattr(signal, "SIGALRM")
    previous_handler = signal.getsignal(signal.SIGALRM) if alarm_available else None
    if alarm_available:
        def on_timeout(_signal, _frame):
            raise TimeoutError("WHD_SWITCH_STALLED at " + stage["name"])
        signal.signal(signal.SIGALRM, on_timeout)
        signal.alarm(120)
    try:
        yield checkpoint
    finally:
        faulthandler.cancel_dump_traceback_later()
        if alarm_available:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_real_family_and_single_multi_switch_bound_bend_work_and_preserve_sheets(tmp_path, monkeypatch, _receiving_switch_deadlock_guard):
    import hashlib
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    import phase6_manufacturing_service as service
    from phase6_project_file import PROJECT_SCHEMA_V2, write_project
    from phase6_receiving_modes import fresh_receiving_mode

    _receiving_switch_deadlock_guard('create Tk/root and host')
    root = tk.Tk()
    host = gui.Phase6PrimaryApplication(root)
    path = write_project(tmp_path / 'latency.p6fold', {
        'schema': PROJECT_SCHEMA_V2,
        'snapshot': fresh_receiving_mode('quantity', {'w': 800, 'h': 1600, 'd': 350, 't': 2}),
    })
    try:
        _receiving_switch_deadlock_guard('load saved Receiving project')
        app = host.load_phase6_project(path)
        _receiving_switch_deadlock_guard('first Tk event loop update')
        root.update()
        counts = {'bends': 0, 'solve': 0}
        original_geometry, original_solve = folding._profile_geometry, service.resolve
        def count_geometry(*args, **kwargs):
            counts['bends'] += 1
            return original_geometry(*args, **kwargs)
        def count_solve(*args, **kwargs):
            counts['solve'] += 1
            return original_solve(*args, **kwargs)
        monkeypatch.setattr(folding, '_profile_geometry', count_geometry)
        monkeypatch.setattr(geometry, '_profile_geometry', count_geometry)
        monkeypatch.setattr(service, 'resolve', count_solve)
        def signature():
            digest = hashlib.sha256()
            for part in app._phase6_last_resolved_manufacturing_geometry.parts:
                digest.update(part.part_key.encode())
                pieces = getattr(part.render_data, 'pieces', ())
                renders = [p.render_data for p in pieces] if pieces else [part.render_data]
                for render in renders:
                    digest.update(render.material.wkb)
                    digest.update(repr(tuple(render.scene.primitives)).encode())
                    digest.update(repr(tuple(render.fold_guides)).encode())
            return digest.hexdigest()
        _receiving_switch_deadlock_guard('hash manufacturing geometry')
        receiving = signature()
        for mode, opener in [('set_bay', bridge._phase6_open_receiving_multi_settings),
                             ('quantity', bridge._phase6_open_receiving_single_settings)]:
            counts.update(bends=0, solve=0)
            _receiving_switch_deadlock_guard('open Receiving mode ' + mode)
            window = opener(app)
            _receiving_switch_deadlock_guard('Tk update after mode ' + mode)
            root.update()
            assert app.designer_workspace.active_mode == mode
            assert counts['bends'] < 1000, counts
            assert counts['solve'] <= 1, counts
            assert signature() == receiving
            _receiving_switch_deadlock_guard('close mode ' + mode)
            window._receiving_multi_close()
            root.update()
            assert root.grab_current() is None
        for family in ['金庫型', '受電箱']:
            counts.update(bends=0, solve=0)
            _receiving_switch_deadlock_guard('switch family to ' + family)
            app.baseline_model_var.set(family)
            _receiving_switch_deadlock_guard('Tk update after family ' + family)
            root.update()
            assert counts['bends'] < 1000, counts
            assert counts['solve'] <= 1, counts
            assert app._phase6_input_snapshot['model'] == family
            assert (signature() == receiving) == (family == '受電箱')
    finally:
        _receiving_switch_deadlock_guard('destroy root')
        root.destroy()
