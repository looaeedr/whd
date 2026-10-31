"""#2517/#2378: EndCap fixed-feature source is Engine Family authority."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from ae_engine import manufacturing_api, expected_endcap_feature_baseline
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from integration_cli.worker_receiving_endcap import receiving_endcap_shared_baseline


@pytest.mark.parametrize("family", ["受電箱", "金庫型"])
def test_headless_endcap_shared_feature_source_is_owned_by_family_policy(tmp_path, family):
    ctx = ManufacturingContext(resource_root=tmp_path)
    source_model = family_policy.baseline_feature_model_name(family)
    assert source_model == "金庫型"
    expected = tmp_path / "基準檔" / source_model / "封頭尾.dxf"
    assert manufacturing_api.expected_endcap_feature_baseline(family, ctx) == expected
    assert expected_endcap_feature_baseline is manufacturing_api.expected_endcap_feature_baseline
    # Expected path is meaningful before a file exists, but is NOT certified
    # manufacturing permission; external Prepare checks actual content bytes.
    assert not expected.exists()
    assert Path(receiving_endcap_shared_baseline(tmp_path)) == expected


def test_shared_feature_source_never_falls_back_to_unknown_family(tmp_path):
    ctx = ManufacturingContext(resource_root=tmp_path)
    with pytest.raises(ValueError, match="WHD_ENDCAP_FEATURE_SOURCE_FAMILY_UNAVAILABLE"):
        manufacturing_api.expected_endcap_feature_baseline("", ctx)


def test_worker_endcap_uses_public_engine_source_no_hardcoded_vault_path():
    source = inspect.getsource(receiving_endcap_shared_baseline)
    assert 'expected_endcap_feature_baseline(' in source
    assert '"金庫型"' not in source
    assert '"封頭尾.dxf"' not in source
