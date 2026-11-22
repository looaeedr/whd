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
    from ae_engine.manufacturing_resolver import resolve as canonical_resolve
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
        # Compare uncached Engine body with the same decorated Engine solve
        # reached through the old Phase6 entry, not the thin compatibility wrapper.
        reference = canonical_resolve.__wrapped__(request)
        before = len(calls)
        calls.clear()
        actual = original(request)
        assert actual == reference  # Includes diagnostics, marking, effects, and geometry.
        assert len(calls) < before * .75, (len(calls), before)
        assert _active_meshes.get() is None
    finally:
        root.destroy()


def test_inactive_fold_tip_keeps_legacy_receiving_mesh_builder_contract_across_all_paths():
    """An optional Tail-only kwarg must never reach an old receiving builder."""
    from ae_engine.assembly_mesh_reuse import reuse_local_mesh
    calls = []
    def legacy(material, x_profile, y_profile, *,
               fold_exemptions=(), fold_guides=()):
        calls.append((material, x_profile, y_profile))
        return object()
    build = reuse_local_mesh(legacy)
    stock = box(0, 0, 100, 80)
    profile = ({'len': 20, 'angle': 90}, {'len': 80})
    # Path 1: no active scope.
    build(stock, profile, (), fold_tip_continuity=())
    assert len(calls) == 1
    with mesh_build_scope():
        # Path 3: first cached build and same-key reuse.
        first = build(stock, profile, (), fold_tip_continuity=())
        assert build(stock, profile, ()) is first
        assert len(calls) == 2
        # Path 2: unusual unhashable profile forces uncached fallback.
        unhashable = ({'len': 20, 'phase6_key': []}, {'len': 80})
        build(stock, unhashable, (), fold_tip_continuity=())
        assert len(calls) == 3


def test_active_fold_tip_is_forwarded_and_separately_cached():
    """Cache key must never confuse a connected-Tail tip with a legacy mesh."""
    from ae_engine.assembly_mesh_reuse import reuse_local_mesh
    calls = []
    def aware(material, x_profile, y_profile, *,
              fold_exemptions=(), fold_guides=(), fold_tip_continuity=()):
        calls.append(tuple(fold_tip_continuity))
        return object()
    build = reuse_local_mesh(aware)
    stock = box(0, 0, 100, 80)
    profile = ({'len': 15, 'angle': 90}, {'len': 85})
    tip = (('x', 15.0, 48.0, 290.0),)
    # Without scope and in the unhashable profile fallback, enabled
    # extensions must actually reach the new geometry builder.
    build(stock, profile, (), fold_tip_continuity=tip)
    with mesh_build_scope():
        plain = build(stock, profile, ())
        folded = build(stock, profile, (), fold_tip_continuity=tip)
        assert build(stock, profile, (), fold_tip_continuity=tip) is folded
        assert build(stock, profile, ()) is plain
        assert folded is not plain
        build(stock, ({'len': 15, 'phase6_key': []},), (),
              fold_tip_continuity=tip)
    assert calls == [tip, (), tip, tip]
