from __future__ import annotations

from pathlib import Path

from tools.actions_visible_naming_guard import (
    main,
    validate_workflow_text,
)


GOOD = """\
name: WHD 動作繁中命名驗收
run-name: "WHD｜#538｜繁中命名驗收"

on:
  push:

jobs:
  contract:
    name: 繁中命名契約
    runs-on: ubuntu-latest
    steps:
      - name: 取出程式碼
        uses: actions/checkout@v4
      - name: 執行 pytest 驗收
        run: python -m pytest -q
"""


def test_accepts_explicit_traditional_chinese_visible_names():
    assert validate_workflow_text(GOOD, path="good.yml") == []


def test_rejects_missing_run_name_fallback_to_commit_message():
    text = GOOD.replace('run-name: "WHD｜#538｜繁中命名驗收"\n', "")
    errors = validate_workflow_text(text, path="missing.yml")
    assert any("缺少 top-level run-name" in item for item in errors)


def test_rejects_english_only_outer_job_and_step_names():
    text = GOOD.replace("name: WHD 動作繁中命名驗收", "name: WHD Actions Contract")
    text = text.replace("name: 繁中命名契約", "name: Contract")
    text = text.replace("name: 取出程式碼", "name: Checkout")
    errors = validate_workflow_text(text, path="english.yml")
    assert any("workflow name 必須包含繁體中文" in item for item in errors)
    assert any("job 'contract' name 必須包含繁體中文" in item for item in errors)
    assert any("step 1 name 必須包含繁體中文" in item for item in errors)


def test_rejects_step_without_explicit_visible_name():
    text = GOOD.replace(
        "      - name: 取出程式碼\n        uses: actions/checkout@v4\n",
        "      - uses: actions/checkout@v4\n",
    )
    errors = validate_workflow_text(text, path="step.yml")
    assert any("step 1 缺少 user-visible name" in item for item in errors)


def test_cli_fails_closed_and_reports_green(tmp_path: Path, capsys):
    good = tmp_path / "good.yml"
    good.write_text(GOOD, encoding="utf-8")
    assert main([str(good)]) == 0
    assert "ACTIONS_VISIBLE_NAMING_GREEN files=1" in capsys.readouterr().out

    bad = tmp_path / "bad.yml"
    bad.write_text(GOOD.replace('run-name: "WHD｜#538｜繁中命名驗收"\n', ""), encoding="utf-8")
    assert main([str(bad)]) == 1
    assert "ACTIONS_VISIBLE_NAMING_RED" in capsys.readouterr().out
