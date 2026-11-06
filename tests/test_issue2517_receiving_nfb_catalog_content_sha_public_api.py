# -*- coding: utf-8 -*-
"""#2517: original Receiving NFB model dropdown uses Engine CSV content revision.

A same-size, same-mtime replacement was previously invisible to the GUI
poller's (mtime_ns, size) signature. No NFB hole or DXF is certified here.
"""
import csv
from dataclasses import FrozenInstanceError
from inspect import getsource
import os

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_numeric_catalog as numeric
from ae_engine import receiving_nfb_model_identity as identities
from ae_engine.receiving_nfb_v5_source_preview import (
    ReceivingNfbV5ModelCatalogSnapshot,
    project_receiving_nfb_v5_model_catalog_snapshot as canonical,
)
from gui_modules.application import fold_designer_composition_receiving as gui


def _write_brand_csv(tmp_path, model):
    path = tmp_path / numeric.RELATIVE_DIRECTORY / "士林" / numeric.FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(numeric.HEADER)
        writer.writerow((model, 75, 130, 68, "28X58", "25X111", 3.2, "", ""))
    return path


def test_same_mtime_and_size_different_real_csv_changes_catalog_source_sha(monkeypatch, tmp_path):
    monkeypatch.setattr(numeric, "PROJECT_ROOT", tmp_path)
    path = _write_brand_csv(tmp_path, "MODEL-A")
    first = api.project_receiving_nfb_v5_model_catalog_snapshot("士林")
    assert first == canonical("士林")
    assert first.model_refs == ("nfbv5:士林:MODEL-A",)
    assert first.manufacturing_ready is False
    old = path.stat()

    _write_brand_csv(tmp_path, "MODEL-B")  # same-length brand/model, not a fake mock
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
    stat = path.stat()
    assert (stat.st_mtime_ns, stat.st_size) == (old.st_mtime_ns, old.st_size)
    # This was the original GUI cache key, so it would not refresh.
    second = api.project_receiving_nfb_v5_model_catalog_snapshot("士林")
    assert second.model_refs == ("nfbv5:士林:MODEL-B",)
    assert first.model_refs == ("nfbv5:士林:MODEL-A",)
    assert first.source_sha256 != second.source_sha256
    assert second.source_sha256 and len(second.source_sha256) == 64


def test_public_snapshot_is_immutable_exact_engine_owner_not_manufacturing_grant():
    assert api.project_receiving_nfb_v5_model_catalog_snapshot is canonical
    assert ae_engine.project_receiving_nfb_v5_model_catalog_snapshot is canonical
    assert ae_engine.ReceivingNfbV5ModelCatalogSnapshot is ReceivingNfbV5ModelCatalogSnapshot
    assert "project_receiving_nfb_v5_model_catalog_snapshot" in ae_engine.__all__
    with pytest.raises(FrozenInstanceError):
        ReceivingNfbV5ModelCatalogSnapshot("士林", "sha", ()).brand = "東元"


def test_invalid_and_mid_read_csv_changes_fail_closed_without_stale_inventory(monkeypatch, tmp_path):
    monkeypatch.setattr(numeric, "PROJECT_ROOT", tmp_path)
    path = _write_brand_csv(tmp_path, "MODEL-A")
    with pytest.raises(ValueError, match="不支援"):
        api.project_receiving_nfb_v5_model_catalog_snapshot("未知品牌")

    path.write_text("bad,header\nMODEL-A,75\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="欄位"):
        api.project_receiving_nfb_v5_model_catalog_snapshot("士林")

    _write_brand_csv(tmp_path, "MODEL-A")
    original = identities.numeric_model_refs

    def replace_during_parse(brand):
        models = original(brand)
        _write_brand_csv(tmp_path, "MODEL-B")
        return models

    monkeypatch.setattr(identities, "numeric_model_refs", replace_during_parse)
    with pytest.raises(ValueError, match="SOURCE_CHANGED_DURING_READ"):
        api.project_receiving_nfb_v5_model_catalog_snapshot("士林")


def test_original_nfb_editor_poll_only_consumes_public_engine_source_snapshot():
    source = getsource(gui)
    begin = source.index("        def refresh_source(*, force=False):")
    end = source.index("        poll_job =", begin)
    poller = source[begin:end]
    assert "manufacturing_api.project_receiving_nfb_v5_model_catalog_snapshot(" in poller
    assert "catalog.source_sha256" in poller
    assert "files = catalog.model_refs" in poller
    assert 'source_state["signature"][index] = None' in poller
    assert "brand_csv_path" not in poller
    assert "stat.st_mtime_ns" not in poller
    assert "manufacturing_api.list_receiving_nfb_model_refs(" not in poller


def test_repeated_unchanged_csv_polls_do_not_reparse_original_model_catalog(monkeypatch, tmp_path):
    monkeypatch.setattr(numeric, "PROJECT_ROOT", tmp_path)
    _write_brand_csv(tmp_path, "MODEL-A")
    original = identities.numeric_model_refs
    calls = []

    def counted(brand):
        calls.append(brand)
        return original(brand)

    monkeypatch.setattr(identities, "numeric_model_refs", counted)
    first = api.project_receiving_nfb_v5_model_catalog_snapshot("士林")
    for _ in range(8):
        assert api.project_receiving_nfb_v5_model_catalog_snapshot("士林") == first
    assert calls == ["士林"]

    _write_brand_csv(tmp_path, "MODEL-B")
    second = api.project_receiving_nfb_v5_model_catalog_snapshot("士林")
    assert calls == ["士林", "士林"]
    assert second.model_refs != first.model_refs
    assert second.source_sha256 != first.source_sha256
