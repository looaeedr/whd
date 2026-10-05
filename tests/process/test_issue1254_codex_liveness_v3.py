from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_deterministic_migration_is_workspace_first():
    text = _read(".agents/skills/engineering/deterministic-repo-migration/SKILL.md")
    assert "WORKSPACE_DEFAULT" in text
    assert "SHARED_ZERO_FALLBACK" in text
    assert "workspace-capable executor" in text
    assert "HANDOFF_TO_ROOT_WORKSPACE_IMPLEMENTATION" not in text
    assert "delivery phase 只可由 `/推推 文檔|主體`" not in text
    assert "Current repository-content mutation order is fixed to:" not in text


def test_repository_delete_is_workspace_first():
    text = _read(".agents/skills/engineering/刪除/SKILL.md")
    section = text.split("## 4. Repository tracked path 的刪除", 1)[1].split(
        "## 5. ACTIVE_ZERO_PHYSICAL_CLEANUP_HARD_GATE_V1", 1
    )[0]
    assert "WORKSPACE_DEFAULT" in section
    assert "WORKSPACE_DELIVERY" in section
    assert "SHARED_ZERO_FALLBACK" in section
    assert "先在 canonical `/Google Drive/WHD` root 確認 path" not in section
    assert "只有使用者下 `/推推 文檔|主體` 才開 GitHub delivery" not in section


def test_scheduler_current_sections_do_not_mandate_drive_shared_zero():
    text = _read("個人AI檔案庫/踩坑庫/scheduler_prompt_authoring_pitfall.md")
    assert "executor-local WORKSPACE_DEFAULT authoring/tests" in text
    assert "workspace-capable executor" in text
    assert "SHARED_ZERO_FALLBACK" in text
    assert "固定 HANDOFF 到 canonical `/Google Drive/WHD`" not in text
    assert "repository-content authority 是 selected shared `0` lineage" not in text
    assert "HANDOFF 到 canonical Google Drive root workspace" not in text


def test_prevention_library_current_guidance_is_workspace_first():
    text = _read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    assert "ordinary repository-content authoring 的 CURRENT authority" in text
    assert "WORKSPACE_DEFAULT" in text
    assert "SHARED_ZERO_FALLBACK" in text
    assert "repository-content authority 固定是 canonical `/Google Drive/WHD`" not in text
    assert "真正需要 repository content 的工作仍走 shared-0" not in text


def test_shared_zero_remains_fallback_not_removed_history():
    deterministic = _read(
        ".agents/skills/engineering/deterministic-repo-migration/SKILL.md"
    )
    deletion = _read(".agents/skills/engineering/刪除/SKILL.md")
    assert "fresh touched-path evidence" in deterministic
    assert "fresh touched-path evidence" in deletion
    assert ".unpushed/{docs|body}/0" in deterministic
    assert ".unpushed/{docs|body}/0" in deletion
