"""#1901: Single quantity source proof must not require Set/Bay/version IDs."""
from hashlib import sha256
from types import SimpleNamespace

import pytest

from ae_engine.receiving_nfb_quantity_editor import (
    NfbVerifiedQuantityDoorProof, assert_quantity_nfb_proof_current,
    verify_quantity_nfb_inner_door_source,
)


def _source_setup(monkeypatch, tmp_path):
    import ae_engine.receiving_nfb_quantity_editor as q
    import ae_engine.receiving_nfb_ui1a as ui
    source = tmp_path / "400_140X257_107.dxf"
    source.write_bytes(b"actual-indexed-original-DXF-bytes")
    digest = sha256(source.read_bytes()).hexdigest()
    panel = SimpleNamespace(
        stable_id="inner_door:upper:panel", inner_door_id="upper",
        cell_key="door:0",
    )
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "w": 800, "h": 1600, "d": 350, "t": 2,
        "part_features": {panel.stable_id: []},
    }
    draft = {"status": "UNSUBMITTED_NFB_DRAFT_PREVIEW_ONLY",
             "set_brand": "士林", "layer_count": 1,
             "layers": [{"slots": [{
                 "unit_id": "unit-1", "filename": source.name,
                 "source_brand": "士林",
             }]}]}
    profile = SimpleNamespace(brand="士林", indexed_filename=source.name,
                              source_sha256=digest)
    monkeypatch.setattr(q.cabinet_family_policy, "derive_inner_door_panels",
                        lambda _snapshot: [panel])
    monkeypatch.setattr(q, "editable_nfb_draft", lambda value: value)
    monkeypatch.setattr(ui, "effective_nfb_slot_brand", lambda *_args: "士林")
    monkeypatch.setattr(q, "_active_slots", lambda state, *, profile: (
        (0, state["layers"][0]["slots"][0]),))
    monkeypatch.setattr(q, "read_nfb_runtime_source_profiles_csv",
                        lambda _path: (profile,))
    monkeypatch.setattr(q, "inspect_nfb_dxf_source",
                        lambda _path: SimpleNamespace(source_sha256=digest))
    monkeypatch.setattr(q, "configured_nfb_inner_door_render_data",
                        lambda snap, door, **kwargs: SimpleNamespace(
                            part_id=panel.stable_id, source_sha256=digest,
                            manufacturing_ready=True,
                            indexed_model_key=("士林", source.name),
                            physical_hole_ids=("unit-1",),
                        ))
    from ae_engine import receiving_nfb_editable_source as edit_source
    monkeypatch.setattr(edit_source, "resolve_editable_nfb_source_profile",
                        lambda _path, *, profile: profile)
    return q, snapshot, draft, source, panel


def test_quantity_uses_actual_single_door_without_forged_multi_version(monkeypatch, tmp_path):
    q, snap, draft, source, panel = _source_setup(monkeypatch, tmp_path)
    proof = verify_quantity_nfb_inner_door_source(
        draft, snapshot=snap, world_x_by_unit={"unit-1": 165.0},
        selected_source_path=source,
    )
    assert isinstance(proof, NfbVerifiedQuantityDoorProof)
    assert proof.part_id == panel.stable_id
    assert proof.world_x_by_unit == (("unit-1", 165.0),)
    assert not hasattr(proof, "set_index")
    assert not hasattr(proof, "bay_index")
    assert not hasattr(proof, "version_id")
    assert assert_quantity_nfb_proof_current(proof, snapshot=snap) is proof


def test_quantity_per_unit_override_uses_real_slot_brand_not_global(monkeypatch, tmp_path):
    q, snap, draft, source, panel = _source_setup(monkeypatch, tmp_path)
    draft["set_brand"] = "東元"  # actual unit override remains 士林
    proof = verify_quantity_nfb_inner_door_source(
        draft, snapshot=snap, world_x_by_unit={"unit-1": 165.0},
        selected_source_path=source,
    )
    assert proof.part_id == panel.stable_id


