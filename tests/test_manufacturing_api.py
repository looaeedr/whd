from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest

import ae_engine.ae as ae
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


def test_contracts_import_without_gui_module():
    code = "import sys; import ae_engine.contracts, ae_engine.manufacturing_api; assert 'gui' not in sys.modules; print('OK')"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "OK"


def test_contracts_preserve_explicit_finished_face_inputs():
    from ae_engine.contracts import BoxBodyPartSpec, DoorPartSpec, EndCapPartSpec

    door = DoorPartSpec(
        width=500, height=600, thickness=2, frame_width=25,
        model_name="金庫型", features=({"type": "圓孔", "x": 100, "y": 120, "params": {"diameter": 22}},),
        frame_edges=DoorFrameEdges(right=False, bottom=False),
    )
    body = BoxBodyPartSpec(width=500, height=600, depth=200, thickness=2, frame_width=25, model_name="金庫型")
    head = EndCapPartSpec(width=500, depth=200, thickness=2, frame_width=25, model_name="金庫型", is_tail=False)

    assert (door.width, door.height, door.thickness, door.model_name) == (500, 600, 2, "金庫型")
    assert door.features[0]["x"] == 100
    assert door.frame_edges.right is False and door.frame_edges.bottom is False
    assert (body.width, body.height, body.depth) == (500, 600, 200)
    assert (head.width, head.depth, head.is_tail) == (500, 200, False)


def _touch_baseline(root: Path, model: str, filename: str):
    path = root / "基準檔" / model / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")
    return path


def test_generate_part_dispatches_door_to_baseline_exporter_when_baseline_exists(tmp_path, monkeypatch):
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    baseline = _touch_baseline(tmp_path, "金庫型", "門.dxf")
    calls = []
    monkeypatch.setattr(ae, "export_stretched_door_dxf", lambda fp, *a, **k: Path(fp).write_text("baseline", encoding="utf-8") or calls.append(("baseline", a, k)))
    monkeypatch.setattr(ae, "export_door_dxf", lambda fp, *a, **k: (_ for _ in ()).throw(AssertionError("formula exporter must not run")))

    out = tmp_path / "out" / "door.dxf"
    result = generate_part(
        DoorPartSpec(width=500, height=600, thickness=2, frame_width=25, model_name="金庫型"),
        out,
        ManufacturingContext(resource_root=tmp_path),
    )

    assert out.read_text(encoding="utf-8") == "baseline"
    assert result.used_baseline is True
    assert Path(result.baseline_path) == baseline
    assert result.exporter_name == "export_stretched_door_dxf"


def test_generate_part_dispatches_door_to_formula_without_baseline(tmp_path, monkeypatch):
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    calls = []
    monkeypatch.setattr(ae, "export_door_dxf", lambda fp, *a, **k: Path(fp).write_text("formula", encoding="utf-8") or calls.append((a, k)))
    monkeypatch.setattr(ae, "export_stretched_door_dxf", lambda *a, **k: (_ for _ in ()).throw(AssertionError("baseline exporter must not run")))

    out = tmp_path / "door.dxf"
    result = generate_part(
        DoorPartSpec(width=500, height=600, thickness=2, frame_width=25, model_name="金庫型"),
        out,
        ManufacturingContext(resource_root=tmp_path),
    )
    assert out.read_text(encoding="utf-8") == "formula"
    assert result.used_baseline is False
    assert result.baseline_path is None
    assert result.exporter_name == "export_door_dxf"


def test_generate_part_box_body_keeps_formula_exporter_and_passes_model_for_fixed_features(tmp_path, monkeypatch):
    from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    baseline = _touch_baseline(tmp_path, "金庫型", "箱身.dxf")
    captured = {}
    def fake_export(fp, *a, **kwargs):
        captured.update(kwargs)
        Path(fp).write_text("box", encoding="utf-8")
    monkeypatch.setattr(ae, "export_box_body_dxf", fake_export)

    out = tmp_path / "box.dxf"
    result = generate_part(
        BoxBodyPartSpec(width=500, height=600, depth=200, thickness=2, frame_width=25, model_name="金庫型"),
        out,
        ManufacturingContext(resource_root=tmp_path),
    )
    assert captured["model_name"] == "金庫型"
    assert result.used_baseline is True
    assert Path(result.baseline_path) == baseline
    assert result.exporter_name == "export_box_body_dxf"


