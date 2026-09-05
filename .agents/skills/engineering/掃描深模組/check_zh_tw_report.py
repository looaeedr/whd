#!/usr/bin/env python3
"""驗證掃描深模組 Skill、HTML 模板與最終報告的繁體中文交付規則。"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ALLOWED_LANGS = {"zh-tw", "zh-hant-tw"}
FORBIDDEN_LABELS = (
    "Before",
    "After",
    "Problem",
    "Solution",
    "Benefits",
    "Wins",
    "Files",
    "Strong",
    "Worth exploring",
    "Speculative",
    "Top recommendation",
)
CHECKED_ATTRIBUTES = {"aria-label", "title", "alt"}
IGNORED_TEXT_TAGS = {"script", "style", "code"}

LEGACY_SOURCE_PATTERNS = (
    "# HTML Report Format",
    "## Scaffold",
    "## Header",
    "## Candidate card",
    "## Diagram patterns",
    "## Style guidance",
    "## Top recommendation section",
    "## Tone",
    "Plain English",
    "plain English",
    "Before / After",
    "Worth exploring",
    "Top recommendation",
)

REQUIRED_SKILL_MARKERS = (
    "## 語言規則（最高優先，強制）",
    "## 啟動前語言自檢（強制）",
    "check_zh_tw_report.py --skill-sources",
    "輸出前語言閘門（強制）",
)

REQUIRED_TEMPLATE_MARKERS = (
    "# HTML 報告格式（繁體中文）",
    '<html lang="zh-Hant-TW">',
    "## 基本骨架",
    "## 頁首",
    "## 候選項目卡片",
    "## 圖表模式",
    "## 視覺風格",
    "## 最高優先建議",
    "## 繁體中文交付檢查（強制）",
)


def _contains_forbidden(text: str) -> list[str]:
    hits: list[str] = []
    for label in FORBIDDEN_LABELS:
        if re.search(rf"(?<![A-Za-z]){re.escape(label)}(?![A-Za-z])", text, re.IGNORECASE):
            hits.append(label)
    return hits


def validate_skill_sources(skill_text: str, template_text: str) -> list[str]:
    """檢查 Skill 與 HTML 模板是否以繁體中文為預設來源。"""
    errors: list[str] = []

    for marker in REQUIRED_SKILL_MARKERS:
        if marker not in skill_text:
            errors.append(f"SKILL.md 缺少必要繁中規則：{marker}")

    for marker in REQUIRED_TEMPLATE_MARKERS:
        if marker not in template_text:
            errors.append(f"HTML-REPORT.md 缺少必要繁中模板標記：{marker}")

    combined = f"{skill_text}\n{template_text}"
    for pattern in LEGACY_SOURCE_PATTERNS:
        if pattern in combined:
            errors.append(f"Skill／模板仍含舊版英文模板文字：{pattern}")

    if '<html lang="en">' in template_text.lower():
        errors.append('HTML-REPORT.md 不得使用 <html lang="en">')

    return errors


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang: str | None = None
        self.tag_stack: list[str] = []
        self.visible_chunks: list[str] = []
        self.attribute_chunks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self.tag_stack.append(tag)
        attrs_dict = {k.lower(): v for k, v in attrs if v is not None}
        if tag == "html":
            self.html_lang = attrs_dict.get("lang")
        for name in CHECKED_ATTRIBUTES:
            value = attrs_dict.get(name)
            if value:
                self.attribute_chunks.append((name, value))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): v for k, v in attrs if v is not None}
        for name in CHECKED_ATTRIBUTES:
            value = attrs_dict.get(name)
            if value:
                self.attribute_chunks.append((name, value))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
            return
        for index in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[index] == tag:
                del self.tag_stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if any(tag in IGNORED_TEXT_TAGS for tag in self.tag_stack):
            return
        if data.strip():
            self.visible_chunks.append(data)


def validate_html(html: str) -> list[str]:
    parser = _VisibleTextParser()
    parser.feed(html)
    errors: list[str] = []

    lang = (parser.html_lang or "").strip().lower()
    if lang not in ALLOWED_LANGS:
        errors.append(
            f'HTML lang 必須是 "zh-TW" 或 "zh-Hant-TW"，目前為 {parser.html_lang!r}'
        )

    visible_text = "\n".join(parser.visible_chunks)
    for label in _contains_forbidden(visible_text):
        errors.append(f"使用者可見文字仍含英文標籤：{label}")

    for attr_name, attr_value in parser.attribute_chunks:
        for label in _contains_forbidden(attr_value):
            errors.append(f"{attr_name} 仍含英文標籤：{label}")

    return errors


def _check_sources(skill_dir: Path) -> int:
    skill_path = skill_dir / "SKILL.md"
    template_path = skill_dir / "HTML-REPORT.md"
    skill_text = skill_path.read_text(encoding="utf-8")
    template_text = template_path.read_text(encoding="utf-8")
    errors = validate_skill_sources(skill_text, template_text)
    if errors:
        print("繁體中文 Skill／模板來源檢查：失敗", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("繁體中文 Skill／模板來源檢查：通過")
    return 0


def _check_report(report: Path) -> int:
    html = report.read_text(encoding="utf-8")
    errors = validate_html(html)
    if errors:
        print("繁體中文報告交付檢查：失敗", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("繁體中文報告交付檢查：通過")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="檢查掃描深模組是否符合繁體中文規則")
    ap.add_argument("report", nargs="?", type=Path, help="要檢查的 HTML 報告")
    ap.add_argument(
        "--skill-sources",
        action="store_true",
        help="檢查目前 Skill 與 HTML 模板來源是否已繁體中文化",
    )
    args = ap.parse_args(argv)

    if args.skill_sources:
        return _check_sources(Path(__file__).resolve().parent)
    if args.report is not None:
        return _check_report(args.report)

    ap.error("請提供 HTML 報告路徑，或使用 --skill-sources")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
