# -*- coding: utf-8 -*-
"""Exercise scoped PAD+real Base CHECK/Q DXF exporter without a GUI bypass."""
from copy import deepcopy
from pathlib import Path
from ae_engine.receiving_nfb_pad_pair_manufacturing import (
    export_verified_pad_base_part_only,
)
from ae_engine.manufacturing_equivalence import ManufacturingParameters
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
    result=export_verified_pad_base_part_only(
        snap,installed,Path("WHD_PAD_BASE_CHECK_Q_PAIR_PART_ONLY"),
        version_id="source-traceable-v1",box_count=3,
        parameters=ManufacturingParameters("SPCC",2.,"LASER"),
    )
    print("PAD_BASE_CHECK_Q_PAIR_PART_ONLY_OK",result.evidence_sha256,
          result.pad_piece_count,result.base_piece_count,result.files,flush=True)


if __name__=="__main__":
    main()
