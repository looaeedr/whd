"""R7–R9 incremental source guards; no changes to manufacturing geometry truth.

RED baseline: GitHub localX@6b8039eae1b00a0cb8574678c4e283a9d01acf17.
These tests drive actual receiving, custom-part and mode ingress APIs.
"""
from __future__ import annotations

import pytest

from ae_engine.receiving_quantity_box import positive_dimension
from phase6_custom_parts import CustomPartCatalog
from phase6_receiving_modes import ReceivingModeSession, fresh_receiving_mode


def test_r7_extreme_receiving_dimensions_fail_as_invalid_operator_input():
    # Python integer input (e.g. a corrupt project/bridge payload) can be
    # larger than an IEEE-754 float. It must not escape as OverflowError.
    too_large = 10 ** 1000
    with pytest.raises(ValueError, match="W.*有限正數"):
        positive_dimension(too_large, "w")
    with pytest.raises(ValueError, match="W.*有限正數"):
        fresh_receiving_mode(
            "set_bay",
            {"w": too_large, "h": 1600, "d": 350},
        )


def test_r8_extreme_custom_part_transverse_length_fails_closed():
    too_large = 10 ** 1000
    catalog = CustomPartCatalog()
    with pytest.raises(ValueError, match="另一軸尺寸必須是有限正數"):
        catalog.add(
            display_name="超大尺寸測試板",
            fold_axis="X",
            transverse_length=too_large,
        )
    assert catalog.snapshot() == {"next_id": 1, "items": {}}
    with pytest.raises(ValueError, match="另一軸尺寸必須是有限正數"):
        CustomPartCatalog({
            "next_id": 2,
            "items": {
                "custom:1": {
                    "display_name": "舊案測試板",
                    "fold_axis": "Y",
                    "transverse_length": too_large,
                },
            },
        })


@pytest.mark.parametrize("invalid_mode", [[], ["set_bay"], {}, {"active_mode": "quantity"}])
def test_r9_unhashable_mode_is_rejected_with_stable_contract(invalid_mode):
    with pytest.raises(ValueError, match="不合法的受電箱操作模式"):
        ReceivingModeSession._check_mode(invalid_mode)
    with pytest.raises(ValueError, match="不合法的受電箱操作模式"):
        fresh_receiving_mode(
            invalid_mode,
            {"w": 800, "h": 1600, "d": 350},
        )
