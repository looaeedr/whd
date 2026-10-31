"""#2517/#2378: Worker must consume Engine-owned shared baseline source pairing."""
from __future__ import annotations

import inspect

import pytest

from ae_engine import manufacturing_api, expected_shared_indicator_baselines
from ae_engine.contracts import DoorPartSpec, IndicatorBoxPartSpec, ManufacturingContext
from integration_cli import prepare_batch


def _sources(root, *, missing=()):
    folder = root / "基準檔" / "指示燈"
    folder.mkdir(parents=True, exist_ok=True)
    for name in {"盒子.dxf", "小門.dxf"} - set(missing):
        (folder / name).write_bytes(b"test-only-source:" + name.encode("utf-8"))
    return folder


def test_headless_engine_owns_both_indicator_source_paths(tmp_path):
    folder = _sources(tmp_path)
    ctx = ManufacturingContext(resource_root=tmp_path)
    box_path, door_path = manufacturing_api.expected_shared_indicator_baselines(ctx)
    assert expected_shared_indicator_baselines is manufacturing_api.expected_shared_indicator_baselines
    assert (box_path, door_path) == (folder / "盒子.dxf", folder / "小門.dxf")
    box_spec = IndicatorBoxPartSpec(layer_groups=(1,), thickness=2.0)
    door_spec = DoorPartSpec(
        width=300.0, height=200.0, thickness=2.0, frame_width=25.0,
        indicator_window_groups=(1,),
    )
    assert manufacturing_api.expected_baseline_path_for(box_spec, ctx) == box_path
    assert manufacturing_api.expected_baseline_path_for(door_spec, ctx) == door_path


@pytest.mark.parametrize("missing", [("盒子.dxf",), ("小門.dxf",)])
def test_engine_shared_indicator_pair_missing_resource_fails_closed(tmp_path, missing):
    _sources(tmp_path, missing=missing)
    with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
        manufacturing_api.expected_shared_indicator_baselines(
            ManufacturingContext(resource_root=tmp_path)
        )


def test_engine_shared_indicator_pair_ambiguous_model_fails_closed(tmp_path):
    _sources(tmp_path / "one")
    _sources(tmp_path / "two")
    # Two candidates must be on the *same* resource root to be ambiguous.
    for name in ("one", "two"):
        source = tmp_path / name / "基準檔" / "指示燈"
        target = tmp_path / "基準檔" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
    with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
        manufacturing_api.expected_shared_indicator_baselines(
            ManufacturingContext(resource_root=tmp_path)
        )


def test_worker_prepare_delegates_pair_source_selection_without_private_import():
    source = inspect.getsource(prepare_batch.prepare_trusted_door_batch)
    assert "expected_shared_indicator_baselines(ctx)" in source
    assert "from ae_engine.manufacturing_baseline_policy import _indicator_shared_expected_path" not in source
    assert "counterpart_name" not in source
