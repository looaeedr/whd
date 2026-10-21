# -*- coding: utf-8 -*-
"""GUI PAD 3D never reuses a stale source or silently hides its failure."""
from types import SimpleNamespace

import pytest
from shapely.geometry import box

from ae_engine.receiving_nfb_pad_preview_cache import (
    pad_preview_source_fingerprint,
)


def test_pad_cache_changes_with_tooling_csv_and_real_base_shape(tmp_path,monkeypatch):
    import ae_engine.receiving_nfb_numeric_catalog as catalog
    import ae_engine.receiving_nfb_pad_generator as generator
    import ae_engine.receiving_nfb_pad_preview_cache as cache

    # Test the same file-backed source graph without touching the project DB.
    source=tmp_path/"base"
    (source/"基準檔/開孔/NFB").mkdir(parents=True)
    tooling=source/"基準檔/開孔/NFB/墊高片共用加工規則.json"
    tooling.write_text('{"source":"first"}',encoding="utf-8")
    csv=tmp_path/"active_model.csv"
    csv.write_bytes(b"one")
    monkeypatch.setattr(cache,"__file__",str(source/"ae_engine"/"receiving_nfb_pad_preview_cache.py"))
    monkeypatch.setattr(catalog,"brand_csv_path",lambda _brand:csv)
    snap={"model":"受電箱","nfb_config":{"holes":[
        {"model_filename":"nfbv5:士林:100HN-s"}]}}
    def part(material):
        return SimpleNamespace(
            part_key="base_plate",offset=(0.,120.,-140.),
            render_data=SimpleNamespace(material=material,fold_guides=(),
                unfolded_topology="root",metadata={"nfb_v5_pad_square_owners":()}))
    a=pad_preview_source_fingerprint(snap,(part(box(0,0,100,100)),))
    csv.write_bytes(b"two")
    b=pad_preview_source_fingerprint(snap,(part(box(0,0,100,100)),))
    assert b!=a
    tooling.write_text('{"source":"second"}',encoding="utf-8")
    c=pad_preview_source_fingerprint(snap,(part(box(0,0,100,100)),))
    assert c!=b
    d=pad_preview_source_fingerprint(snap,(part(box(0,0,99,100)),))
    assert d!=c
    csv.unlink()
    with pytest.raises(FileNotFoundError):
        pad_preview_source_fingerprint(snap,(part(box(0,0,100,100)),))


def test_gui_exposes_pad_failure_as_visible_warning_not_success():
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter
    adapter=Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    adapter.last_formed_pad_display_blocker="PAD_BASE_LOCATOR_SQUARES_NOT_SAME_OWNER"
    assert "PAD_BASE_LOCATOR_SQUARES_NOT_SAME_OWNER" in (
        " ".join(adapter._pad_display_warnings())
    )
    adapter.last_formed_pad_display_blocker=None
    assert adapter._pad_display_warnings()==()
