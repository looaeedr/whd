"""#2517 EndCap relief interference source and world diagnostic owner."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from shapely.geometry import box

from ae_engine import manufacturing_api, project_assembled_endcap_relief_interference
from phase6_final_scene_renderer import Phase6FinalSceneRenderer


def _part():
    return SimpleNamespace(
        part_key="head",
        x_profile=({"len": 100.0, "core": "W"},),
        y_profile=({"len": 80.0, "core": "D"},),
        render_data=SimpleNamespace(
            fold_guides=(), material=box(0, 0, 100, 80),
        ),
    )


def _args():
    return dict(
        diagnostic_relief_delta=box(0, 0, 10, 10),
        box_body_collision_mesh=(((0, 0, 0), (1, 0, 0), (0, 1, 0)),),
        box_body_world=(((0, 0, 0), (10, 0, 0), (0, 10, 0)),),
        placement="head", offset=(1, 2, 3), thickness=2.,
    )


def test_absent_verified_source_refuses_unapproved_display_delta():
    part = _part()
    state = SimpleNamespace(
        ignore_fixed_corner_relief=False,
        preserve_endcap_core_origin=False,
    )
    assert project_assembled_endcap_relief_interference(
        part, None, state, **_args(),
    ) is None


def test_probe_prefers_exact_pre_solve_source_over_legacy_display_delta(monkeypatch):
    from ae_engine import endcap_relief_interference_preview as owner
    used = []
    material = box(1, 1, 99, 79)
    actual_delta = box(0, 0, 5, 5)
    monkeypatch.setattr(
        owner, "restored_endcap_relief_delta",
        lambda source: used.append(("delta", source)) or actual_delta,
    )
    folded = (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)
    def make_mesh(poly, xp, yp, *, fold_guides):
        used.append(("fold", poly, xp, yp, fold_guides))
        return folded
    monkeypatch.setattr(owner, "folded_mesh_from_polygon", make_mesh)
    target = (((1, 2, 3), (2, 2, 3), (1, 3, 3)),)
    def place(mesh, **kwargs):
        used.append(("placement", mesh, kwargs))
        return SimpleNamespace(solid_triangles=target)
    monkeypatch.setattr(owner, "resolve_assembled_endcap_world_skins", place)
    token = object()
    monkeypatch.setattr(
        owner, "detect_world_mesh_surface_interference",
        lambda source, dest: used.append(("detector", source, dest)) or token,
    )
    probe = SimpleNamespace(
        x_profile=({"len": 50, "core": "W"},),
        y_profile=({"len": 60, "core": "D"},),
        render_data=SimpleNamespace(material=material, fold_guides=("existing",)),
    )
    global_state = SimpleNamespace(
        ignore_fixed_corner_relief=True,
        preserve_endcap_core_origin=True,
    )
    args = _args()
    assert project_assembled_endcap_relief_interference(
        _part(), probe, global_state, **args,
    ) is token
    assert used[0] == ("delta", material)
    assert used[1] == (
        "fold", actual_delta, ({"len": 50, "core": "W"},),
        ({"len": 60, "core": "D"},), ("existing",),
    )
    assert used[2] == ("placement", folded, {
        "placement": "head", "box_body_world": args["box_body_world"],
        "offset": (1, 2, 3), "thickness": 2.,
        "preserve_core_origin": True,
    })
    assert used[3] == ("detector", args["box_body_collision_mesh"], target)
    assert manufacturing_api.project_assembled_endcap_relief_interference is (
        project_assembled_endcap_relief_interference
    )


def test_empty_probe_delta_does_not_invent_a_collision(monkeypatch):
    from ae_engine import endcap_relief_interference_preview as owner
    monkeypatch.setattr(
        owner, "restored_endcap_relief_delta",
        lambda source: box(0, 0, 0, 0),
    )
    assert project_assembled_endcap_relief_interference(
        _part(), _part(), SimpleNamespace(ignore_fixed_corner_relief=True),
        **_args(),
    ) is None


def test_legacy_ignore_relief_uses_saved_delta_not_any_entire_endcap(monkeypatch):
    from ae_engine import endcap_relief_interference_preview as owner
    seen = []
    monkeypatch.setattr(
        owner, "folded_mesh_from_polygon",
        lambda material, xp, yp, *, fold_guides: seen.append(
            (material, xp, yp, fold_guides)
        ) or (),
    )
    monkeypatch.setattr(
        owner, "resolve_assembled_endcap_world_skins",
        lambda *args, **kwargs: SimpleNamespace(solid_triangles=()),
    )
    part = _part()
    delta = _args()["diagnostic_relief_delta"]
    result = project_assembled_endcap_relief_interference(
        part, None, SimpleNamespace(ignore_fixed_corner_relief=True),
        **_args(),
    )
    assert result is None
    assert len(seen) == 1 and seen[0][0] is delta or (
        len(seen) == 1 and seen[0][0].equals(delta)
    )


def test_GUI_is_only_public_diagnostic_API_consumer():
    source = inspect.getsource(Phase6FinalSceneRenderer)
    needle = "manufacturing_api.project_assembled_endcap_relief_interference("
    assert needle in source
    block = source[source.index(needle):source.index(
        "if diagnostic is not None and diagnostic.has_interference:",
        source.index(needle),
    )]
    assert "folded_mesh_from_polygon(" not in block
    assert "detect_world_mesh_surface_interference(" not in block
    from ae_engine import endcap_relief_interference_preview as owner
    code = inspect.getsource(owner)
    assert "tkinter" not in code and "matplotlib" not in code
    assert "phase6_final_scene" not in code
