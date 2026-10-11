# -*- coding: utf-8 -*-
"""#1502: one existing base FinalScene, with EAR cuts retained and NFB added."""
import pytest

from ae_engine.manufacturing_render_data import (
    PartRenderData, UnfoldedBlankTopology, MaterialSegment,
    material_polygon_from_final_scene,
)
from ae_engine.receiving_nfb_base_process_projection import (
    NfbActualBaseWorkFace, NfbProjectedBaseProcess,
    compose_projected_nfb_on_actual_base,
)
from ae_engine.sheetmetal_drawing import DrawingScene, CirclePrimitive


def _base():
    scene=DrawingScene()
    scene.add_polyline(((0,0),(500,0),(500,500),(0,500)),
                       layer="CUTTING",closed=True)
    scene.add_circle((100,100),5,layer="CUTTING",source_type="EAR_MOUNT")
    part="receiving:upper:real_base"
    blank=UnfoldedBlankTopology(
        piece_id=part,
        x_segments=(MaterialSegment("X","face_w",500,"BASE"),),
        y_segments=(MaterialSegment("Y","face_h",500,"BASE"),),
        source="BASE",revision=1,
    )
    rendered=PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        unfolded_topology=blank,metadata={"stable_id":part},
    )
    return NfbActualBaseWorkFace(
        physical_part_id=part,actual_render=rendered,
        world_face_center_xy_mm=(0,250),
        unfolded_face_center_uv_mm=(250,250),
        face_outline_uv_mm=((0,0),(500,0),(500,500),(0,500)),
    )


def test_actual_ear_holes_preserved_when_projected_nfb_is_composed():
    base=_base()
    prior=tuple(base.actual_render.scene.primitives)
    cut=DrawingScene()
    cut.add_circle((250,250),2,layer="CUTTING",color=30,
                   source_type="NFB_LOWER_NATIVE_FIXING_CIRCLE",
                   source_id="nfb:A:FIX1")
    mark=DrawingScene()
    mark.add_line((260,260),(270,260),layer="MARKING",color=212)
    overlay=NfbProjectedBaseProcess(
        physical_part_id=base.physical_part_id,
        source_sha256="e"*64,source_model="indexed.dxf",
        owner_hole_ids=("nfb:A",),
        cutting=tuple(cut.primitives),
        marking=tuple(mark.primitives),
    )
    combined=compose_projected_nfb_on_actual_base(
        target=base,projection=overlay,
    )
    assert not combined.manufacturing_ready
    assert combined.render_data.metadata["nfb_base_mfg2_release_approved"] is False
    assert combined.render_data.unfolded_topology==base.actual_render.unfolded_topology
    assert combined.render_data.material.area < base.actual_render.material.area
    assert len(combined.render_data.scene.primitives)==len(prior)+2
    assert sum(isinstance(p,CirclePrimitive) and p.source_type=="EAR_MOUNT"
               for p in combined.render_data.scene.primitives)==1
    assert tuple(base.actual_render.scene.primitives)==prior
    with pytest.raises(ValueError,match="owner"):
        compose_projected_nfb_on_actual_base(
            target=base,
            projection=NfbProjectedBaseProcess(
                physical_part_id="other:base",source_sha256="e"*64,
                source_model="indexed.dxf",owner_hole_ids=("nfb:A",),
                cutting=tuple(cut.primitives),marking=(),
            ),
        )
