"""Build Traditional Chinese WHD release notes from an exact published source diff.

The Windows packaging workflow supplies the verified current/previous release
identities. This script does not create tags, grant /推推 authority, or publish.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import re
import subprocess

SHA = re.compile(r"^[0-9a-f]{40}$")
TYPES = (
    ("新增與改善", ("feat", "feature", "add", "enhance", "improve")),
    ("錯誤修正", ("fix", "bug", "repair", "hotfix")),
    ("測試與驗證", ("test", "qa", "audit")),
    ("文件與發版", ("docs", "build", "ci", "chore", "release")),
)


def _category(title: str) -> str:
    lead = title.lower().strip()
    for label, prefixes in TYPES:
        if any(re.match(rf"^{re.escape(prefix)}(?:$|[ (:!])", lead) for prefix in prefixes):
            return label
    return "其他程式變更"


def build_notes(
    *, tag: str, sha: str, previous_tag: str, previous_sha: str,
    titles: list[str],
) -> str:
    if not tag.startswith("v") or not previous_tag.startswith("v"):
        raise ValueError("RELEASE_NOTES_INVALID_TAG")
    if not SHA.fullmatch(sha) or not SHA.fullmatch(previous_sha) or sha == previous_sha:
        raise ValueError("RELEASE_NOTES_INVALID_EXACT_SHA")
    grouped: dict[str, list[str]] = defaultdict(list)
    for title in titles:
        title = " ".join(title.strip().split())
        if title and not title.startswith("Merge pull request"):
            grouped[_category(title)].append(title)
    if not grouped:
        raise ValueError("RELEASE_NOTES_EMPTY_SOURCE_DIFF")
    lines = [
        "# WHD 正式版更新說明（繁體中文）", "",
        f"**本次版本：** `{tag}`  ",
        f"**正式 X 程式來源：** `{sha}`  ",
        f"**上一個正式版本：** `{previous_tag}`（`{previous_sha}`）",
        "",
        "## 本次主要更新",
        "此版本相對上一個正式版，累積下列已合併的功能、修正及驗證。"
        "分類與數量由實際版本差異產生；原始提交標題保留供查核，"
        "不將其冒充完整人工翻譯或全部使用情境的驗收。",
        "",
    ]
    for group in ("新增與改善", "錯誤修正", "測試與驗證", "文件與發版", "其他程式變更"):
        items = grouped.get(group, [])
        if items:
            lines.append(f"- **{group}：{len(items)} 項。**")
    lines.extend(["", "## 逐項變更（保留原始提交標題）", ""])
    for group in ("新增與改善", "錯誤修正", "測試與驗證", "文件與發版", "其他程式變更"):
        items = grouped.get(group, [])
        if not items:
            continue
        lines.extend([f"### {group}", ""])
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    lines.extend([
        "## Windows 下載與啟動", "",
        f"- 下載 `WHD_Windows_x64_{tag}.zip` 與 `SHA256.txt`；先核對 SHA-256。",
        "- 解壓縮整個 ZIP，再執行 `WHD/WHD.exe`，勿只複製 EXE。",
        "- 保留 `config.ini`、`config/`、`基準檔/` 與其他隨附檔案。",
        "- 先備份自訂 DXF、CSV、`.p6fold` 與設定，勿直接覆蓋舊版資料夾。",
        "- GitHub 自動提供的 Source code (zip) 是原始碼，**不是可執行版**。",
        "",
        "## 安全與驗收界線", "",
        "- 本包由 GitHub Windows x64 Runner 建置並做啟動 Smoke；"
        "此項不等於每一種現場板型及機台的製造驗收。",
        "- CADCraft 為選用的外部繪圖程式，不承諾把第三方 EXE 包入 WHD。",
        "- 程式未簽署 Windows 程式碼簽章，請以官方 Release 與 SHA-256 驗證來源。",
        "",
    ])
    return "\n".join(lines)


def build_guide(*, tag: str, sha: str) -> str:
    if not tag.startswith("v") or not SHA.fullmatch(sha):
        raise ValueError("RELEASE_GUIDE_INVALID_IDENTITY")
    return "\n".join([
        "# WHD Windows 64 位元可攜版使用說明（繁體中文）", "",
        f"**版本：** `{tag}`  ",
        f"**精確產品來源：** `{sha}`", "",
        "## 如何下載", "",
        f"1. 開啟 GitHub 正式版本頁："
        f"https://github.com/looaeedr/whd/releases/tag/{tag}",
        f"2. 在 Assets 下載 `WHD_Windows_x64_{tag}.zip`、`SHA256.txt`。",
        "3. GitHub 預設提供的 Source code (zip) 只有程式原始碼，不含可執行 EXE。", "",
        "## 安裝與操作", "",
        "1. 將 ZIP **完整解壓到新的資料夾**，不要在壓縮檔內直接執行。",
        "2. 開啟 `WHD` 資料夾，執行 `WHD.exe`；不需要另裝 Python。",
        "3. 保留同資料夾中的 `config.ini`、`config/`、`基準檔/` 與其他相依檔案。",
        "4. 用既有 `.p6fold` 測試開啟、保存、2D／3D 及 DXF，現場核對後再製造。", "",
        "## 保護資料與排除問題", "",
        "- 先備份原有 `config.ini`、DXF、CSV、`.p6fold` 及舊版程式；不要用新包直接覆蓋。",
        "- 無法啟動時，確認使用 Windows x64 且整個 ZIP 已解壓。",
        "- 本版沒有程式碼簽章。請確認官方來源並以 `SHA256.txt` 驗證下載內容。",
        "- 此 Windows 執行版 Smoke 不取代現場每一種實際板型的製造驗收。",
        "- 版本改動請閱讀同資料夾的 `本次更新.md`。",
        "",
    ])


def git_titles(root: Path, previous_sha: str, sha: str) -> list[str]:
    def run(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True, encoding="utf-8"
        ).strip()
    if run("rev-parse", "HEAD") != sha:
        raise ValueError("RELEASE_NOTES_WRONG_SOURCE_CHECKOUT")
    subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", previous_sha, sha],
        check=True,
    )
    return run("log", "--no-merges", "--format=%s", f"{previous_sha}..{sha}").splitlines()


def main() -> None:
    parser = argparse.ArgumentParser()
    for key in ("tag", "sha", "previous-tag", "previous-sha", "root", "out"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    source = Path(args.root)
    dest = Path(args.out)
    titles = git_titles(source, args.previous_sha, args.sha)
    notes = build_notes(
        tag=args.tag, sha=args.sha, previous_tag=args.previous_tag,
        previous_sha=args.previous_sha, titles=titles,
    )
    guide = build_guide(tag=args.tag, sha=args.sha)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "WHD_Release_Notes_zh-TW.md").write_text(notes, encoding="utf-8")
    (dest / "WHD_Windows_Guide_zh-TW.md").write_text(guide, encoding="utf-8")
    print(f"RELEASE_ZH_TW_READY tag={args.tag} sha={args.sha} changes={len(titles)}")


if __name__ == "__main__":
    main()
