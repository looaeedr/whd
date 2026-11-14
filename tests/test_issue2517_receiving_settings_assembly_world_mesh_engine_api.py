"""#2517 Receiving settings 2D physical world-assembly belongs to Engine."""
from __future__ import annotations

from types import SimpleNamespace
import inspect

import pytest
from shapely.geometry import box, Point

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene
from gui_modules.application import receiving_settings_preview_2d as gui


def _part(key, material, *, offset=(0, 0, 0), placement="offset"):
    return SimpleNamespace(
        part_key=key,
        render_data=PartRenderData(scene=DrawingScene(), material=material),
        x_profile=({"len": 100.0, "core": "W"},),
        y_profile=({"len": 70.0, "core": "H"},),
        placement=placement,
        offset=offset,
    )


def test_headless_world_meshes_keep_holes_offsets_and_source_part_identity():
    material = box(0, 0, 100, 70).difference(
        Point(45, 35).buffer(7, quad_segs=12)
    )
    witness = material.wkb
    parts = (_part("door:left", material),
             _part("door:right", material, offset=(180, 0, 0)))
    rows = api.resolve_receiving_settings_assembly_world_meshes(
        parts, finished_dimensions=(300, 200, 80), thickness=2.0,
    )
    assert [key for _, key, _ in rows] == ["door:left", "door:right"]
    assert all(len(mesh) > 4 for _, _, mesh in rows)
    mins = [min(pt[0] for tri in mesh for pt in tri) for _, _, mesh in rows]
    assert mins[1] - mins[0] == pytest.approx(180.0)
    assert material.wkb == witness


def test_real_receiving_split_box_body_uses_exact_physical_world_skins():
    from tests.test_piece_level_joint_geometry import _receiving_body_part
    body = _receiving_body_part()
    dims = (800.0, 600.0, 350.0)
    world = api.build_joint_world_geometry(
        (body,), dims, 2.0,
    )["world_triangles_by_part"]
    rows = api.resolve_receiving_settings_assembly_world_meshes(
        (body,), finished_dimensions=dims, thickness=2.0,
    )
    roles = {role for role, _key, _mesh in rows}
    assert roles == {"left_side", "back", "right_side"}
    for role, key, mesh in rows:
        # Original physical piece IDs use underscores; world owner keys use
        # "box_body:" namespace. Preserve both identities exactly as sourced.
        assert key == f"box_body_{role}"
        assert mesh == tuple(world[f"box_body:{role}"])


def test_invalid_multisheet_outside_width_source_fails_closed():
    fake = SimpleNamespace(role="left_side", formed_w_end=True)
    data = SimpleNamespace(pieces=(fake,))
    body = SimpleNamespace(part_key="box_body", render_data=data)
    with pytest.raises(ValueError, match="BOX_BODY_PIECE_OUTSIDE_DATUM_INVALID"):
        api.resolve_receiving_settings_assembly_world_meshes(
            (body,), finished_dimensions=(800, 600, 350), thickness=2.0,
        )


def test_receiving_gui_only_delegates_world_geometry_and_maps_display_role(monkeypatch):
    expected = (("door:left", "door:left", (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)),)
    calls = []
    def fake(parts, **kw):
        calls.append((parts, kw))
        return expected
    monkeypatch.setattr(api, "resolve_receiving_settings_assembly_world_meshes", fake)
    request = SimpleNamespace(
        render_data=SimpleNamespace(assembly_parts=("source",),
                                    preserve_endcap_core_origin=True),
        finished_dimensions=(800, 600, 350),
        thickness=2.0,
    )
    assert tuple(gui._assembly_world_meshes(request)) == (
        ("door", "door:left", expected[0][2]),
    )
    assert calls == [(("source",), {
        "finished_dimensions": (800, 600, 350),
        "thickness": 2.0,
        "preserve_endcap_core_origin": True,
    })]
    source = inspect.getsource(gui._assembly_world_meshes)
    assert "manufacturing_api.resolve_receiving_settings_assembly_world_meshes" in source
    assert "_phase6_" not in source
    assert "place_endcap_against_box_body" not in source


