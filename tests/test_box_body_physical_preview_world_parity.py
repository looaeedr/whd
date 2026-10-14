# -*- coding: utf-8 -*-
"""One physical panel must be the identical manufactured solid in both 3D views."""
from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

from phase6_final_scene_contracts import FinalSceneDependencies
from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_final_scene_projection import _phase6_box_body_true_world_piece_meshes
from tests.test_issue39_divider_relief import _snapshot, _body_part
from tests.test_phase6_assembly_3d_view import Axis


def _view(*, active, material, body, dims, thickness):
    # Real typed view ports. Non-participating GUI callbacks stay inert.
    callback = lambda *args, **kwargs: None
    ports = {
        field.name: callback
        for field in fields(FinalSceneDependencies)
        if field.default is None
    }
    ports.update(
        active_part=lambda: active,
        input_snapshot=lambda: {"t": thickness},
        settings_values=lambda: {"t": thickness},
        alpha_bend=lambda: 0.85,
        display_mode=lambda: "single",
        operator_dimensions=lambda key=None: dims,
        is_physical_piece_key=lambda key: key.startswith("box_body:") and
            key.split(":")[1] in {"left_side", "right_side", "back"},
        final_render_provider=lambda: material,
        resolve_geometry=lambda: SimpleNamespace(parts=(body,)),
        active_mesh_profiles=lambda material: (_ for _ in ()).throw(
            AssertionError("physical panel may not re-fold an operator chain")
        ),
        corner_dimension_text=lambda material: "",
        blank_text=lambda material, **kw: "",
    )
    return Phase6FinalSceneViewAdapter(
        dependencies=FinalSceneDependencies(**ports)
    )


def test_all_physical_box_body_piece_previews_are_exact_assembly_world_skins():
    snap = _snapshot()
    body = _body_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])
    canonical = {
        piece.role: tuple(triangles)
        for piece, triangles in _phase6_box_body_true_world_piece_meshes(
            body, dimensions=dims, thickness=snap["t"]
        )
    }
    for piece in body.render_data.pieces:
        role = piece.role
        request = _view(
            active="box_body:" + role,
            material=piece.render_data,
            body=body,
            dims=dims,
            thickness=snap["t"],
        ).build_request()
        assert request.x_profile == request.y_profile == ()
        assert request.physical_world_triangles == canonical[role]
        shown = Phase6FinalSceneRenderer(
            SimpleNamespace(ax3d=Axis())
        ).render(request)
        assert tuple(shown) == canonical[role], (
            f"{role}: single 3D and assembled manufactured solids differ"
        )
        assert shown, f"{role} missing physical 3D"


def test_nonphysical_door_still_renders_its_editor_fold_draft():
    from shapely.geometry import box

    profile = ({"len": 20.0, "angle": 90.0}, {"len": 100.0})
    material = SimpleNamespace(
        material=box(0, 0, 120, 240), metadata=None
    )
    snap = _snapshot()
    dims = (snap["w"], snap["h"], snap["d"])
    body = _body_part(snap)
    view = _view(
        active="door", material=material, body=body,
        dims=dims, thickness=snap["t"],
    )
    from dataclasses import replace
    deps = replace(
        view.dependencies,
        active_mesh_profiles=lambda material: (profile, ({"len": 240.0},)),
    )
    request = Phase6FinalSceneViewAdapter(
        dependencies=deps
    ).build_request()
    assert request.x_profile == profile
    assert request.physical_world_triangles == ()
