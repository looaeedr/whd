import pytest


def test_registry_resolves_vault_and_ro_aliases_to_canonical_registrations():
    from ae_engine.cabinet_types import resolve_cabinet_type

    vault = resolve_cabinet_type('金庫型')
    assert vault.canonical_name == '金庫型'
    assert vault.module_name.endswith('.vault')
    assert vault.implemented is True
    assert resolve_cabinet_type('VAULT') is vault

    ro = resolve_cabinet_type('RO')
    assert ro.canonical_name == 'RO'
    assert ro.module_name.endswith('.ro')
    assert ro.implemented is False
    assert resolve_cabinet_type('落地盤') is ro


def test_registry_normalizes_spacing_and_case_but_rejects_unknown_models():
    from ae_engine.cabinet_types import resolve_cabinet_type

    assert resolve_cabinet_type('  ro  ').canonical_name == 'RO'
    assert resolve_cabinet_type(' vault ').canonical_name == '金庫型'
    with pytest.raises(KeyError):
        resolve_cabinet_type('UNKNOWN')


def test_ae_engine_exports_cabinet_type_registry_without_changing_part_api():
    import ae_engine

    assert ae_engine.resolve_cabinet_type('RO').canonical_name == 'RO'
    assert callable(ae_engine.generate_part)