def test_generate_part_endcap_baseline_and_tail_flag(tmp_path, monkeypatch):
    from ae_engine.contracts import EndCapPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    _touch_baseline(tmp_path, "金庫型", "封頭尾.dxf")
    captured = {}
    def fake_export(fp, *args, **kwargs):
        captured.update(kwargs)
        Path(fp).write_text("endcap", encoding="utf-8")
    monkeypatch.setattr(ae, "export_stretched_end_cap_dxf", fake_export)
    monkeypatch.setattr(ae, "export_end_cap_dxf", lambda *a, **k: (_ for _ in ()).throw(AssertionError("formula exporter must not run")))

    out = tmp_path / "tail.dxf"
    result = generate_part(
        EndCapPartSpec(width=500, depth=200, thickness=2, frame_width=25, model_name="金庫型", is_tail=True),
        out,
        ManufacturingContext(resource_root=tmp_path),
    )
    assert captured["is_tail"] is True
    assert result.used_baseline is True


def test_generate_part_is_atomic_when_exporter_fails(tmp_path, monkeypatch):
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    out = tmp_path / "door.dxf"
    out.write_text("OLD", encoding="utf-8")
    def fail_after_partial_write(fp, *args, **kwargs):
        Path(fp).write_text("BROKEN", encoding="utf-8")
        raise RuntimeError("boom")
    monkeypatch.setattr(ae, "export_door_dxf", fail_after_partial_write)

    with pytest.raises(RuntimeError, match="boom"):
        generate_part(
            DoorPartSpec(width=500, height=600, thickness=2, frame_width=25),
            out,
            ManufacturingContext(resource_root=tmp_path, overwrite=True),
        )
    assert out.read_text(encoding="utf-8") == "OLD"
    assert not list(tmp_path.glob(".*door*.tmp*.dxf"))


def test_generate_part_refuses_existing_destination_when_overwrite_disabled(tmp_path):
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    out = tmp_path / "door.dxf"
    out.write_text("OLD", encoding="utf-8")
    with pytest.raises(FileExistsError):
        generate_part(
            DoorPartSpec(width=500, height=600, thickness=2, frame_width=25),
            out,
            ManufacturingContext(resource_root=tmp_path, overwrite=False),
        )


def test_real_custom_resource_root_loads_door_baseline_outside_ae_directory(tmp_path):
    import shutil
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    project_root = Path(__file__).resolve().parents[1]
    custom_root = tmp_path / "split_project"
    model_dir = custom_root / "基準檔" / "金庫型"
    model_dir.mkdir(parents=True)
    shutil.copy2(project_root / "基準檔" / "金庫型" / "門.dxf", model_dir / "門.dxf")

    out = tmp_path / "custom_root_door.dxf"
    result = generate_part(
        DoorPartSpec(width=500, height=600, thickness=2, frame_width=25, model_name="金庫型"),
        out,
        ManufacturingContext(resource_root=custom_root, draw_stock=False),
    )
    assert result.used_baseline is True
    assert Path(result.baseline_path) == model_dir / "門.dxf"
    doc = ezdxf.readfile(out)
    assert any(e.dxf.layer == "CUTTING" for e in doc.modelspace())


def test_real_headless_api_exports_door_box_body_head_and_tail_without_gui(tmp_path):
    from ae_engine.contracts import BoxBodyPartSpec, DoorPartSpec, EndCapPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    project_root = Path(__file__).resolve().parents[1]
    ctx = ManufacturingContext(resource_root=project_root, draw_stock=False)
    specs = [
        ("door", DoorPartSpec(width=500, height=600, thickness=2, frame_width=25, model_name="金庫型")),
        ("box", BoxBodyPartSpec(width=500, height=600, depth=200, thickness=2, frame_width=25, model_name="金庫型")),
        ("head", EndCapPartSpec(width=500, depth=200, thickness=2, frame_width=25, model_name="金庫型", is_tail=False)),
        ("tail", EndCapPartSpec(width=500, depth=200, thickness=2, frame_width=25, model_name="金庫型", is_tail=True)),
    ]

    for name, spec in specs:
        out = tmp_path / f"{name}.dxf"
        result = generate_part(spec, out, ctx)
        assert result.output_path == str(out)
        doc = ezdxf.readfile(out)
        layers = {e.dxf.layer for e in doc.modelspace()}
        assert "CUTTING" in layers
        if name == "box":
            assert "BEND" in layers


