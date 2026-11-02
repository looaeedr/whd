"""#2517: Fold Designer manufacturing source verification belongs to public Engine."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_baseline_policy as policy
from gui_modules.application import fold_designer_manufacturing_projection as gui


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "金庫型"))
def test_engine_preflight_verifies_each_present_optional_source(model, monkeypatch):
    looked_up, loaded = [], []

    def path_for(selected, filename):
        looked_up.append((selected, filename))
        return filename if filename != "門.dxf" else None

    def load(path, *, allow_unverified_source):
        loaded.append((path, allow_unverified_source))
        return object(), policy.ae.BASELINE_SOURCE_VERIFIED

    monkeypatch.setattr(policy.ae, "baseline_part_path", path_for)
    monkeypatch.setattr(policy.ae, "load_baseline_dxf_source_with_status", load)
    assert api.require_verified_operator_baseline_sources(model) is True
    assert looked_up == [(model, n) for n in ("箱身.dxf", "封頭尾.dxf", "門.dxf")]
    assert loaded == [("箱身.dxf", False), ("封頭尾.dxf", False)]


def test_unset_operator_model_preserves_existing_noop(monkeypatch):
    monkeypatch.setattr(policy.ae, "baseline_part_path",
                        lambda *_: pytest.fail("an unset model must not resolve files"))
    assert api.require_verified_operator_baseline_sources("") is True
    assert api.require_verified_operator_baseline_sources(None) is True


def test_unverified_existing_source_never_passes_manufacturing_preflight(monkeypatch):
    monkeypatch.setattr(policy.ae, "baseline_part_path", lambda *_: "封頭尾.dxf")
    monkeypatch.setattr(policy.ae, "load_baseline_dxf_source_with_status",
                        lambda _path, *, allow_unverified_source: (None, "SOURCE_UNVERIFIED"))
    with pytest.raises(RuntimeError, match="基準來源尚未驗證：受電箱/箱身.dxf"):
        api.require_verified_operator_baseline_sources("受電箱")


def test_real_broken_dxf_does_not_fall_back_to_last_known_good(tmp_path, monkeypatch):
    path = tmp_path / "封頭尾.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline(
        [(0, 0), (100, 0), (100, 80), (0, 80)], close=True,
    )
    doc.saveas(path)
    monkeypatch.setattr(
        policy.ae, "baseline_part_path",
        lambda _model, filename: str(path) if filename == "封頭尾.dxf" else None,
    )
    assert api.require_verified_operator_baseline_sources("受電箱") is True
    path.write_text("corrupt and not a valid DXF", encoding="utf-8")
    policy.ae.force_reload_baseline_dxf_sources()
    with pytest.raises((OSError, ezdxf.DXFError)):
        api.require_verified_operator_baseline_sources("受電箱")


def test_gui_preflight_forwards_model_to_public_engine_without_source_logic(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api, "require_verified_operator_baseline_sources",
        lambda model: calls.append(model) or True,
    )
    host = SimpleNamespace(_baseline_source_model=lambda: "受電箱")
    assert gui._require_verified_baseline_sources_for_manufacturing(host) is True
    assert gui._require_verified_baseline_sources_for_manufacturing(
        SimpleNamespace()
    ) is True
    assert calls == ["受電箱", ""]
    source = inspect.getsource(gui._require_verified_baseline_sources_for_manufacturing)
    assert "manufacturing_api.require_verified_operator_baseline_sources(" in source
    assert "baseline_part_path(" not in source
    assert "load_baseline_dxf_source_with_status(" not in source
    assert "_require_verified_baseline_sources_for_manufacturing()" in inspect.getsource(
        gui._export_authoritative_part
    )
