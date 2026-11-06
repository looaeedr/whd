"""#2517 geometry-only Engine batch reopens all real DXFs BEFORE publishing.

Geometry validation is separate from trusted source revision certification.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import (
    DoorPartSpec, ManufacturingContext,
    ResolvedManufacturingGeometry, ResolvedManufacturingPart,
)


def _batch():
    spec = DoorPartSpec(
        width=500, height=600, thickness=2,
        frame_width=25, model_name="金庫型",
    )
    ctx = ManufacturingContext(
        resource_root=Path(__file__).resolve().parents[1], draw_stock=False,
    )
    render = manufacturing_api.build_operator_part_render_data(spec, ctx)
    return (("set1__bay1", ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(part_key="door", render_data=render),
    ))),)


def test_geometry_only_batch_reopens_and_matches_actual_canonical_dxf(tmp_path):
    batch = _batch()
    target = tmp_path / "geometry"
    files = manufacturing_api.save_resolved_manufacturing_geometry_batch_dxf(
        batch, target, verify_reopen=True,
    )
    assert len(files) == 1
    path = Path(next(iter(files.values())))
    assert path.parent == target
    assert not ezdxf.readfile(path).audit().errors
    verification = manufacturing_api.verify_saved_resolved_manufacturing_geometry_batch_dxf(
        batch, target,
    )
    assert verification.ok, verification.issues
    assert not list(target.glob(".whd-dxf-stage-*"))


def test_bad_reopen_preserves_previously_approved_batch_bytes(tmp_path, monkeypatch):
    from ae_engine import manufacturing_verification

    batch = _batch()
    target = tmp_path / "geometry"
    original = manufacturing_api.save_resolved_manufacturing_geometry_batch_dxf(
        batch, target, verify_reopen=True,
    )
    path = Path(next(iter(original.values())))
    previous_bytes = path.read_bytes()
    monkeypatch.setattr(
        manufacturing_verification, "verify_saved_part_render_data_dxf",
        lambda *_a, **_k: SimpleNamespace(ok=False),
    )
    with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
        manufacturing_api.save_resolved_manufacturing_geometry_batch_dxf(
            batch, target, overwrite=True, verify_reopen=True,
        )
    assert path.read_bytes() == previous_bytes
    assert not list(target.glob(".whd-dxf-stage-*"))
    assert not list(target.glob(".whd-dxf-backup-*"))


@pytest.mark.parametrize("bad", [0, 1, None, "true"])
def test_geometry_only_option_rejects_boolean_coercion(tmp_path, bad):
    with pytest.raises(TypeError, match="verify_reopen must be bool"):
        manufacturing_api.save_resolved_manufacturing_geometry_batch_dxf(
            _batch(), tmp_path / "output", verify_reopen=bad,
        )
    assert not (tmp_path / "output").exists()


def test_source_guarded_manufacturing_cannot_be_bypassed(tmp_path):
    with pytest.raises(ValueError, match="WHD_PRECOMMIT_GUARD_REQUIRED"):
        manufacturing_api.save_verified_resolved_manufacturing_geometry_batch_dxf(
            _batch(), tmp_path / "protected", pre_commit_guard=None,
        )
    assert not (tmp_path / "protected").exists()
