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


# Only evidence-backed, user-facing Traditional Chinese highlights belong in
# Release notes and bundled 本次更新.md. Never dump raw commit titles.
_TOPICS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("#2379", "closed profile", "lwpolyline", "bulge", "edge cycle"),
     "**門板開孔與幾何**：加強原始 DXF 輪廓、矩形與座標的來源核對；異常弧段或交叉邊界不會被當成有效開孔。"),
    (("#2380", "rollback", "durable journal", "original dxf backup", "staged dxf"),
     "**多份 DXF 的資料保護**：補強原檔備份、批次處理與中斷回復的內部驗證；相關能力仍屬內部整合，並非全面開放。"),
    (("#2378", "indicator small-door", "small-door prepare", "cadsplit"),
     "**小門與外部工具串接**：補強門板、小門與來源基準的對應檢查；目前屬整合驗證，未宣稱全部功能已對外啟用。"),
    (("release", "pyinstaller", "windows exe", "zh-tw", "packaging"),
     "**Windows 交付**：加強同版 EXE、完整下載包、檔案校驗與繁體中文更新說明的發布檢查。"),
    (("nfb", "receiving", "pad", "base plate"),
     "**受電箱與 NFB 配置**：整理相關板件、底板及配置的操作與來源驗證。"),
    (("cadcraft", "hole editor", "hole editing"),
     "**開孔編輯**：補強開孔操作與 CADCraft 資料交換的驗證。"),
    (("save-reload", "save/reload", "p6fold", "persist", "snapshot"),
     "**專案資料一致性**：補強存檔、重新開啟與編輯結果的核對。"),
    (("2d", "3d", "viewport", "gui", "preview", "finalscene"),
     "**操作畫面**：整理預覽顯示、操作流程及相關驗證。"),
)
_MAX_HIGHLIGHTS = 5


def validate_notes(notes: str) -> None:
    """Reject an English commit dump even when its heading is zh-TW."""
    if "## 本次主要更新" not in notes or "## 下載與使用" not in notes:
        raise ValueError("RELEASE_NOTES_ZH_TW_SECTIONS_MISSING")
    if "## 逐項變更" in notes or re.search(
        r"(?m)^\s*[-*]\s*(?:feat|fix|test|docs|chore|ci|build|refactor)[(:! ]",
        notes, flags=re.IGNORECASE,
    ):
        raise ValueError("RELEASE_NOTES_RAW_COMMIT_DUMP_FORBIDDEN")
    if len(notes) > 2000:
        raise ValueError("RELEASE_NOTES_MUST_BE_CONCISE")
    if not (1 <= len(re.findall(r"(?m)^- \*\*[^*]+\*\*：", notes)) <= _MAX_HIGHLIGHTS):
        raise ValueError("RELEASE_NOTES_HIGHLIGHT_COUNT_OUT_OF_RANGE")


def build_notes(
    *, tag: str, sha: str, previous_tag: str, previous_sha: str,
    titles: list[str],
) -> str:
    if not tag.startswith("v") or not previous_tag.startswith("v"):
        raise ValueError("RELEASE_NOTES_INVALID_TAG")
    if not SHA.fullmatch(sha) or not SHA.fullmatch(previous_sha) or sha == previous_sha:
        raise ValueError("RELEASE_NOTES_INVALID_EXACT_SHA")
    subjects = [
        " ".join(title.strip().split()).casefold()
        for title in titles
        if title.strip() and not title.startswith("Merge pull request")
    ]
    if not subjects:
        raise ValueError("RELEASE_NOTES_EMPTY_SOURCE_DIFF")
    highlights: list[str] = []
    for terms, sentence in _TOPICS:
        if any(any(term in title for term in terms) for title in subjects):
            highlights.append(sentence)
            if len(highlights) == _MAX_HIGHLIGHTS:
                break
    if not highlights:
        highlights.append(
            "**品質與穩定性**：本次以既有程式的調整與回歸驗證為主，"
            "未確認可另外宣稱的新操作功能。"
        )
    lines = [
        "# WHD 正式版更新重點", "",
        f"**版本：** `{tag}`  ",
        f"**正式產品來源：** `{sha}`  ",
        f"**上一正式版：** `{previous_tag}`", "",
        "## 本次主要更新", "",
        *[f"- {item}" for item in highlights], "",
        "以上依實際版本差異歸納重點，不逐條照抄開發提交；"
        "完整技術紀錄可從 GitHub 比較版本查閱：",
        f"https://github.com/looaeedr/whd/compare/{previous_sha}...{sha}", "",
        "## 下載與使用", "",
        f"下載 `WHD_Windows_x64_{tag}.zip`，完整解壓後執行 `WHD/WHD.exe`。",
        "更新前先備份設定、基準 DXF、CSV 與 `.p6fold` 專案；"
        "不要直接覆蓋舊版資料夾。GitHub 的 Source code ZIP 不是執行版。", "",
        "**驗收範圍：** Windows EXE 可建立及啟動，不代表所有現場型號與機台"
        "都已完成製造驗收；CADCraft 外部程式不包含在 WHD ZIP 中。", "",
    ]
    notes = "\n".join(lines)
    validate_notes(notes)
    return notes


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
