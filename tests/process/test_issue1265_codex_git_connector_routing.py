from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PITFALL = ROOT / "個人AI檔案庫/踩坑庫/git_connector_target_write_pitfall.md"


def _text() -> str:
    return PITFALL.read_text(encoding="utf-8")


def test_current_git_connector_guidance_is_workspace_first():
    text = _text()
    assert "WORKSPACE_DEFAULT" in text
    assert "HISTORICAL_SHARED_ZERO_RETIRED" in text or "shared-zero" in text
    assert "本 executor 的 repo workspace" in text
    assert "不得因本 reference 回退或等待 `/Google Drive/WHD/work/active`" in text


def test_current_guidance_does_not_restore_drive_only_authoring():
    text = _text()
    stale = (
        "在 `/Google Drive/WHD/work/active/...` 完成 mutation、tests、diff freeze",
        "RETURN_TO_ROOT_WORKSPACE",
        "canonical root mutation/tests/freeze 是否完成",
    )
    for token in stale:
        assert token not in text


def test_direct_production_contents_write_remains_forbidden():
    text = _text()
    assert "Contents API 永遠不得直接寫 authoritative production target" in text
    assert "`cleanup/2d-3d-sync`" in text
    assert "`main`" in text
    assert "Flow v2 trusted `MERGE / SYNC_TARGET`" in text
    assert "exact-tested-diff" in text or "exact tested diff" in text


def test_drive_mount_absence_is_not_workspace_default_blocker():
    text = _text()
    assert "Drive mount 缺失不得影響 `WORKSPACE_DEFAULT`" in text
