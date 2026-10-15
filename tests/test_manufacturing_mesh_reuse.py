"""Exact local mesh reuse, with changes and solve lifetime as hard boundaries."""
from dataclasses import replace

import pytest
from shapely.geometry import Point, box

from ae_engine.assembly_geometry import folded_mesh_with_flat_uv_from_polygon
from ae_engine.assembly_geometry_folded_mesh import folded_mesh_from_polygon
from ae_engine.assembly_mesh_reuse import mesh_build_scope, _active_meshes
from ae_engine.manufacturing_render_data import FoldGuide


@pytest.mark.parametrize('build', [folded_mesh_from_polygon, folded_mesh_with_flat_uv_from_polygon])
def test_reuses_exact_mesh_and_invalidates_all_geometry_dependencies(build):
    material = box(0, 0, 100, 80).difference(Point(50, 40).buffer(4))
    xp = [{'len': 20, 'angle': 90}, {'len': 60, 'core': 'W'}, {'len': 20}]
    yp = [{'len': 15, 'angle': -90}, {'len': 50, 'core': 'D'}, {'len': 15}]
    guides = [FoldGuide('x', 20, 10, 60)]
    exemptions = [('y', box(0, 0, 25, 80))]
    with mesh_build_scope():
        first = build(material, xp, yp, fold_guides=guides, fold_exemptions=exemptions)
        assert build(material, xp, yp, fold_guides=guides, fold_exemptions=exemptions) is first
        # Every mutated input must match a fresh uncached computation exactly.
        variants = []
        variants.append((material.difference(Point(30, 40).buffer(3)), xp, yp, guides, exemptions))
        variants.append((material, [{**xp[0], 'angle': -90}, *xp[1:]], yp, guides, exemptions))
        variants.append((material, [xp[0], {**xp[1], 'len': 55}, xp[2]], yp, guides, exemptions))
        variants.append((material, [{**xp[0], 'core': 'W'}, {**xp[1], 'core': ''}, xp[2]], yp, guides, exemptions))
        variants.append((material, xp, yp, [replace(guides[0], span_end=30)], exemptions))
        variants.append((material, xp, yp, [replace(guides[0], position=80)], exemptions))
        variants.append((material, xp, yp, guides, [('y', box(0, 0, 65, 80))]))
        variants.append((material, xp, yp, guides, [('x', exemptions[0][1])]))
        for m, x, y, g, e in variants:
            actual = build(m, x, y, fold_guides=g, fold_exemptions=e)
            assert actual == build.__wrapped__(m, x, y, fold_guides=g, fold_exemptions=e)
            assert actual is not first
        xp[0]['angle'] = -45
        assert build(material, xp, yp, fold_guides=guides) == build.__wrapped__(material, xp, yp, fold_guides=guides)
    assert _active_meshes.get() is None
    with mesh_build_scope():
        assert build(material, xp, yp) is not first


def test_nested_and_failed_scopes_release_their_meshes():
    with mesh_build_scope():
        outer = _active_meshes.get()
        with pytest.raises(RuntimeError):
            with mesh_build_scope():
                assert _active_meshes.get() is not outer
                raise RuntimeError('failed solve')
        assert _active_meshes.get() is outer
    assert _active_meshes.get() is None


def test_real_receiving_solve_reuses_meshes_without_changing_any_result(tmp_path, monkeypatch):
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('requires Tk display')
    import tkinter as tk
    import shapely.ops
    import gui
    import phase6_manufacturing_service as service
    from phase6_project_file import PROJECT_SCHEMA_V2, write_project
    from phase6_receiving_modes import fresh_receiving_mode

    requests = []
    original = service.resolve
    def capture(request):
        requests.append(request)
        return original(request)
    monkeypatch.setattr(service, 'resolve', capture)
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root)
        path = write_project(tmp_path / 'reuse.p6fold', {
            'schema': PROJECT_SCHEMA_V2,
            'snapshot': fresh_receiving_mode('quantity', {'w': 800, 'h': 1600, 'd': 350, 't': 2}),
        })
        host.load_phase6_project(path)
        root.update()
        request = requests[-1]
        calls = []
        triangulate = shapely.ops.triangulate
        def count(*args, **kwargs):
            calls.append(1)
            return triangulate(*args, **kwargs)
        monkeypatch.setattr(shapely.ops, 'triangulate', count)
        reference = original.__wrapped__(request)
        before = len(calls)
        calls.clear()
        actual = original(request)
        assert actual == reference  # Includes diagnostics, marking, effects, and geometry.
        assert len(calls) < before * .75, (len(calls), before)
        assert _active_meshes.get() is None
    finally:
        root.destroy()
