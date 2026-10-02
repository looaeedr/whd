from __future__ import annotations

from pathlib import Path

from ae_engine import ae
from gui import _Phase6DerivedCacheOwner


def test_invalidation_matrix_is_precise_and_display_safe():
    owner = _Phase6DerivedCacheOwner()
    for name in owner.PRODUCTS:
        owner.cache(name)["sentinel"] = name

    assert owner.invalidate("display") == ()
    assert owner.invalidate("camera") == ()
    assert all(owner.cache(name) for name in owner.PRODUCTS)

    assert owner.invalidate("assembly") == ("authoritative_render", "box_body_faces")
    assert owner.cache("door_layout") == {"sentinel": "door_layout"}
    assert owner.cache("box_body_faces") == {}
    assert owner.cache("authoritative_render") == {}


def test_geometry_invalidation_never_clears_immutable_source_cache(tmp_path, monkeypatch):
    path = tmp_path / "part.dxf"
    path.write_text("dummy", encoding="utf-8")
    reads = []
    sentinel = object()
    monkeypatch.setattr(ae.ezdxf, "readfile", lambda p: (reads.append(str(p)) or sentinel))
    ae.clear_baseline_dxf_source_cache()

    assert ae.load_baseline_dxf_source(path) is sentinel
    owner = _Phase6DerivedCacheOwner()
    for _ in range(5):
        owner.invalidate("geometry", {"w", "h", "d", "fw"})
        assert ae.load_baseline_dxf_source(path) is sentinel

    assert reads == [str(path)]


def test_source_fingerprint_changes_on_force_reload_even_when_stat_is_same(tmp_path):
    path = tmp_path / "part.dxf"
    path.write_text("dummy", encoding="utf-8")
    before = ae.baseline_source_fingerprint(path)
    ae.force_reload_baseline_dxf_sources()
    after = ae.baseline_source_fingerprint(path)
    assert before[:-1] == after[:-1]
    assert after[-1] == before[-1] + 1


def test_manufacturing_source_gate_rejects_source_unverified(monkeypatch):
    from gui import BoxCalculatorGUI

    fake = type("Fake", (), {})()
    fake._baseline_source_model = lambda: "金庫型"
    monkeypatch.setattr(ae, "baseline_part_path", lambda model, filename: f"/network/{filename}")
    monkeypatch.setattr(
        ae,
        "load_baseline_dxf_source_with_status",
        lambda path, allow_unverified_source=False: (object(), ae.BASELINE_SOURCE_UNVERIFIED),
    )
    import pytest
    with pytest.raises(RuntimeError, match="正式製造輸出已停止"):
        BoxCalculatorGUI._require_verified_baseline_sources_for_manufacturing(fake)
