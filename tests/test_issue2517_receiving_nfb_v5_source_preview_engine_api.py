# -*- coding: utf-8 -*-
"""#2517 public Engine NFB V5 source identity/cache, source-only GUI boundary."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_numeric_catalog import NfbNumericSpec
import ae_engine.receiving_nfb_v5_source_preview as owner
from gui_modules.application import receiving_nfb_source_preview as gui


def _spec(brand="士林", model="100HN-s"):
    return NfbNumericSpec(
        brand=brand, model=model, width_mm=75., height_mm=130., depth_mm=68.,
        opening_mm=(25., 95.), screw_pitch_mm=(25., 111.),
        screw_diameter_mm=3.2,
    )


def test_engine_source_identity_and_revision_cache_do_not_reparse_same_model(tmp_path, monkeypatch):
    path = tmp_path / "NFB數值規格.csv"
    path.write_text("first-original", encoding="utf-8")
    calls = []
    monkeypatch.setattr(owner, "brand_csv_path", lambda brand: path)
    monkeypatch.setattr(owner, "selected_numeric_spec", lambda brand, ref: (
        calls.append((brand, ref)) or _spec()
    ))
    cache = manufacturing_api.ReceivingNfbV5SourcePreviewCache(max_entries=2)
    ref = "nfbv5:士林:100HN-s"
    a = cache.load("士林", ref)
    assert isinstance(a, manufacturing_api.ReceivingNfbV5SourcePreview)
    assert a.spec == _spec()
    assert a.manufacturing_ready is False
    assert a.source_key[:3] == ("v5", "士林", ref)
    assert cache.load("士林", ref) is a
    assert cache.parse_count == 1 and calls == [("士林", ref)]
    with pytest.raises(FrozenInstanceError):
        a.manufacturing_ready = True
    path.write_text("edited-original-with-new-source-data", encoding="utf-8")
    b = cache.load("士林", ref)
    assert b is not a and b.source_key != a.source_key
    assert cache.parse_count == 2 and len(cache._entries) == 1
    assert calls == [("士林", ref)] * 2


@pytest.mark.parametrize("model_ref,brand", [
    ("nfbv5:東元:100HN-s", "士林"),
    ("nfbv5:壞廠牌:100HN-s", "士林"),
    ("100HN-s.dxf", "士林"),
    ("nfbv5:士林:", "士林"),
])
def test_unknown_or_wrong_brand_never_reads_csv(tmp_path, monkeypatch, model_ref, brand):
    monkeypatch.setattr(owner, "brand_csv_path", lambda _: pytest.fail("must not read CSV"))
    with pytest.raises(ValueError, match="廠牌"):
        manufacturing_api.ReceivingNfbV5SourcePreviewCache().load(brand, model_ref)


def test_missing_model_and_source_revision_race_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "NFB數值規格.csv"
    path.write_text("original", encoding="utf-8")
    monkeypatch.setattr(owner, "brand_csv_path", lambda brand: path)
    cache = manufacturing_api.ReceivingNfbV5SourcePreviewCache()
    monkeypatch.setattr(owner, "selected_numeric_spec", lambda *args: None)
    with pytest.raises(ValueError, match="已無此型號"):
        cache.load("士林", "nfbv5:士林:100HN-s")
    assert cache.parse_count == 0
    def concurrent_change(*args):
        path.write_text("changed-while-reading", encoding="utf-8")
        return _spec()
    monkeypatch.setattr(owner, "selected_numeric_spec", concurrent_change)
    with pytest.raises(ValueError, match="讀取期間來源版本變更"):
        cache.load("士林", "nfbv5:士林:100HN-s")
    assert cache.parse_count == 0


def test_brand_model_provenance_mismatch_does_not_silently_accept(tmp_path, monkeypatch):
    path = tmp_path / "NFB數值規格.csv"
    path.write_text("original", encoding="utf-8")
    monkeypatch.setattr(owner, "brand_csv_path", lambda brand: path)
    monkeypatch.setattr(owner, "selected_numeric_spec", lambda *args: _spec("東元", "100HN-s"))
    with pytest.raises(ValueError, match="身份不一致"):
        manufacturing_api.ReceivingNfbV5SourcePreviewCache().load(
            "士林", "nfbv5:士林:100HN-s",
        )


def test_gui_reads_public_engine_cache_and_does_not_own_model_csv_identity():
    src = inspect.getsource(gui)
    assert "manufacturing_api.ReceivingNfbV5SourcePreviewCache()" in src
    assert "self._numeric_sources.load(brand,filename)" in src
    assert "parse_numeric_model_ref(" not in src
    assert "selected_numeric_spec(" not in src
    assert "brand_csv_path(" not in src
    assert "self._numeric_sources[key]" not in src
    assert "_numeric_zoom=1.0" in src


def test_gui_v5_source_selection_reuses_engine_revision_without_repainting_fake_holes(tmp_path, monkeypatch):
    path = tmp_path / "NFB數值規格.csv"
    path.write_text("source-rev-A", encoding="utf-8")
    monkeypatch.setattr(owner, "brand_csv_path", lambda brand: path)
    monkeypatch.setattr(owner, "selected_numeric_spec", lambda *args: _spec())

    class Surface:
        def __init__(self):
            self.text = ""
        def configure(self, **kwargs):
            self.text = kwargs.get("text", self.text)
        def set(self, value):
            self.text = value

    panel = gui.NfbDxfSourcePreviewPanel.__new__(gui.NfbDxfSourcePreviewPanel)
    panel.frame = Surface()
    panel.identity = Surface()
    panel.reason = Surface()
    panel.viewport = SimpleNamespace(preview=None)
    panel._numeric_sources = manufacturing_api.ReceivingNfbV5SourcePreviewCache()
    panel._numeric_mode = False
    panel._numeric_spec = None
    panel._source_key = None
    panel._numeric_pan = (11., 7.)
    panel._numeric_zoom = 2.
    paints = []
    panel.paint = lambda: paints.append(panel._numeric_spec)
    ref = "nfbv5:士林:100HN-s"
    panel.show("士林", ref)
    assert panel._numeric_mode is True
    assert panel.identity.text.startswith("士林｜100HN-s")
    assert "僅預覽" in panel.reason.text
    assert panel._numeric_sources.parse_count == 1
    assert panel._numeric_zoom == 1. and panel._numeric_pan == (0., 0.)
    panel._numeric_zoom = 3.0
    panel.show("士林", ref)
    assert panel._numeric_sources.parse_count == 1
    assert panel._numeric_zoom == 3.0
    assert paints == [_spec(), _spec()]
    path.write_text("source-rev-B-changed", encoding="utf-8")
    panel.show("士林", ref)
    assert panel._numeric_sources.parse_count == 2
    assert panel._numeric_zoom == 1.0
    panel.show("東元", ref)
    assert panel._numeric_spec is None
    assert "禁止製造" in panel.reason.text
    assert "100HN-s" in panel.identity.text
