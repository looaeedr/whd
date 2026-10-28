# -*- coding: utf-8 -*-
"""Package standalone NFB PAD tool from WHD's SAME authoritative sources.

No duplicated formula modules are committed. The archive is built by copying
the current engine, source CSV V5 and common tooling rule at packaging time.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "nfb_pad_standalone.py",
    "ae_engine/receiving_nfb_pad_standalone.py",
    "ae_engine/receiving_nfb_pad_generator.py",
    "ae_engine/receiving_nfb_numeric_catalog.py",
    "基準檔/開孔/NFB/墊高片共用加工規則.json",
    *(
        f"基準檔/開孔/NFB/數值規格/{brand}/NFB數值規格.csv"
        for brand in ("士林", "東元", "伍菱")
    ),
)

README = """WHD NFB 墊高片獨立草稿預覽工具

1. 先解壓縮本 ZIP 到新資料夾，完整保留 ae_engine 和 基準檔 子目錄。
2. Windows：雙擊 啟動_NFB墊高片.bat，或執行 python nfb_pad_standalone.py。
3. 需要 Python 3.11+ 與 Tkinter。草稿 DXF 輸出另外需要 pip install ezdxf。
4. 加入實體層與 CSV V5 NFB 型號；同一層由最深 NFB 計算較淺者的 PAD。
5. 2D 展開是尺寸草稿；3D 是折彎示意，不是底板/碰撞驗收。
6. DXF 是 DRAFT_* 非加工草圖，有 NOT FOR MANUFACTURING 文字及 JSON 收據。
7. 不含 WHD 主 GUI，不需要 config.ini，也不修改原 WHD 受電箱專案。
8. 真正板件、固定片、底板孔與正式 CHECK/Q、NC 必須回 WHD 裝配驗證。

來源：打包當下同一份 WHD 共用 PAD 引擎、CSV V5 與加工規則。
"""

WINDOWS_LAUNCHER = (
    "@echo off\r\n"
    "cd /d \"%~dp0\"\r\n"
    "py -3 nfb_pad_standalone.py\r\n"
    "if errorlevel 1 python nfb_pad_standalone.py\r\n"
    "if errorlevel 1 pause\r\n"
)


def make_archive(output: str | Path, *, source_root: Path = ROOT) -> Path:
    """Create one portable ZIP. Refuse existing output and missing input data."""
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"獨立工具封裝已存在，禁止覆寫：{destination}")
    for relative in SOURCE_FILES:
        path = source_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"獨立工具缺少來源：{relative}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "x", compression=ZIP_DEFLATED) as archive:
        archive.writestr("ae_engine/__init__.py", "")
        for relative in SOURCE_FILES:
            archive.write(source_root / relative, arcname=relative)
        archive.writestr("README_獨立工具.txt", README.encode("utf-8"))
        archive.writestr("啟動_NFB墊高片.bat", WINDOWS_LAUNCHER.encode("ascii"))
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="封裝獨立 NFB 墊高片草稿工具")
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "dist" / "NFB_PAD_STANDALONE_DRAFT.zip",
    )
    args = parser.parse_args()
    print(make_archive(args.output))


if __name__ == "__main__":
    main()
