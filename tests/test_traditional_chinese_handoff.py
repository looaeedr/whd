# -*- coding: utf-8 -*-
from pathlib import Path

from ae_engine.sheetmetal_geometry import CORNER_TYPE_LABELS, EDITABLE_CORNER_TYPE_IDS

ROOT = Path(__file__).resolve().parents[1]


def test_corner_type_user_labels_are_traditional_chinese():
    labels = [CORNER_TYPE_LABELS[item] for item in EDITABLE_CORNER_TYPE_IDS]
    assert labels == ["十字截角", "貼外型", "嵌入型", "嵌入貼外型"]


def test_new_corner_ui_does_not_show_english_or_legacy_operation_names():
    sources = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("gui.py", "fold_designer_bridge.py")
    )
    forbidden_visible_literals = (
        'text="CornerType',
        "text='CornerType",
        'text="Cross',
        "text='Cross",
        'text="Overlay',
        "text='Overlay",
        'text="Insert',
        "text='Insert",
        'values=("C01"',
        "values=('C01'",
    )
    for literal in forbidden_visible_literals:
        assert literal not in sources
    assert "未知類型" not in sources
    assert "自訂" in sources


def test_superpowers_and_delivery_headings_are_traditional_chinese():
    paths = [
        ROOT / "docs/superpowers/README.md",
        ROOT / "docs/superpowers/specs/2026-08-21-corner-type-semantic-assembly-design.md",
        ROOT / "docs/superpowers/plans/2026-08-21-corner-type-semantic-assembly-implementation.md",
        ROOT / "docs/superpowers/verification/2026-08-21-corner-type-semantic-assembly-verification.md",
        ROOT / "修改日誌/20260821.md",
    ]
    forbidden_headings = (
        "# CornerType ",
        "# Superpowers Handoff",
        "## Goal",
        "## Scope",
        "## Engine",
        "## Box Body",
        "## Contracts/API",
        "## GUI / FoldDesigner",
        "### Task ",
        "## Legacy compatibility",
        "## Public contract / API",
        "## GUI state and persistence",
        "## Non-goals",
        "## Success criteria",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for heading in forbidden_headings:
            assert heading not in text, f"{path}: still contains English heading {heading!r}"


def test_handoff_explicitly_documents_traditional_chinese_ui_rule():
    text = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    assert "使用者可見介面一律使用繁體中文" in text
    assert "程式內部識別字" in text


def test_superpowers_does_not_reintroduce_wrong_endcap_secondary_formula():
    paths = [
        ROOT / "docs/superpowers/README.md",
        ROOT / "docs/superpowers/specs/2026-08-21-corner-type-semantic-assembly-design.md",
        ROOT / "docs/superpowers/plans/2026-08-21-corner-type-semantic-assembly-implementation.md",
        ROOT / "docs/superpowers/verification/2026-08-21-corner-type-semantic-assembly-verification.md",
        ROOT / "修改日誌/20260821.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "側折 + FW - 嵌入留肉量" not in combined
    assert "側折 + FW - 0.5T" not in combined
    assert "第二級位置為 `39mm`" not in combined
    assert "TOP_SECONDARY_LEFT 39.0" not in combined
    assert "正確二級 CUTTING = 側折 + 嵌入留肉量" in combined
    assert "文字大小：小 / 中 / 大" in combined
