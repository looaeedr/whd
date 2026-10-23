# -*- coding: utf-8 -*-
"""CI-only true WHD FinalScene PAD 3D render from a submitted V5 Bay fixture.

An independent visual receipt of real engine drawing, NOT a Windows screenshot
or an authorization to manufacture PAD. No handwritten geometry/render overlay.
"""
from __future__ import annotations

from argparse import ArgumentParser
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from matplotlib.figure import Figure

from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_pad_assembly_preview import (
    build_committed_pad_assembly_display,
)
from phase6_final_scene_contracts import (
    AssemblySceneRenderData, FinalSceneViewRequest,
)
from phase6_final_scene_renderer import Phase6FinalSceneView


def create_pad_3d_ci_receipt(path: str | Path) -> str:
    # Existing, test-proven submitted physical Bay fixture. Models and
    # dimensions are sample DATA, not generator logic.
    from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
    from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make

    snap = _current()
    snap["receiving_base_plate"] = {
        "pattern": "LEFT_FLAT_SIDE",
        "height": 340., "shrink_top": 20., "shrink_bottom": 20.,
        "shrink_left": 45., "shrink_right": 45., "bend": 20.,
    }
    rows = snap["nfb_config"]["holes"]
    rows[0].update(model_filename="nfbv5:士林:3P400SN", source_brand="士林")
    rows[1].update(model_filename="nfbv5:士林:100HN-s", source_brand="士林")
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    physical = apply_committed_csv_v5_to_canonical_parts(
        snap, (_make(snap),)
    )
    skins = build_committed_pad_assembly_display(snap, physical)
    if (len(skins) != 1 or skins[0].rise_mm != 39.
            or skins[0].manufacturing_ready
            or skins[0].assembly_contact_certified):
        raise ValueError("PAD_CI_VISUAL_UNVERIFIED_SOURCE")
    payload = AssemblySceneRenderData(
        assembly_parts=physical,
        visible_part_keys=("base_plate",),
        formed_nfb_pad_skins=skins,
        warnings=(
            "CI 模擬組裝：WHD 真實渲染器；非 Windows GUI、非製造核准",
        ),
    )
    fig = Figure(figsize=(9, 6), dpi=160)
    ax = fig.add_subplot(111, projection="3d")
    view = Phase6FinalSceneView(type("_Renderer", (), {"ax3d": ax})())
    view.render(FinalSceneViewRequest(
        render_data=payload, x_profile=(), y_profile=(),
        part_key="assembly", finished_dimensions=(800., 1600., 350.),
        thickness=2.,
    ))
    if view.last_formed_pad_display_ids != (skins[0].part_id,):
        raise ValueError("PAD_CI_RENDERER_DID_NOT_DRAW_REAL_SKIN")
    ax.view_init(elev=22., azim=-62.)
    output=Path(path)
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output, dpi=160)
    digest=sha256(output.read_bytes()).hexdigest()
    print("WHD_PAD_CI_ACTUAL_ENGINE_VISUAL_RECEIPT",output.name,
          skins[0].part_id, "rise=39mm", "sha256="+digest)
    return digest


def main() -> None:
    parser=ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    create_pad_3d_ci_receipt(args.output)


if __name__=="__main__":
    main()
