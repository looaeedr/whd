"""#2517: physical sheet T shown in FinalScene comes from the Engine source."""
from copy import deepcopy
from dataclasses import fields
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from phase6_final_scene_contracts import FinalSceneDependencies
from phase6_final_scene_view import Phase6FinalSceneViewAdapter


REQUIRED = (
    "is_physical_piece_key", "physical_piece_render_data",
    "user_joint_parts", "resolve_geometry", "scene_payload_for_part",
    "publish_live_state", "corner_dimension_text", "formed_size_text",
    "blank_text", "operator_dimensions", "cabinet_family",
    "assembly_blank_text", "active_mesh_profiles", "active_part",
    "scene_query", "input_snapshot", "settings_values", "alpha_bend",
    "display_mode", "assembly_corner_text_sink", "assembly_part_text_sink",
    "assembly_visibility", "interference_probe_parts",
    "show_interference", "render_committed", "set_preview_enabled",
    "refresh_preview",
)


def _view(snapshot, settings, *, active="box_body", mode="assembly", metadata=None):
    used = []
    provider_scene = object()
    part = SimpleNamespace(
        material=object(), pieces=(), metadata=metadata or {},
    )
    source = dict(snapshot)
    values = dict(settings)
    kwargs = {name: (lambda *args, **kw: None) for name in REQUIRED}
    kwargs.update(
        active_part=lambda: active,
        input_snapshot=lambda: source,
        settings_values=lambda: values,
        alpha_bend=lambda: 0.85,
        display_mode=lambda: mode,
        operator_dimensions=lambda name=None: (800.0, 1600.0, 350.0),
        assembly_render_provider=lambda: used.append("assembly") or provider_scene,
        final_render_provider=lambda: used.append("part") or part,
        active_mesh_profiles=lambda _material: ((), ()),
        corner_dimension_text=lambda *_args: "",
        blank_text=lambda *_args, **_kwargs: "",
        assembly_blank_text=lambda *_args: "",
    )
    assert set(REQUIRED).issubset({field.name for field in fields(FinalSceneDependencies)})
    return Phase6FinalSceneViewAdapter(dependencies=FinalSceneDependencies(**kwargs)), source, values, used


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("raw", ("2", "2.125", 2, 2.125))
def test_assembly_physical_thickness_matches_public_engine_and_json_reload(family, raw):
    view, source, settings, calls = _view({"model": family, "t": 2}, {"t": raw})
    before = deepcopy((source, settings))
    expected = api.normalize_operator_source_dimension(raw, field="t")
    request = view.build_request()
    assert request.thickness == expected
    assert calls == ["assembly"]
    assert (source, settings) == before
    saved = json.loads(json.dumps({"t": expected}))
    assert _view({"model": family}, saved)[0].build_request().thickness == expected


@pytest.mark.parametrize("raw", (
    True, False, 0, -1, None, "nan", "inf", "-inf", [], {},
))
@pytest.mark.parametrize("owner", ("snapshot", "settings"))
def test_invalid_physical_t_refuses_before_reading_any_scene(owner, raw):
    src = {"model": "受電箱", "t": raw} if owner == "snapshot" else {"t": 2}
    settings = {"t": raw} if owner == "settings" else {}
    view, source, values, calls = _view(src, settings)
    before = deepcopy((source, values))
    with pytest.raises(ValueError, match="包外尺寸"):
        view.build_request()
    with pytest.raises(ValueError, match="包外尺寸"):
        api.normalize_operator_source_dimension(raw, field="t")
    assert calls == []
    assert (source, values) == before


@pytest.mark.parametrize("raw,expected", (
    (None, 2.0), ("2.375", 2.375),
))
def test_absent_t_uses_existing_legacy_default_without_overriding_present_t(raw, expected):
    settings = {} if raw is None else {"t": raw}
    view, _, _, calls = _view({}, settings)
    assert view.build_request().thickness == expected
    assert calls == ["assembly"]


@pytest.mark.parametrize("raw", (True, 0, -2, "nan", "inf", None))
def test_fixing_plate_metadata_thickness_is_also_engine_validated(raw):
    view, source, settings, calls = _view(
        {"t": 2.0}, {},
        active="base_plate:fixing_plate:0",
        mode="single",
        metadata={"thickness": raw},
    )
    before = deepcopy((source, settings))
    with pytest.raises(ValueError, match="包外尺寸"):
        view.build_request()
    assert calls == ["part"]
    assert (source, settings) == before


@pytest.mark.parametrize("raw", ("0.875", 0.875, "3.125"))
def test_legitimate_fixing_plate_thickness_preserves_engine_fractional_mm(raw):
    view, _source, _settings, calls = _view(
        {"t": 2}, {},
        active="base_plate:fixing_plate:1",
        mode="single",
        metadata={"thickness": raw},
    )
    assert view.build_request().thickness == api.normalize_operator_source_dimension(
        raw, field="t",
    )
    assert calls == ["part"]


def test_display_owner_has_no_guessed_thickness_or_python_bool_conversion():
    view = inspect.getsource(Phase6FinalSceneViewAdapter)
    assert view.count("manufacturing_api.normalize_operator_source_dimension(") >= 3
    assert 'thickness = _num(' not in view
    assert 'float(render_data.metadata["thickness"])' not in view
