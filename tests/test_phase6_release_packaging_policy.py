from __future__ import annotations

import json
from pathlib import Path
import zipfile
import pytest

from tools.phase6_release import collect_full_paths, collect_update_paths, load_release_policy, validate_update_baseline_archive, verify_zip_against_source


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_policy_uses_runtime_baseline_and_never_hardcodes_archive_name():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root / "release_required_artifacts.json").read_text(encoding="utf-8"))
    policy = load_release_policy(root)
    assert policy.update_baseline_mode == "explicit_runtime_archive"
    assert "canonical_update_baseline_archive" not in raw
    assert "個人AI檔案庫" in policy.mandatory_update_trees
    assert "config.ini" in policy.forbidden_update_files
    assert ".agents/skills/engineering/phase6-release-packaging/SKILL.md" in policy.mandatory_update_files


def test_runtime_baseline_validation_accepts_different_full_archive_names(tmp_path):
    root = Path(__file__).resolve().parents[1]
    policy = load_release_policy(root)
    for name in (
        "PHASE6_A_FULL_20260904_010203.zip",
        "PHASE6_B_FULL_20261005_040506.zip",
    ):
        archive = tmp_path / name
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("config.ini", "unchanged")
            zf.writestr("gui.py", "print('ok')")
        validate_update_baseline_archive(policy, archive)



def test_release_policy_declares_full_and_update_package_root_exclusions():
    root = Path(__file__).resolve().parents[1]
    policy = load_release_policy(root)
    assert policy.excluded_package_roots == (".git", ".scratch")


def test_full_and_update_collectors_exclude_git_and_scratch_roots(tmp_path):
    source = tmp_path / "source"
    baseline = tmp_path / "baseline"
    source.mkdir(); baseline.mkdir()
    _write(source, ".git/config", "repo metadata")
    _write(source, ".git/index", "repo index")
    _write(source, ".scratch/release.jsonl", "journal")
    _write(source, "normal.py", "new")
    _write(baseline, "normal.py", "old")

    excluded = (".git", ".scratch")
    full_paths = collect_full_paths(source, excluded_package_roots=excluded)
    update_paths = collect_update_paths(
        source,
        baseline,
        mandatory_update_files=(),
        mandatory_update_trees=(),
        forbidden_update_files=("config.ini",),
        excluded_package_roots=excluded,
    )

    assert "normal.py" in full_paths
    assert "normal.py" in update_paths
    assert not any(rel.startswith(".git/") for rel in full_paths | update_paths)
    assert not any(rel.startswith(".scratch/") for rel in full_paths | update_paths)


def test_zip_verifier_rejects_forbidden_package_roots_even_if_expected_set_is_wrong(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _write(source, ".git/config", "repo metadata")
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(source / ".git/config", arcname=".git/config")

    with pytest.raises(ValueError, match="excluded package root"):
        verify_zip_against_source(
            source,
            archive,
            expected_paths=(".git/config",),
            excluded_package_roots=(".git", ".scratch"),
        )

def test_unchanged_personal_ai_tree_is_always_in_update(tmp_path):
    source = tmp_path / "source"
    baseline = tmp_path / "baseline"
    source.mkdir(); baseline.mkdir()
    rel = "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md"
    _write(source, rel, "same")
    _write(baseline, rel, "same")
    paths = collect_update_paths(
        source,
        baseline,
        mandatory_update_files=(),
        mandatory_update_trees=("個人AI檔案庫",),
        forbidden_update_files=("config.ini",),
    )
    assert rel in paths


def test_update_never_contains_config_even_when_source_differs(tmp_path):
    source = tmp_path / "source"
    baseline = tmp_path / "baseline"
    source.mkdir(); baseline.mkdir()
    _write(source, "config.ini", "current")
    _write(baseline, "config.ini", "old")
    _write(source, "changed.py", "new")
    _write(baseline, "changed.py", "old")
    paths = collect_update_paths(
        source,
        baseline,
        mandatory_update_files=(),
        mandatory_update_trees=(),
        forbidden_update_files=("config.ini",),
    )
    assert "changed.py" in paths
    assert "config.ini" not in paths


def test_packaging_skill_contains_non_negotiable_release_contract():
    root = Path(__file__).resolve().parents[1]
    skill = root / ".agents/skills/engineering/phase6-release-packaging/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    for required in (
        "explicit_runtime_archive",
        "runtime",
        "個人AI檔案庫/**",
        "config.ini",
        "Asia/Taipei",
        "FULL",
        "UPDATE",
        "SHA256",
        "解壓",
        "禁止交付",
    ):
        assert required in text
    import re
    assert not re.search(r"PHASE6_[A-Z0-9_]+_FULL_\d{8}_\d{6}\.zip", text), "release skill must not hardcode a timestamped FULL baseline"


def test_release_path_normalization_preserves_leading_dotfiles():
    from tools.phase6_release import _normalized
    assert _normalized(".gitignore") == ".gitignore"
    assert _normalized("./folder/file.txt") == "folder/file.txt"


def test_release_policy_has_no_stale_cleanup_paths():
    root = Path(__file__).resolve().parents[1]
    policy = load_release_policy(root)
    assert policy.update_cleanup_paths == ()
    assert "tools/apply_phase6_update_cleanup.py" in policy.mandatory_update_files
    assert "APPLY_PHASE6_UPDATE_CLEANUP.bat" in policy.mandatory_update_files


def test_update_cleanup_removes_only_declared_project_relative_paths(tmp_path):
    from tools.apply_phase6_update_cleanup import apply_cleanup_paths

    root = tmp_path / "project"
    (root / "skills/engineering").mkdir(parents=True)
    (root / "skills/engineering/SKILL.md").write_text("old", encoding="utf-8")
    (root / "keep.txt").write_text("keep", encoding="utf-8")

    removed = apply_cleanup_paths(root, ("skills",))
    assert removed == ("skills",)
    assert not (root / "skills").exists()
    assert (root / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_update_cleanup_rejects_parent_traversal(tmp_path):
    from tools.apply_phase6_update_cleanup import apply_cleanup_paths

    root = tmp_path / "project"
    root.mkdir()
    with pytest.raises(ValueError, match="unsafe cleanup path"):
        apply_cleanup_paths(root, ("../outside",))


def test_permanent_suite_does_not_depend_on_retired_user_p6fold_paths():
    root = Path(__file__).resolve().parents[1]
    retired_paths = tuple(
        "/mnt/data/" + name
        for name in ("自訂.p6fold", "自訂(2).p6fold", "自訂(6).p6fold")
    )
    offenders = []
    for path in (root / "tests").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for retired in retired_paths:
            if retired in text:
                offenders.append(f"{path.relative_to(root).as_posix()}: {retired}")
    assert not offenders, "retired external user fixtures remain in permanent suite:\n" + "\n".join(offenders)


def test_packaging_skill_rejects_retired_ephemeral_user_fixture_dependencies():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".agents/skills/engineering/phase6-release-packaging/SKILL.md").read_text(encoding="utf-8")
    assert "永久 suite" in text
    assert "/mnt/data/自訂" in text
    assert "conditional skip" in text
