from __future__ import annotations

import configparser
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
AE = ROOT / "ae_engine" / "ae.py"
API = ROOT / "ae_engine" / "manufacturing_api.py"
sys.path.insert(0, str(ROOT))


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gui_never_builds_baseline_filesystem_paths_itself():
    src = _text(GUI)
    assert "os.path.dirname(ae.__file__)" not in src
    assert not re.search(r"os\.path\.join\([^\n]*[\"']基準檔", src)
    assert 'ae.get_resource_path("基準檔' not in src
    assert "ae.indicator_shared_baseline_model_name()" not in src


def test_manufacturing_api_never_knows_baseline_directory_or_shared_folder_name():
    src = _text(API)
    assert '"基準檔"' not in src
    assert "'基準檔'" not in src
    assert 'INDICATOR_SHARED_BASELINE_MODEL' not in src
    assert not re.search(r"getattr\(ae,[^\n]*[\"']指示燈[\"']", src)
    assert "_indicator_shared_model_name" not in src


def test_small_door_role_is_not_detected_by_shared_model_name():
    src = _text(AE)
    assert "model_name or '').strip() == shared_model" not in src
    assert 'model_name or "").strip() == shared_model' not in src
    assert "if indicator_window_groups is not None:" in src


def test_ae_has_one_central_baseline_root_builder_and_no_fixed_shared_model():
    src = _text(AE)
    # Only baseline_root_path() may ask get_resource_path() for the baseline root.
    occurrences = src.count('get_resource_path("基準檔') + src.count("get_resource_path('基準檔")
    assert occurrences == 1
    assert "INDICATOR_SHARED_BASELINE_MODEL =" not in src
    assert 'fallback="指示燈"' not in src
    assert "fallback='指示燈'" not in src


def _fresh_config(shared_model: str = "") -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read_dict({"INDICATOR_BOX": {"shared_baseline_model": shared_model}})
    return cfg


def _make_shared(root: Path, name: str) -> Path:
    folder = root / "基準檔" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "盒子.dxf").write_text("box", encoding="utf-8")
    (folder / "小門.dxf").write_text("door", encoding="utf-8")
    return folder


def test_shared_baseline_auto_discovers_unique_folder(monkeypatch, tmp_path):
    from ae_engine import ae

    shared = _make_shared(tmp_path, "任意共用名稱")
    monkeypatch.setattr(ae, "config", _fresh_config())
    monkeypatch.setattr(ae, "get_resource_path", lambda relative: str(tmp_path / relative))

    assert ae.indicator_shared_baseline_model_name() == "任意共用名稱"
    assert Path(ae.indicator_shared_baseline_part_path("盒子.dxf")) == shared / "盒子.dxf"
    assert Path(ae.indicator_shared_baseline_part_path("小門.dxf")) == shared / "小門.dxf"


def test_shared_baseline_explicit_config_wins_without_fixed_folder_name(monkeypatch, tmp_path):
    from ae_engine import ae

    _make_shared(tmp_path, "自動候選")
    explicit = _make_shared(tmp_path, "使用者指定")
    monkeypatch.setattr(ae, "config", _fresh_config("使用者指定"))
    monkeypatch.setattr(ae, "get_resource_path", lambda relative: str(tmp_path / relative))

    assert ae.indicator_shared_baseline_model_name() == "使用者指定"
    assert Path(ae.indicator_shared_baseline_part_path("盒子.dxf")) == explicit / "盒子.dxf"


def test_shared_baseline_ambiguous_candidates_fail_instead_of_fallback(monkeypatch, tmp_path):
    from ae_engine import ae

    _make_shared(tmp_path, "A")
    _make_shared(tmp_path, "B")
    monkeypatch.setattr(ae, "config", _fresh_config())
    monkeypatch.setattr(ae, "get_resource_path", lambda relative: str(tmp_path / relative))

    with pytest.raises(RuntimeError, match="shared_baseline_model"):
        ae.indicator_shared_baseline_model_name()


def test_shared_baseline_missing_fails_instead_of_fallback(monkeypatch, tmp_path):
    from ae_engine import ae

    (tmp_path / "基準檔").mkdir(parents=True)
    monkeypatch.setattr(ae, "config", _fresh_config())
    monkeypatch.setattr(ae, "get_resource_path", lambda relative: str(tmp_path / relative))

    with pytest.raises(FileNotFoundError, match="shared_baseline_model"):
        ae.indicator_shared_baseline_model_name()


