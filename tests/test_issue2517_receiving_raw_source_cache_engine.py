"""#2517 Receiving raw material source hashes and reuse belong to Engine API."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy
from ae_engine.inner_door_panels import InnerDoorPanelPart
from gui_modules.application.fold_designer_composition_receiving import (
    _receiving_cached_bay_inner_door_panel,
    _receiving_cached_bay_inner_door_frame,
    _receiving_cached_bay_box_body_divider,
)


def _payload(model="受電箱"):
    return {"model": model, "active_mode": "set_bay", "features": ()}


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_registered_aliases_preserve_source_free_panel_key(model, monkeypatch):
    panel = InnerDoorPanelPart(
        stable_id="inner_door:source:panel", inner_door_id="source",
        cell_key="upper", width=670, height=950, thickness=2,
    )
    monkeypatch.setattr(policy, "derive_inner_door_panels", lambda data: (panel,))
    ticket = api.project_receiving_raw_source_cache_ticket(panel.stable_id, _payload(model))
    assert ticket.kind == "panel"
    assert ticket.signature
    assert api.receiving_raw_source_cache_entry_valid(ticket, object())
    assert api.project_receiving_raw_source_cache_ticket(
        panel.stable_id, {**_payload(model), "features": (object(),)},
    ) is None


@pytest.mark.parametrize("model", ("金庫型", "RO", "unknown"))
def test_non_receiving_family_cannot_reuse_any_physical_material(model):
    for kind in ("inner_door:source:panel",
                 "inner_door:source:top_frame",
                 "box_body:divider:source"):
        assert api.receiving_raw_source_cache_kind(kind, _payload(model)) is None
        assert api.project_receiving_raw_source_cache_ticket(kind, _payload(model)) is None


def test_frame_witness_exact_source_bytes_generation_and_mfg_metadata(monkeypatch, tmp_path):
    from hashlib import sha256
    from ae_engine import receiving_frame_baseline
    from ae_engine.inner_door_frames import derive_inner_door_frames
    from gui_modules.application import fold_designer_manufacturing_projection as projection

    source = tmp_path / "框.dxf"
    source.write_bytes(b"frame-source-1")
    monkeypatch.setattr(receiving_frame_baseline, "frame_source_file", lambda: source)
    frame = derive_inner_door_frames(
        "source", spans={"top": 750}, thickness=2, included_sides=("top",),
    )[0]
    monkeypatch.setattr(projection, "_inner_door_frame_from_payload",
                        lambda key, payload: frame)
    material = SimpleNamespace(metadata={
        "receiving_frame_source_path": str(source),
        "receiving_frame_source_sha256": sha256(source.read_bytes()).hexdigest(),
    })
    t = api.project_receiving_raw_source_cache_ticket(
        frame.stable_id, _payload("receiving"), typed_part=frame,
    )
    assert t is not None and api.receiving_raw_source_cache_entry_valid(t, material)
    owner = SimpleNamespace()
    assert _receiving_cached_bay_inner_door_frame(
        owner, frame.stable_id, _payload(), lambda: material,
    ) is material
    assert _receiving_cached_bay_inner_door_frame(
        owner, frame.stable_id, _payload(),
        lambda: (_ for _ in ()).throw(AssertionError("should reuse")),
    ) is material
    source.write_bytes(b"frame-source-2")
    assert not api.receiving_raw_source_cache_entry_valid(t, material)
    assert _receiving_cached_bay_inner_door_frame(
        owner, frame.stable_id, _payload(), lambda: object(),
    ) is not material
    source.unlink()
    assert api.project_receiving_raw_source_cache_ticket(
        frame.stable_id, _payload(), typed_part=frame,
    ) is None


def test_gui_raw_cache_contains_no_source_or_manufacturing_signatures():
    source = (Path(__file__).resolve().parents[1] /
              "gui_modules/application/fold_designer_composition_receiving.py"
              ).read_text(encoding="utf-8")
    section = source.split("def _receiving_cached_bay_inner_door_panel(")[1].split(
        "def _retain_committed_receiving_bay_preview(", 1,
    )[0]
    assert "manufacturing_api.project_receiving_raw_source_cache_ticket" in section
    assert "manufacturing_api.receiving_raw_source_cache_entry_valid" in section
    assert "baseline_source_fingerprint" not in section
    assert "manufacturing_fingerprint" not in section
    assert "sha256(" not in section
    assert "model\"\u0029 in" not in section
    engine = (Path(__file__).resolve().parents[1] /
              "ae_engine/receiving_raw_source_cache.py").read_text(encoding="utf-8")
    assert "from gui_modules" not in engine and "from phase6_" not in engine
