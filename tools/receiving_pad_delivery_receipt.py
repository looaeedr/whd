# -*- coding: utf-8 -*-
"""CI witness only: real WHD PAD/Base trial DXF & verified physical BOM."""
from copy import deepcopy
from pathlib import Path

from ae_engine.receiving_nfb_pad_delivery import export_pad_trial_bundle
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make


def main():
    snap=_current()
    snap["nfb_config"]["holes"][0].update(
        model_filename="nfbv5:士林:3P400SN",source_brand="士林")
    snap["nfb_config"]["holes"][1].update(
        model_filename="nfbv5:士林:100HN-s",source_brand="士林")
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    installed=apply_committed_csv_v5_to_canonical_parts(snap,(_make(snap),))
    out=Path("WHD_PAD_BASE_SOURCE_VERIFIED_TRIAL_NOT_MFG")
    receipt=export_pad_trial_bundle(snap,installed,out,piece_count=3)
    print("WHD_PAD_REAL_BOM_AND_TRIAL_DXF_ROUNDTRIP",out,
          receipt["parts"][0]["id"],receipt["parts"][0]["quantity"],
          len(receipt["dxf"]),flush=True)


if __name__=="__main__":
    main()