def test_manufacturing_context_resource_root_controls_box_and_small_door(monkeypatch, tmp_path):
    from ae_engine import ae
    from ae_engine.contracts import IndicatorBoxPartSpec, ManufacturingContext
    from ae_engine import manufacturing_api as api

    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    shared_a = _make_shared(root_a, "共用甲")
    shared_b = _make_shared(root_b, "共用乙")
    monkeypatch.setattr(ae, "config", _fresh_config())

    box = IndicatorBoxPartSpec(layer_groups=(1,), thickness=2.0)
    small = api.indicator_small_door_spec((1,), thickness=2.0)
    assert small.model_name is None

    path_a_box = api.expected_baseline_path_for(box, ManufacturingContext(resource_root=str(root_a)))
    path_a_door = api.expected_baseline_path_for(small, ManufacturingContext(resource_root=str(root_a)))
    path_b_box = api.expected_baseline_path_for(box, ManufacturingContext(resource_root=str(root_b)))
    path_b_door = api.expected_baseline_path_for(small, ManufacturingContext(resource_root=str(root_b)))

    assert path_a_box == shared_a / "盒子.dxf"
    assert path_a_door == shared_a / "小門.dxf"
    assert path_b_box == shared_b / "盒子.dxf"
    assert path_b_door == shared_b / "小門.dxf"


def test_generic_baseline_helpers_and_context_root_share_the_same_resolver(monkeypatch, tmp_path):
    from ae_engine import ae
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine import manufacturing_api as api

    model = tmp_path / "基準檔" / "PW"
    model.mkdir(parents=True)
    (model / "門.dxf").write_text("door", encoding="utf-8")
    (tmp_path / "基準檔" / "開孔").mkdir(parents=True)
    monkeypatch.setattr(ae, "get_resource_path", lambda relative: str(tmp_path / relative))

    assert Path(ae.baseline_expected_path("PW", "門.dxf")) == model / "門.dxf"
    assert Path(ae.baseline_part_path("PW", "門.dxf")) == model / "門.dxf"
    assert Path(ae.baseline_hole_catalog_root_path()) == tmp_path / "基準檔" / "開孔"

    spec = DoorPartSpec(width=500, height=600, thickness=2, frame_width=25, model_name="PW")
    expected = api.expected_baseline_path_for(spec, ManufacturingContext(resource_root=str(tmp_path)))
    assert expected == model / "門.dxf"


def _write_real_shared_baselines(root: Path, name: str) -> Path:
    import ezdxf

    folder = root / "基準檔" / name
    folder.mkdir(parents=True, exist_ok=True)

    box = ezdxf.new("R2010")
    for layer in ("CUTTING", "BEND"):
        if layer not in box.layers:
            box.layers.add(layer)
    msp = box.modelspace()
    msp.add_lwpolyline([(0, 0), (326, 0), (326, 445), (0, 445)], close=True, dxfattribs={"layer": "CUTTING"})
    for a, b in [((49,0),(49,445)), ((277,0),(277,445)), ((0,49),(326,49)), ((0,396),(326,396))]:
        msp.add_line(a, b, dxfattribs={"layer": "BEND"})
    box.saveas(folder / "盒子.dxf")

    door = ezdxf.new("R2010")
    if "BEND" not in door.layers:
        door.layers.add("BEND")
    msp = door.modelspace()
    w, h, fold = 254.0, 374.0, 19.0
    msp.add_lwpolyline([(0,0),(w,0),(w,h),(0,h)], close=True, dxfattribs={"layer": "0"})
    for a, b in [((fold,0),(fold,h)), ((w-fold,0),(w-fold,h)), ((0,fold),(w,fold)), ((0,h-fold),(w,h-fold))]:
        msp.add_line(a, b, dxfattribs={"layer": "BEND"})
    door.saveas(folder / "小門.dxf")
    return folder


def test_real_exports_follow_resolver_with_arbitrary_shared_folder_name(monkeypatch, tmp_path):
    from ae_engine import ae
    from ae_engine.contracts import IndicatorBoxPartSpec, ManufacturingContext
    from ae_engine import manufacturing_api as api

    shared = _write_real_shared_baselines(tmp_path, "完全任意名稱")
    monkeypatch.setattr(ae, "config", _fresh_config())
    ctx = ManufacturingContext(resource_root=str(tmp_path))

    box_out = tmp_path / "box_out.dxf"
    box_result = api.generate_part(IndicatorBoxPartSpec(layer_groups=(1,), thickness=2.0), box_out, ctx)
    assert box_out.is_file()
    assert Path(box_result.baseline_path) == shared / "盒子.dxf"

    door_out = tmp_path / "door_out.dxf"
    small = api.indicator_small_door_spec((1,), thickness=2.0)
    door_result = api.generate_part(small, door_out, ctx)
    assert door_out.is_file()
    assert Path(door_result.baseline_path) == shared / "小門.dxf"
