from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/knowledge_governance.py"
CURRENT_API = ROOT / "docs/superpowers/CURRENT_API_INVENTORY_20260818.md"
MIRRORS = {
    ROOT / "07_Phase6尺寸語意與標準截角母規則.md": "個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md",
    ROOT / "標準基準檔格式.md": "加工層分類與定義.md",
}


def _load_governance():
    spec = importlib.util.spec_from_file_location("knowledge_governance_t6", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _governed_paths(governance) -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*.md"):
        rel = path.relative_to(ROOT).as_posix()
        if governance.is_governed_markdown(rel):
            paths.append(path)
    return sorted(paths)


def _metadata_debt(governance) -> list[str]:
    debt: list[str] = []
    for path in _governed_paths(governance):
        rel = path.relative_to(ROOT).as_posix()
        try:
            governance.parse_doc_metadata(path.read_text(encoding="utf-8"), path=rel)
        except Exception as exc:  # diagnostic list is the RED evidence
            debt.append(f"{rel}: {exc}")
    return debt


def _body_after_frontmatter(text: str) -> list[str]:
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    assert end != -1
    body = text[end + 5 :]
    return [line.strip() for line in body.splitlines() if line.strip()]


def test_all_governed_markdown_has_valid_whd_doc_meta_v1() -> None:
    governance = _load_governance()
    debt = _metadata_debt(governance)
    if debt:
        print(f"STRICT_METADATA_DEBT_COUNT={len(debt)}")
        for item in debt:
            print(f"STRICT_METADATA_DEBT: {item}")
    assert debt == []


def test_strict_validator_exists_and_fails_closed_on_any_missing_metadata(tmp_path: Path) -> None:
    governance = _load_governance()
    assert hasattr(governance, "validate_strict"), "T6 requires validate_strict full-tree enforcement"

    root = tmp_path
    (root / "README.md").write_text("# missing metadata\n", encoding="utf-8")
    errors = governance.validate_strict(root)
    assert errors
    assert any("README.md" in error and "WHD_DOC_META_V1" in error for error in errors)


def test_strict_cli_command_is_registered() -> None:
    governance = _load_governance()
    parser = governance.build_parser()
    args = parser.parse_args(["strict", "--root", str(ROOT)])
    assert args.command == "strict"


def test_current_named_api_snapshot_is_structurally_historical() -> None:
    governance = _load_governance()
    metadata = governance.parse_doc_metadata(CURRENT_API.read_text(encoding="utf-8"), path=CURRENT_API.relative_to(ROOT).as_posix())
    assert metadata.role == "HISTORICAL"
    assert metadata.contract == "api-inventory"
    prefix = CURRENT_API.read_text(encoding="utf-8")[:1600]
    assert "HISTORICAL" in prefix
    assert "不參與 current routing" in prefix
    assert "09_WHD_Canonical_Authority_Map.md" in prefix


def test_known_mirrors_use_structured_pointer_only_template() -> None:
    governance = _load_governance()
    for path, canonical in MIRRORS.items():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        metadata = governance.parse_doc_metadata(text, path=rel)
        assert metadata.role == "MIRROR", rel
        assert metadata.canonical == canonical, rel
        assert (ROOT / canonical).is_file(), rel
        body = _body_after_frontmatter(text)
        assert 3 <= len(body) <= 5, (rel, body)
        assert canonical in "\n".join(body), rel
        assert "不得新增或複製 normative 規則" in "\n".join(body), rel


def test_strict_validator_accepts_the_repository_after_migration() -> None:
    governance = _load_governance()
    assert hasattr(governance, "validate_strict")
    errors = governance.validate_strict(ROOT)
    if errors:
        for error in errors:
            print(f"STRICT_ERROR: {error}")
    assert errors == ()
