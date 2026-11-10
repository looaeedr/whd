"""#2517: physical sheet T shown in FinalScene comes from the Engine source."""
from copy import deepcopy
from dataclasses import fields, replace
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from phase6_final_scene_contracts import FinalSceneDependencies
from phase6_final_scene_view import Phase6FinalSceneViewAdapter, _operator_final_scene_thickness


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
    view, source, settings, calls = _view({"model": family}, {"t": raw})
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
    src = {"model": "受電箱", "t": raw} if owner == "snapshot" else {"model": "受電箱"}
    settings = {"t": raw} if owner == "settings" else {}
    view, source, values, calls = _view(src, settings)
    before = deepcopy((source, values))
    with pytest.raises(ValueError, match="包外尺寸"):
        view.build_request()
    with pytest.raises(ValueError, match="包外尺寸"):
        api.normalize_operator_source_dimension(raw, field="t")
    assert calls == []
    assert (source, values) == before


def test_missing_t_in_both_sources_fails_before_any_render_or_2mm_fallback():
    view, snapshot, settings, calls = _view({"model": "受電箱"}, {})
    with pytest.raises(ValueError, match="包外尺寸"):
        view.build_request()
    assert calls == []
    assert "t" not in snapshot and "t" not in settings


def test_missing_saved_t_uses_explicit_settings_t_without_guessing():
    view, snapshot, settings, calls = _view({"model": "受電箱"}, {"t": "2.375"})
    assert view.build_request().thickness == 2.375
    assert calls == ["assembly"]
    assert "t" not in snapshot and settings["t"] == "2.375"


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("mode", ("single", "assembly"))
def test_finalscene_and_headless_request_use_same_saved_t_even_with_stale_settings(family, mode):
    raw_snapshot = {"model": family, "t": "1.375"}
    settings = {"t": "2.875"}
    view, snapshot, global_settings, calls = _view(
        raw_snapshot, settings, mode=mode,
    )
    saved = json.loads(json.dumps({"snapshot": raw_snapshot, "settings": settings}, ensure_ascii=False))
    assert view.build_request().thickness == api.project_operator_manufacturing_request_snapshot(
        saved["snapshot"], saved["settings"], {},
    )["t"] == 1.375
    assert calls == ["assembly" if mode == "assembly" else "part"]
    assert (snapshot, global_settings) == (raw_snapshot, settings)


@pytest.mark.parametrize("bad", (True, "nan", None, 0))
def test_invalid_saved_t_must_not_use_valid_settings_t_or_render(bad):
    source = {"model": "受電箱", "t": bad}
    view, snapshot, settings, calls = _view(source, {"t": "2.375"})
    with pytest.raises(ValueError, match="包外尺寸"):
        view.build_request()
    assert calls == []
    assert (snapshot, settings) == (source, {"t": "2.375"})


def test_query_assembly_render_data_uses_same_saved_thickness_for_formed_text():
    snapshot = {"model": "金庫型", "t": "1.625"}
    settings = {"t": "3.5"}
    view, source, values, _calls = _view(snapshot, settings)
    messages = []
    part = SimpleNamespace(
        part_key="head", render_data=object(),
        x_profile=(), y_profile=(), placement="assembled", offset=(0.0, 0.0, 0.0),
    )
    view.dependencies = replace(
        view.dependencies,
        resolve_geometry=lambda: SimpleNamespace(parts=(part,), diagnostics=()),
        assembly_part_cls=SimpleNamespace,
        assembly_visibility=lambda _parts: (("head",), ()),
        cabinet_family=lambda: "金庫型",
        formed_size_text=lambda _render, **kw: kw["thickness"],
        assembly_part_text_sink=lambda *args: messages.append(args),
    )
    view.query_assembly_render_data()
    assert ("formed", "head", 1.625) in messages
    assert (source, values) == (snapshot, settings)


def test_diagnostic_only_empty_assembly_without_t_is_not_fabricated_or_suppressed():
    view, snapshot, settings, _calls = _view({"model": "金庫型"}, {})
    view.dependencies = replace(
        view.dependencies,
        resolve_geometry=lambda: SimpleNamespace(
            parts=(), diagnostics=("NO_VERIFIED_EAR_SOURCE",),
        ),
        assembly_visibility=lambda _parts: ((), ()),
        cabinet_family=lambda: "金庫型",
    )
    scene = view.query_assembly_render_data()
    assert scene.collision_certification_diagnostics == ("NO_VERIFIED_EAR_SOURCE",)
    assert scene.assembly_parts == ()
    assert "t" not in snapshot and "t" not in settings


def test_query_assembly_invalid_saved_t_never_resolves_geometry():
    view, _source, _settings, _calls = _view(
        {"model": "受電箱", "t": True}, {"t": 2.0},
    )
    called = []
    view.dependencies = replace(
        view.dependencies, resolve_geometry=lambda: called.append("geometry"),
    )
    with pytest.raises(ValueError, match="包外尺寸"):
        view.query_assembly_render_data()
    assert called == []


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
    assert view.count("_operator_final_scene_thickness(") == 2
    assert "snapshot.get(\"t\", 2.0)" not in view
    source = inspect.getsource(_operator_final_scene_thickness)
    assert "manufacturing_api.project_operator_manufacturing_request_snapshot(" in source
    assert 'thickness = _num(' not in view
    assert 'float(render_data.metadata["thickness"])' not in view
