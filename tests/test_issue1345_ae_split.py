from __future__ import annotations

import inspect

from ae_engine import ae
from ae_engine import ae_config


def test_issue1345_config_owner_is_extracted_without_public_api_break():
    assert ae.get_resource_path is ae_config.get_resource_path
    for name in ("W", "H", "D", "T", "FW", "RELIEF_CONFIG", "VAULT_ENDCAP_FEATURE_POLICY"):
        assert getattr(ae, name) == getattr(ae_config, name)


def test_issue1345_ae_facade_shrinks_and_config_owner_is_one_way():
    assert len(inspect.getsource(ae).splitlines()) < 1900
    owner = inspect.getsource(ae_config)
    assert "from .ae import" not in owner
    assert "import ae_engine.ae" not in owner


def test_issue1345_calculation_owner_is_extracted_one_way():
    from ae_engine import ae_calculations
    assert ae.calculate_z_length is ae_calculations.calculate_z_length
    assert ae.calculate_y_width is ae_calculations.calculate_y_width
    assert ae.calculate_door_finished_size is ae_calculations.calculate_door_finished_size
    assert len(inspect.getsource(ae).splitlines()) < 1800
    owner = inspect.getsource(ae_calculations)
    assert "from .ae import" not in owner
    assert "import ae_engine.ae" not in owner


def test_issue1345_endcap_owner_is_extracted_one_way():
    from ae_engine import ae_endcap
    assert ae.export_end_cap_dxf is ae_endcap.export_end_cap_dxf
    assert ae.export_stretched_end_cap_dxf is ae_endcap.export_stretched_end_cap_dxf
    assert ae.baseline_part_path is ae_endcap.baseline_part_path
    assert len(inspect.getsource(ae).splitlines()) < 1500
    owner = inspect.getsource(ae_endcap)
    assert "from .ae import" not in owner
    assert "import ae_engine.ae" not in owner
