# -*- coding: utf-8 -*-
"""#2517: source-verified Receiving NFB Bay transactions use one public Engine."""
import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_nfb_ui1b_bridge import (
    NfbVerifiedDraftSubmission as OriginalBundle,
    assert_live_verified_nfb as original_assert,
    submit_live_verified_nfb as original_submit,
    copy_live_verified_nfb as original_copy,
)
from gui_modules.application import fold_designer_composition_receiving as gui


@pytest.mark.parametrize("name,owner", [
    ("NfbVerifiedDraftSubmission", OriginalBundle),
    ("assert_live_verified_nfb", original_assert),
    ("submit_live_verified_nfb", original_submit),
    ("copy_live_verified_nfb", original_copy),
])
def test_public_facades_reexport_exact_original_source_verified_owner(name, owner):
    assert getattr(api, name) is owner
    assert getattr(ae_engine, name) is owner
    assert name in ae_engine.__all__


def test_original_gui_stages_and_commits_by_public_engine_only():
    source = inspect.getsource(gui)
    assert "from ae_engine.receiving_nfb_ui1b_bridge import" not in source
    assert source.count("manufacturing_api.NfbVerifiedDraftSubmission") == 1
    assert source.count("manufacturing_api.assert_live_verified_nfb(") == 2
    assert source.count("manufacturing_api.submit_live_verified_nfb(") == 1
    assert source.count("manufacturing_api.copy_live_verified_nfb(") == 1
    assert "pending_verified_nfb[(bundle.set_index,bundle.bay_index)]=bundle" in source
    assert "verified_target_indices=tuple(verified_targets)" in source


def test_public_source_proof_guard_rejects_unknown_and_unverified_object():
    with pytest.raises(TypeError, match="source-verified"):
        api.assert_live_verified_nfb(object(), object(), current_snapshot={})
    with pytest.raises(TypeError, match="source-verified"):
        api.submit_live_verified_nfb(
            object(), object(), current_snapshot={}, confirm=lambda: True,
        )
    with pytest.raises(TypeError, match="source-verified"):
        api.copy_live_verified_nfb(
            object(), source_bay_index=0, target_bundle=object(),
            current_snapshot={}, confirm=lambda: True,
        )
