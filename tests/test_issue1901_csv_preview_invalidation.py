# -*- coding: utf-8 -*-
"""The current NFB source is CSV; invalid rechecks must clear stale GUI CAD."""
from types import SimpleNamespace

import pytest

from gui_modules.application.receiving_nfb_source_preview import (
    NfbDxfSourcePreviewPanel,
)
from gui_modules.application.receiving_nfb_v5_scene_preview import (
    clear_v5_checked_geometry_preview,
)


class _Text:
    def __init__(self):
        self.value = ""
    def set(self, value):
        self.value = str(value)


class _Frame:
    def __init__(self):
        self.title = ""
    def configure(self, **kwargs):
        self.title = kwargs["text"]


class _Canvas:
    def __init__(self):
        self.deleted = []
    def delete(self, tag):
        self.deleted.append(tag)


class _Book:
    def __init__(self, primary, second, *, visible=True):
        self.primary = primary
        self.second = second
        self.visible = visible
        self.forgot = []
        self.title = None
    def tabs(self):
        return [str(self.primary)] + ([str(self.second)] if self.visible else [])
    def forget(self, item):
        self.forgot.append(item)
        self.visible = False
    def tab(self, item, *, text):
        assert item == self.primary
        self.title = text


@pytest.mark.parametrize("visible", (True, False))
def test_failed_csv_recheck_erases_both_layers_and_previous_door_cad(visible):
    door, base, second = _Canvas(), _Canvas(), _Canvas()
    primary_tab, second_tab = object(), object()
    book = _Book(primary_tab, second_tab, visible=visible)
    popup = SimpleNamespace(
        _receiving_v5_second_base_canvas=second,
        _receiving_v5_second_base_tab=second_tab,
        _receiving_v5_base_primary_tab=primary_tab,
        _receiving_v5_tabs=book,
    )
    clear_v5_checked_geometry_preview(
        popup, door_canvas=door, base_canvas=base,
    )
    assert [door.deleted, base.deleted, second.deleted] == [
        ["v5-real-part"], ["v5-real-part"], ["v5-real-part"],
    ]
    assert book.visible is False
    assert book.forgot == ([second_tab] if visible else [])
    assert book.title == "底板尚未驗證"


def _source_panel():
    panel = NfbDxfSourcePreviewPanel.__new__(NfbDxfSourcePreviewPanel)
    panel.frame = _Frame()
    panel.identity = _Text()
    panel.reason = _Text()
    panel.viewport = SimpleNamespace(preview=None)
    panel._source_key = None
    panel._numeric_mode = False
    panel._numeric_spec = None
    # __new__ bypasses the real Tk constructor: initialize the full cache contract.
    panel._numeric_sources = {}
    panel._index_path = None
    panel.paint = lambda: None
    panel.cache = SimpleNamespace(load=lambda *a, **k: (_ for _ in ()).throw(
        ValueError("legacy source unavailable")
    ))
    return panel


def test_csv_model_shows_csv_label_never_claims_original_dxf():
    panel = _source_panel()
    panel.show("士林", "nfbv5:士林:2P400")
    assert "CSV" in panel.frame.title
    assert "DXF" not in panel.frame.title
    assert "2P400" in panel.identity.value
    assert panel._numeric_mode and panel._numeric_spec is not None
    assert "未經實體／製造驗證" in panel.reason.value
    panel.show("東元", "nfbv5:士林:2P400")
    assert "CSV" in panel.frame.title
    assert "禁止製造" in panel.reason.value
    assert panel._numeric_mode and panel._numeric_spec is None


def test_legacy_preview_keeps_explicit_dxf_label_and_empty_slot_neutral():
    panel = _source_panel()
    panel.show("士林", "400_140X257_107.dxf")
    assert "舊 DXF" in panel.frame.title
    assert "來源無法查證" in panel.reason.value
    assert not panel._numeric_mode
    panel.show("士林", None)
    assert panel.frame.title == "NFB 型號來源｜僅預覽"
    assert panel.identity.value == "空槽｜尚未選型"
