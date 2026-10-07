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
