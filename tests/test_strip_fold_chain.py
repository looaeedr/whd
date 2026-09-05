from ae_engine.sheetmetal_geometry import FoldSegment, StripFoldChain, build_strip_outline, build_strip_bend_segments


def test_nine_segment_chain_produces_eight_bends_with_compensation():
    segs = tuple(FoldSegment(str(i), length, 1.0) for i, length in enumerate([10,20,30,40,50,60,70,80,90]))
    chain = StripFoldChain(segs, height=100)
    bends = build_strip_bend_segments(chain)
    assert [b.p1.x for b in bends] == [11,32,63,104,155,216,287,368]
    assert build_strip_outline(chain)[1].x == sum([10,20,30,40,50,60,70,80,90]) + 9


def test_asymmetric_eight_segment_chain_produces_seven_bends():
    segs = tuple(FoldSegment(str(i), length) for i, length in enumerate([15,20,25,146,396,146,20,15]))
    chain = StripFoldChain(segs, height=496)
    assert [b.p1.x for b in build_strip_bend_segments(chain)] == [15,35,60,206,602,748,768]
