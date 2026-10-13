# -*- coding: utf-8 -*-
"""Receiving shares certified Vault DXF FEATURES, not Vault box geometry."""
from __future__ import annotations

from types import SimpleNamespace

from ae_engine import ae
from ae_engine.cabinet_types import policy as cabinet_family_policy
from gui_modules.rendering.box_body_view import box_body_baseline_faces


def test_receiving_fixed_box_features_read_certified_vault_dxf(monkeypatch):
    assert cabinet_family_policy.baseline_feature_model_name("受電箱") == "金庫型"
    assert ae.has_baseline_part("金庫型", "箱身.dxf")
    assert not ae.has_baseline_part("受電箱", "箱身.dxf")
    calls = []
    original = ae.baseline_part_path

    def observe(model, part):
        calls.append((model, part))
        return original(model, part)

    monkeypatch.setattr(ae, "baseline_part_path", observe)
    kwargs = dict(total_length=1700.0, total_height=1600.0,
                  zl1=-24.0, zl2=24.0, zr1=18.0, zr2=18.0,
                  z_comp=2.0, w=800.0, d=350.0, t=2.0, fw=29.0)
    receiving = ae.get_box_body_baseline_unfolded_features("受電箱", **kwargs)
    vault = ae.get_box_body_baseline_unfolded_features("金庫型", **kwargs)
    assert receiving == vault
    assert receiving, "Receiving must load actual certified DXF features, not two empty lists"
    assert ("金庫型", "箱身.dxf") in calls
    assert ("受電箱", "箱身.dxf") not in calls
    assert ae.box_body_baseline_source_label("受電箱") == (
        "基準檔：金庫型/箱身.dxf（固定特徵映射）"
    )


def test_box_body_preview_reads_shared_feature_source_only():
    observed = []
    mock_ae = SimpleNamespace(
        has_baseline_part=lambda model, filename: observed.append(("exists", model)) or True,
        baseline_expected_path=lambda model, filename: observed.append(("path", model)) or "source.dxf",
        baseline_source_fingerprint=lambda path: ("fingerprint", path),
        get_box_body_baseline_face_features=lambda model, **kwargs:
            observed.append(("features", model)) or {"left": [], "back": [], "right": []},
    )
    host = SimpleNamespace(
        _baseline_source_model=lambda: "受電箱",
        _box_body_corner_policies=lambda fw: (None, None),
        _box_body_baseline_face_cache={},
    )
    values = dict(w=800, h=1600, d=350, t=2, fw=29,
                  zl1=-24, zl2=24, zr1=0, zr2=18, z_comp=2)
    result = box_body_baseline_faces(host, values, ae_module=mock_ae)
    assert result == {"left": [], "back": [], "right": []}
    assert observed == [
        ("exists", "金庫型"), ("path", "金庫型"),
        ("features", "金庫型"),
    ]


def test_receiving_family_geometry_remains_receiving_specific():
    from ae_engine.cabinet_types import receiving
    assert receiving.BOX_BODY_DEFAULTS["fw"] == 29.0
    assert receiving.BASE_PLATE_DEFAULTS["base_plate_shrink_top"] == 55.0
    assert cabinet_family_policy.baseline_feature_model_name("金庫型") == "金庫型"
