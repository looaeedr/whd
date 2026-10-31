"""#2517: baseline source authority belongs to headless Engine, not GUI."""
from __future__ import annotations

import inspect
from pathlib import Path

from ae_engine import ae, manufacturing_api, receiving_baseline_source_stamp
from ae_engine.contracts import ManufacturingContext
from phase6_manufacturing_adapter import _receiving_baseline_source_stamp


STANDARD = ("箱身.dxf", "封頭尾.dxf", "門.dxf")
PHYSICAL = ("左側板.dxf", "右側板.dxf", "後面板.dxf")


def _source(tmp_path: Path, filename: str) -> Path:
    path = tmp_path / "基準檔" / "受電箱" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"DXF-source-witness:" + filename.encode("utf-8"))
    return path


def test_engine_public_api_owns_scoped_baseline_and_multipart_witness(tmp_path):
    paths = {name: _source(tmp_path, name) for name in STANDARD + PHYSICAL}
    ctx = ManufacturingContext(resource_root=tmp_path)
    witness = manufacturing_api.receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    )
    assert receiving_baseline_source_stamp is manufacturing_api.receiving_baseline_source_stamp
    assert tuple(row[0] for row in witness[:3]) == STANDARD
    assert tuple((row[0], row[1]) for row in witness[3:]) == (
        ("back", "後面板.dxf"),
        ("left_side", "左側板.dxf"),
        ("right_side", "右側板.dxf"),
    )
    assert witness[0][1] == tuple(ae.baseline_source_fingerprint(paths["箱身.dxf"]))
    assert witness[3][2] == tuple(ae.baseline_source_fingerprint(paths["後面板.dxf"]))
    assert witness == manufacturing_api.receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    )


def test_engine_source_witness_rejects_missing_physical_and_changes_on_edit(tmp_path):
    paths = {name: _source(tmp_path, name) for name in STANDARD + PHYSICAL}
    ctx = ManufacturingContext(resource_root=tmp_path)
    before = manufacturing_api.receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    )
    paths["後面板.dxf"].write_bytes(b"changed-physical-source")
    after = manufacturing_api.receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    )
    assert before != after
    paths["後面板.dxf"].unlink()
    assert manufacturing_api.receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    ) is None
    assert len(manufacturing_api.receiving_baseline_source_stamp("受電箱", context=ctx)) == 3


def test_engine_source_witness_retires_previous_generation(tmp_path):
    for name in STANDARD:
        _source(tmp_path, name)
    ctx = ManufacturingContext(resource_root=tmp_path)
    before = manufacturing_api.receiving_baseline_source_stamp("受電箱", context=ctx)
    ae.force_reload_baseline_dxf_sources()
    after = manufacturing_api.receiving_baseline_source_stamp("受電箱", context=ctx)
    assert before != after
    assert all(old[1][:-1] == new[1][:-1] for old, new in zip(before, after))


def test_gui_adapter_delegates_source_authority_to_public_engine(monkeypatch):
    calls = []
    token = object()

    def engine_witness(model, *, context, include_physical_panels):
        calls.append((model, context, include_physical_panels))
        return token

    monkeypatch.setattr(manufacturing_api, "receiving_baseline_source_stamp", engine_witness)
    ctx = ManufacturingContext()
    assert _receiving_baseline_source_stamp(
        "受電箱", context=ctx, include_physical_panels=True,
    ) is token
    assert calls == [("受電箱", ctx, True)]
    source = inspect.getsource(_receiving_baseline_source_stamp)
    assert "manufacturing_api.receiving_baseline_source_stamp(" in source
    assert "baseline_source_fingerprint(" not in source
    assert "baseline_part_path(" not in source
