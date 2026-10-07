from __future__ import annotations

import inspect

from ae_engine import box_body_structure
from ae_engine import box_body_structure_core
from ae_engine import box_body_piece_features


def test_issue1364_core_types_are_reexported():
    assert box_body_structure.ResolvedBoxBodyPiece is box_body_structure_core.ResolvedBoxBodyPiece
    assert box_body_structure.ResolvedBoxBodyStructure is box_body_structure_core.ResolvedBoxBodyStructure
    assert box_body_structure.BoxBodyStructureWarning is box_body_structure_core.BoxBodyStructureWarning


def test_issue1364_piece_feature_owner_is_one_way_and_facade_shrinks():
    assert box_body_structure.box_body_seam_positions is box_body_piece_features.box_body_seam_positions
    assert box_body_structure.apply_base_plate_structure_reliefs is box_body_piece_features.apply_base_plate_structure_reliefs
    assert box_body_structure.resolve_box_body_piece_face_features is box_body_piece_features.resolve_box_body_piece_face_features
    facade = inspect.getsource(box_body_structure)
    assert len(facade.splitlines()) < 600
    for owner in (inspect.getsource(box_body_structure_core), inspect.getsource(box_body_piece_features)):
        assert "from .box_body_structure import" not in owner
        assert "import ae_engine.box_body_structure" not in owner