def test_endcap_formula_contract_preserves_full_gui_parameters(tmp_path, monkeypatch):
    from ae_engine.contracts import EndCapPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    captured = {}
    def fake_export(fp, *args, **kwargs):
        captured.update(kwargs)
        Path(fp).write_text("endcap-formula", encoding="utf-8")
    monkeypatch.setattr(ae, "export_end_cap_dxf", fake_export)

    spec = EndCapPartSpec(
        width=500, height=600, depth=200, thickness=2, frame_width=25,
        fold_left=21, fold_right=22, fold_top=41, fold_bottom=23,
        box_fold_left=14, box_fold_right=16,
        model_name=None, is_tail=False,
    )
    generate_part(spec, tmp_path / "head.dxf", ManufacturingContext(resource_root=tmp_path))

    assert captured["W_val"] == 500
    assert captured["H_val"] == 600
    assert captured["D_val"] == 200
    assert captured["T_val"] == 2
    assert captured["FW_val"] == 25
    assert captured["yl1"] == 21
    assert captured["yr1"] == 22
    assert captured["ytop1"] == 41
    assert captured["ybottom1"] == 23
    assert captured["zl1"] == 14
    assert captured["zr1"] == 16


def test_generate_part_supports_base_plate(tmp_path, monkeypatch):
    from ae_engine.contracts import BasePlatePartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    captured = {}
    def fake_export(fp, *args, **kwargs):
        captured.update(kwargs)
        Path(fp).write_text("base", encoding="utf-8")
    monkeypatch.setattr(ae, "export_base_plate_dxf", fake_export)

    result = generate_part(
        BasePlatePartSpec(
            width=500, height=600, thickness=2,
            shrink_top=12, shrink_bottom=13, shrink_left=14, shrink_right=15,
            bend=20, features=({"type": "圓孔", "x": 50, "y": 60, "params": {"diameter": 8}},),
        ),
        tmp_path / "base.dxf",
        ManufacturingContext(resource_root=tmp_path, draw_stock=True),
    )
    assert result.part_kind == "base_plate"
    assert result.exporter_name == "export_base_plate_dxf"
    assert captured["W_val"] == 500 and captured["H_val"] == 600
    assert captured["shrink_top"] == 12 and captured["shrink_right"] == 15
    assert captured["bend"] == 20
    assert captured["draw_stock"] is True
    assert len(captured["user_features"]) == 1


def test_generate_part_supports_indicator_box(tmp_path, monkeypatch):
    from ae_engine.contracts import IndicatorBoxPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    shared = tmp_path / "基準檔" / "任意共用名稱"
    shared.mkdir(parents=True)
    (shared / "盒子.dxf").write_text("box", encoding="utf-8")
    (shared / "小門.dxf").write_text("door", encoding="utf-8")
    captured = {}
    def fake_export(fp, *args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        Path(fp).write_text("ibox", encoding="utf-8")
    monkeypatch.setattr(ae, "export_stretched_indicator_box_dxf", fake_export)

    result = generate_part(
        IndicatorBoxPartSpec(
            layer_groups=(2, 3), thickness=2,
            features=({"type": "圓孔", "x": 20, "y": 30, "params": {"diameter": 6}},),
        ),
        tmp_path / "ibox.dxf",
        ManufacturingContext(resource_root=tmp_path, draw_stock=True),
    )
    assert result.part_kind == "indicator_box"
    assert result.exporter_name == "export_stretched_indicator_box_dxf"
    assert captured["args"][0] is None
    assert captured["args"][1] == [2, 3]
    assert captured["T_val"] == 2
    assert captured["draw_stock"] is True
    assert len(captured["user_features"]) == 1