def test_quantity_proof_rejects_wrong_current_panel_or_changed_original_source(
    monkeypatch, tmp_path,
):
    q, snap, draft, source, panel = _source_setup(monkeypatch, tmp_path)
    proof = verify_quantity_nfb_inner_door_source(
        draft, snapshot=snap, world_x_by_unit={"unit-1": 0.0},
        selected_source_path=source,
    )
    modified = dict(snap, w=900)
    # Current panel identity/dimensions are derived from physical layout.
    monkeypatch.setattr(q.cabinet_family_policy, "derive_inner_door_panels",
                        lambda current: [
                            SimpleNamespace(**{
                                **vars(panel), "unfolded_width": current["w"],
                            })
                        ])
    with pytest.raises(ValueError, match="內門定位"):
        assert_quantity_nfb_proof_current(proof, snapshot=modified)
    source.write_bytes(b"tampered-DXF")
    with pytest.raises(ValueError, match="DXF 已變更"):
        assert_quantity_nfb_proof_current(proof, snapshot=snap)


def test_quantity_model_rotation_drift_invalidates_verified_opening(monkeypatch, tmp_path):
    q, snap, draft, source, _panel = _source_setup(monkeypatch, tmp_path)
    proof = verify_quantity_nfb_inner_door_source(
        draft, snapshot=snap, world_x_by_unit={"unit-1": 165.0},
        selected_source_path=source,
    )
    from copy import deepcopy
    altered = deepcopy(draft)
    altered["layers"][0]["slots"][0]["rotation_deg"] = 90
    with pytest.raises(ValueError, match="轉向"):
        assert_quantity_nfb_proof_current(proof, snapshot=snap, draft=altered)
    assert assert_quantity_nfb_proof_current(
        proof, snapshot=snap, draft=draft,
    ) is proof


def test_single_v5_preview_uses_real_quantity_panel_without_bay(monkeypatch, tmp_path):
    q, snap, draft, _source, panel = _source_setup(monkeypatch, tmp_path)
    import ae_engine.receiving_nfb_model_identity as identity
    import ae_engine.receiving_nfb_ui1a as ui
    import ae_engine.receiving_nfb_v5_configured_inner_door as v5

    draft["layers"][0]["slots"][0]["filename"] = "numeric:士林:400"
    monkeypatch.setattr(identity, "parse_numeric_model_ref",
                        lambda _ref: ("士林", "400"))
    monkeypatch.setattr(ui, "effective_nfb_slot_brand", lambda *_args: "士林")
    trial = SimpleNamespace(manufacturing_ready=False, status="PREVIEW_ONLY")
    observed = []
    def trial_on_real_part(snapshot, inner_door, *, holes):
        observed.append((snapshot, inner_door, tuple(holes)))
        return trial
    monkeypatch.setattr(v5, "trial_configured_nfb_v5_inner_door_render_data",
                        trial_on_real_part)
    result, entries, inner_door_id = q.preview_quantity_nfb_v5_on_actual_inner_door(
        draft, snapshot=snap, world_x_by_unit={"unit-1": 120.0},
    )
    assert result is trial
    assert inner_door_id == panel.inner_door_id
    assert entries[0].physical_hole_id == (
        "nfb:quantity:" + panel.stable_id + ":unit-1"
    )
    assert observed[0][0] is snap
    assert result.manufacturing_ready is False
    with pytest.raises(ValueError, match="世界 X"):
        q.preview_quantity_nfb_v5_on_actual_inner_door(
            draft, snapshot=snap, world_x_by_unit={},
        )


def test_quantity_invalid_world_x_does_not_stage_or_write(monkeypatch, tmp_path):
    q, snap, draft, source, _panel = _source_setup(monkeypatch, tmp_path)
    for coordinates in ({}, {"wrong-unit": 25.0}, {"unit-1": float("nan")}):
        with pytest.raises(ValueError, match="世界 X"):
            verify_quantity_nfb_inner_door_source(
                draft, snapshot=snap, world_x_by_unit=coordinates,
                selected_source_path=source,
            )
