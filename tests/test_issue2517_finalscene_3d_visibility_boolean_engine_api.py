"""#2517: serialized display flags may not change assembled 3D state by truthiness."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from phase6_final_scene_contracts import (
    AssemblyScenePart, AssemblySceneRenderData, AssemblyVisibility,
)
from phase6_final_scene_view import Phase6FinalSceneViewAdapter


@pytest.mark.parametrize("raw,expected", (
    (False, False), ("false", False), ("FALSE", False),
    ("off", False), ("0", False), (0, False),
    (True, True), ("true", True), ("on", True), ("1", True), (1, True),
))
def test_ear_visibility_serialized_flag_uses_original_public_engine_boolean(raw, expected):
    value = AssemblyVisibility(
        ("base_plate",), (), show_fixing_plate_mesh=raw,
    )
    assert value.show_fixing_plate_mesh is expected
    assert value == (("base_plate",), ())
    assert value.show_fixing_plate_mesh is (
        manufacturing_api.normalize_operator_settings_boolean(raw)
    )


@pytest.mark.parametrize("raw", ("invalid", "maybe", 2, -1, 0.5, None, [], {}))
def test_bad_3d_visibility_cannot_become_a_claimed_visible_ear(raw):
    with pytest.raises(ValueError):
        AssemblyVisibility((), (), show_fixing_plate_mesh=raw)


class _LegacyRawVisibility(tuple):
    """An older GUI visibility port can supply the raw state on a tuple."""

    def __new__(cls, raw):
        value = super().__new__(cls, ((), None))
        value.show_fixing_plate_mesh = raw
        return value


def _adapter(snapshot, *, raw_ear, raw_interference):
    view = object.__new__(Phase6FinalSceneViewAdapter)
    view.dependencies = SimpleNamespace(
        input_snapshot=lambda: snapshot,
        settings_values=lambda: {},
        resolve_geometry=lambda: SimpleNamespace(parts=(), diagnostics=()),
        assembly_part_cls=AssemblyScenePart,
        corner_dimension_text=lambda *_: "",
        assembly_corner_text_sink=lambda *_: None,
        formed_size_text=lambda *a, **kw: "",
        blank_text=lambda *a, **kw: "",
        operator_dimensions=lambda *_: (800.0, 1200.0),
        refresh_box_body_piece_info=None,
        assembly_part_text_sink=lambda *a: None,
        assembly_visibility=lambda *_: _LegacyRawVisibility(raw_ear),
        interference_probe_parts=lambda: (),
        cabinet_family=lambda: "金庫型",
        show_interference=lambda: raw_interference,
        assembly_render_data_cls=AssemblySceneRenderData,
    )
    return view


@pytest.mark.parametrize("raw_ear,raw_interference,expected_ear,expected_interference", (
    ("false", "false", False, False),
    ("true", "true", True, True),
    (False, "off", False, False),
    ("0", 1, False, True),
))
def test_real_finalscene_assembly_reads_both_raw_flags_through_engine(
    tmp_path, raw_ear, raw_interference, expected_ear, expected_interference,
):
    import phase6_project_file as project

    original = {"model": "金庫型", "w": 800.0, "h": 1200.0,
                "d": 350.0, "t": 2.0}
    target = project.write_project(
        tmp_path / "canonical-3d-visibility.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    saved = project.read_project(target)["snapshot"]
    view = _adapter(
        saved, raw_ear=raw_ear, raw_interference=raw_interference,
    )
    actual = view.query_assembly_render_data()
    assert isinstance(actual, AssemblySceneRenderData)
    assert actual.show_fixing_plate_mesh is expected_ear
    assert actual.show_interference is expected_interference
    assert actual.assembly_parts == ()
    assert saved["model"] == "金庫型"


@pytest.mark.parametrize("kind", ("ear", "interference"))
def test_invalid_existing_gui_3d_flag_rejects_without_rendering_unverified_state(kind):
    snapshot = {"model": "金庫型", "w": 800.0, "h": 1200.0,
                "d": 350.0, "t": 2.0}
    view = _adapter(
        snapshot,
        raw_ear="bad" if kind == "ear" else False,
        raw_interference="bad" if kind == "interference" else False,
    )
    with pytest.raises(ValueError):
        view.query_assembly_render_data()
