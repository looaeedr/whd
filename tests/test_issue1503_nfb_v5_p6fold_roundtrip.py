# -*- coding: utf-8 -*-
"""#1503 UAT RED: current CSV V5 NFB identity must survive REAL .p6fold v3.

Saving a submitted NFB Bay, independently copied Bay or quantity version
cannot require an obsolete .dxf name when the actual GUI selects nfbv5 refs.
"""
from copy import deepcopy
import json

import pytest

from ae_engine.receiving_layout import (
    new_receiving_layout, update_receiving_bay,
)
from ae_engine.receiving_nfb_persistence import normalize_nfb_config
from phase6_project_file import write_project, read_project, PROJECT_SCHEMA_V3
from phase6_quantity_model import QuantityModel

V5=("nfbv5:士林:2P400","nfbv5:士林:3P125SN")


def _config(*, two_tiers=False):
    n=2 if two_tiers else 1
    return {
        "layer_count":n,
        "holes":[{
            "physical_hole_id":f"nfb:upper:tier:{i}:unit:0",
            "model_filename":V5[i],
            "source_brand":"士林",
            "layer_index":i,
            "slot_index":0,
            "manual_x_state":"NONE",
            "manual_x_mm":None,
            "rotation_deg":0,
        } for i in range(n)],
    }


@pytest.mark.parametrize("two_tiers", (False,True))
def test_current_v5_submitted_single_bay_saves_and_reloads_with_exact_brand_and_holes(
    tmp_path, two_tiers,
):
    config=_config(two_tiers=two_tiers)
    layout=update_receiving_bay(
        new_receiving_layout(width=800,height=1600,depth=350),
        set_index=0,bay_index=0,nfb_config_submitted=True,nfb_config=config,
    )
    p=write_project(tmp_path/"receiving.p6fold",{
        "schema":"phase6-fold-project-v1",
        "snapshot":{"model":"受電箱","w":800,"h":1600,"d":350,"t":2,
                    "active_mode":"set_bay","receiving_layout":layout},
    })
    saved=json.loads(p.read_text(encoding="utf-8"))
    assert saved["schema"]==PROJECT_SCHEMA_V3
    restored=read_project(p)["snapshot"]
    bay=restored["receiving_layout"]["sets"][0]["bays"][0]
    assert bay["nfb_config_submitted"] is True
    assert bay["nfb_config"]["holes"]==normalize_nfb_config(config)["holes"]
    assert all(r["source_brand"]=="士林" for r in bay["nfb_config"]["holes"])
    assert all(r["model_filename"]==V5[i]
               for i,r in enumerate(bay["nfb_config"]["holes"]))
    assert not any("manufacturing_ready" in row for row in bay["nfb_config"]["holes"])


def test_current_v5_quantity_version_p6fold_roundtrip_preserves_source_owned_model(
    tmp_path,
):
    q=QuantityModel()
    q.set_version_nfb_config(q.selected_version_id,submitted=True,config=_config(two_tiers=True))
    f=write_project(tmp_path/"quantity.p6fold",{
        "schema":"phase6-fold-project-v1",
        "snapshot":{"model":"受電箱","active_mode":"quantity",
                    "receiving_quantity_box":{"w":800,"h":1600,"d":350},
                    "quantity":q.snapshot()},
    })
    assert read_project(f)["schema"]==PROJECT_SCHEMA_V3
    rows=read_project(f)["snapshot"]["quantity"]["versions"][0]["nfb_config"]["holes"]
    assert [x["model_filename"] for x in rows]==list(V5)


@pytest.mark.parametrize("invalid",(
    "nfbv5:不存在:2P400",
    "nfbv5:士林:",
    "nfbv5:士林:2P400/../../danger",
    "nfbv5:士林:2P400:fake",
    "random-unindexed-input",
))
def test_invalid_v5_reference_rejected_during_persistence(invalid):
    value=_config()
    value["holes"][0]["model_filename"]=invalid
    with pytest.raises(ValueError,match="valid V5 identity or legacy DXF"):
        normalize_nfb_config(value)


def test_mismatched_per_hole_brand_is_rejected_instead_of_cross_brand_fallback():
    value=_config()
    value["holes"][0]["source_brand"]="東元"
    with pytest.raises(ValueError,match="source_brand mismatch"):
        normalize_nfb_config(value)


def test_historical_dxf_identity_still_saves_without_migration():
    value=_config()
    value["holes"][0]["model_filename"]="400_140X257_107.dxf"
    value["holes"][0].pop("source_brand")
    accepted=normalize_nfb_config(value)
    assert accepted["holes"][0]["model_filename"]=="400_140X257_107.dxf"