def test_preserve_core_origin_source_is_validated_before_any_world_geometry():
    """A damaged saved bool cannot be treated as True or deferred until meshing."""
    for bad in ("not-a-boolean", None, 2, -1, float("nan"), object()):
        with pytest.raises(ValueError, match="布林"):
            api.resolve_receiving_settings_assembly_world_meshes(
                (object(),), finished_dimensions=(300, 200, 80), thickness=2.0,
                preserve_endcap_core_origin=bad,
            )
    assert api.resolve_receiving_settings_assembly_world_meshes(
        (), finished_dimensions=(300, 200, 80), thickness=2.0,
        preserve_endcap_core_origin="false",
    ) == ()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(False, False), ("false", False), ("off", False), (0, False),
     (True, True), ("true", True), ("on", True), (1, True)],
)
def test_headless_receiving_world_assembly_uses_engine_decoded_origin_flag(
    monkeypatch, raw, expected,
):
    from ae_engine import receiving_settings_assembly_mesh as owner

    seen = []

    def observed_endcap(local, **kwargs):
        seen.append(kwargs["preserve_core_origin"])
        return SimpleNamespace(solid_triangles=tuple(local))

    monkeypatch.setattr(owner, "resolve_assembled_endcap_world_skins", observed_endcap)
    material = box(0, 0, 100, 70)
    rows = api.resolve_receiving_settings_assembly_world_meshes(
        (_part("box_body", material), _part("head", material, placement="head")),
        finished_dimensions=(300, 200, 80), thickness=2.0,
        preserve_endcap_core_origin=raw,
    )
    assert seen == [expected]
    assert [key for _, key, _ in rows] == ["box_body", "head"]


def test_direct_assembled_endcap_source_uses_same_engine_boolean_contract(monkeypatch):
    from ae_engine import receiving_settings_assembly_mesh as owner

    seen = []
    triangle = (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)

    def fake_place(*args, **kwargs):
        seen.append(kwargs["preserve_core_origin"])
        return triangle

    monkeypatch.setattr(owner, "place_endcap_against_box_body", fake_place)
    monkeypatch.setattr(owner, "thicken_triangle_surface", lambda surface, _t: surface)
    for raw in ("false", False, "true", True):
        assembled = api.resolve_assembled_endcap_world_skins(
            triangle, placement="head", box_body_world=triangle,
            thickness=2.0, preserve_core_origin=raw,
        )
        assert assembled.formed_surface == triangle
    assert seen == [False, False, True, True]
    with pytest.raises(ValueError, match="布林"):
        api.resolve_assembled_endcap_world_skins(
            triangle, placement="head", box_body_world=triangle,
            thickness=2.0, preserve_core_origin="invalid",
        )
    assert seen == [False, False, True, True]


def test_gui_passes_raw_preserve_origin_source_to_headless_engine(monkeypatch):
    calls = []

    def observed(parts, **kwargs):
        calls.append(kwargs["preserve_endcap_core_origin"])
        api.normalize_operator_settings_boolean(kwargs["preserve_endcap_core_origin"])
        return ()

    monkeypatch.setattr(api, "resolve_receiving_settings_assembly_world_meshes", observed)
    for raw in ("false", False, "true", True):
        request = SimpleNamespace(
            render_data=SimpleNamespace(assembly_parts=(), preserve_endcap_core_origin=raw),
            finished_dimensions=(300, 200, 80), thickness=2.0,
        )
        assert tuple(gui._assembly_world_meshes(request)) == ()
    assert calls == ["false", False, "true", True]
    invalid = SimpleNamespace(
        render_data=SimpleNamespace(assembly_parts=(), preserve_endcap_core_origin="broken"),
        finished_dimensions=(300, 200, 80), thickness=2.0,
    )
    with pytest.raises(ValueError, match="布林"):
        tuple(gui._assembly_world_meshes(invalid))
    assert calls[-1] == "broken"
    assert invalid.render_data.preserve_endcap_core_origin == "broken"
    assert "preserve_endcap_core_origin=bool(" not in inspect.getsource(gui._assembly_world_meshes)
