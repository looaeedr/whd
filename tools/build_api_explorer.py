#!/usr/bin/env python3
"""Build the WHD public Python API browser from checked-in source, without imports.

This catalog documents source signatures only. It NEVER grants manufacturing
certification, advertises HTTP support, or executes Engine modules.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from html import escape
import json
from pathlib import Path

try:
    from tools.api_gui_call_index import attach_gui_call_sites
except ModuleNotFoundError:  # direct: python tools/build_api_explorer.py
    from api_gui_call_index import attach_gui_call_sites

ROOT = Path(__file__).resolve().parents[1]
ENTRY_MODULES = ("ae_engine/__init__.py", "ae_engine/manufacturing_api.py", "ae_engine/integration_api.py")
SOURCE_BASE = "https://github.com/looaeedr/whd/blob/localX/"
CATEGORIES = (
    ("integration", "CADSplit／WHD 整合入口"),
    ("export", "製造／DXF 輸出（需正式來源與 Gate）"),
    ("verify", "驗證／安全檢查（不等於製造放行）"),
    ("source", "輸入／PartSpec／來源轉換"),
    ("view", "預覽／投影／其它公開 API"),
)


def annotation(node: ast.AST | None) -> str:
    return ast.unparse(node) if node is not None else ""


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    def one(arg: ast.arg, default=None) -> str:
        result = arg.arg
        if arg.annotation is not None:
            result += ": " + annotation(arg.annotation)
        if default is not None:
            result += "=" + annotation(default)
        return result
    parts = [one(a, d) for a, d in zip(positional, defaults)]
    if args.posonlyargs:
        parts.insert(len(args.posonlyargs), "/")
    if args.vararg is not None:
        parts.append("*" + one(args.vararg))
    elif args.kwonlyargs:
        parts.append("*")
    parts.extend(one(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults))
    if args.kwarg is not None:
        parts.append("**" + one(args.kwarg))
    result = node.name + "(" + ", ".join(parts) + ")"
    if node.returns is not None:
        result += " -> " + annotation(node.returns)
    return result


def _parsed(root: Path, rel: str, cache: dict):
    if rel in cache:
        return cache[rel]
    file = root / rel
    if not file.is_file():
        cache[rel] = None
        return None
    cache[rel] = ast.parse(file.read_text(encoding="utf-8-sig"), filename=rel)
    return cache[rel]


def _exports(node: ast.Module) -> set[str] | None:
    for statement in node.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in statement.targets):
                try:
                    values = ast.literal_eval(statement.value)
                    return {v for v in values if isinstance(v, str)}
                except (ValueError, TypeError):
                    return None
    return None


def category(name: str, origins: set[str]) -> str:
    # The index stores full callable paths, not bare module names.
    # Match the integration module boundary without claiming any other
    # ae_engine.* symbol is an external integration/manufacturing API.
    if any(path.startswith("ae_engine.integration_api.") for path in origins):
        return "integration"
    if name.startswith(("export_", "save_", "generate_")):
        return "export"
    if name.startswith(("verify_", "validate_", "require_", "reject_")):
        return "verify"
    if name.startswith(("build_", "derive_", "resolve_", "prepare_", "receiving_manufacturing_")):
        return "source"
    return "view"


def find_public_api(root: Path = ROOT) -> list[dict]:
    cache: dict = {}
    functions: dict[tuple[str, str], dict] = {}
    for rel in ENTRY_MODULES:
        top = _parsed(root, rel, cache)
        if top is None:
            raise FileNotFoundError(rel)
        names = _exports(top) if rel.endswith("/__init__.py") else None
        visible = "ae_engine" if rel.endswith("/__init__.py") else rel.removesuffix(".py").replace("/", ".")
        candidates: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, str]] = []
        for stmt in top.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                candidates.append((stmt.name, stmt, rel))
            if isinstance(stmt, ast.ImportFrom) and stmt.level == 1 and stmt.module:
                child = "ae_engine/" + stmt.module.replace(".", "/") + ".py"
                parsed = _parsed(root, child, cache)
                if parsed is None:
                    continue
                definitions = {
                    f.name: f for f in parsed.body
                    if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                for alias in stmt.names:
                    if alias.name in definitions:
                        candidates.append((alias.asname or alias.name, definitions[alias.name], child))
        for public_name, fn, original in candidates:
            if public_name.startswith("_") or (names is not None and public_name not in names):
                continue
            key = (original, fn.name)
            row = functions.setdefault(key, {
                "name": fn.name,
                "signature": signature(fn),
                "doc": (ast.get_docstring(fn) or "").strip().splitlines()[0] if ast.get_docstring(fn) else "原始碼尚無說明；請看實作與契約",
                "source": original,
                "line": fn.lineno,
                "link": SOURCE_BASE + original + "#L" + str(fn.lineno),
                "entrypoints": set(),
            })
            row["entrypoints"].add(visible + "." + public_name)
    rows = []
    for row in functions.values():
        paths = sorted(row["entrypoints"])
        row["category"] = category(row["name"], row["entrypoints"])
        row["entrypoints"] = paths
        row["status"] = {
            "integration": "來源 API／有限 Verified Sink；不得推定外部製造",
            "export": "需按該函式的正式來源／認證 Gate 判斷",
            "verify": "驗證結果，不直接授權整箱加工",
            "source": "輸入／實體來源處理，不等同已出圖",
            "view": "公開功能；不直接推定製造放行",
        }[row["category"]]
        rows.append(row)
    rows.sort(key=lambda r: (list(dict(CATEGORIES)).index(r["category"]) if False else
                             [k for k, _ in CATEGORIES].index(r["category"]),
                             r["name"], r["source"]))
    return rows


def render_markdown(rows: list[dict]) -> str:
    lines = [
        "---",
        "whd_doc_role: REFERENCE",
        "whd_contract: project-reference",
        "whd_canonical: null",
        "whd_schema: WHD_DOC_META_V1",
        "---",
        "# WHD API 功能／參數／連結 — 自動產生索引",
        "",
        "**這頁從 `ae_engine` 公開 Python 函式及 GUI／Phase6 的真實呼叫 AST 自動產生；不手動維護 API 名單。**",
        "",
        "- [網頁式 API 查詢器（需 GitHub Pages 啟用）](https://looaeedr.github.io/whd/api/)",
        "- [HTML 查詢器原始碼](docs/api/index.html)",
        "- [完整 Headless API 契約](HEADLESS_API.md)",
        "- [唯一 CURRENT 製造架構規範](個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md)",
        "- [WHD × CADSplit API v5.1 REFERENCE](docs/integrations/WHD_CADSplit_API_架構與權威整合_REFERENCE_v5.1.md)",
        "",
        "> **注意**：此目錄是 Python 同程序呼叫的資訊索引，**不是 HTTP／REST/Swagger**。函式可 import ≠ 已取得任意 Family／板件／操作的正式製造資格；source-only Worker/EXE 外部製造仍停用。網站需完成 GitHub Pages 設定才可直接開啟。正式製造資格依 CURRENT、Registry 及當次驗證結果。",
        "",
        f"公開 callable 共 **{len(rows)}** 項（依來源檔＋函式去重；可有多個公開 import 路徑）。",
        "",
    ]
    receiving = [r for r in rows if any(s["scope"] == "receiving" for s in r.get("gui_usage", ()))]
    lines.extend([
        f"## 受電箱 GUI 直接呼叫的公開 API（{len(receiving)}）",
        "",
        "以下只記錄 AST 中的實際 Python 呼叫位置；共用 GUI／Phase6 函式請在網頁選「全部 GUI／Phase6 呼叫」查詢。"
        " 靜態呼叫 ≠ 執行成功、API 製造認證或完整 GUI 覆蓋。",
        "",
        "| API／原始碼 | GUI 呼叫位置 | 參數簽名 |",
        "| --- | --- | --- |",
    ])
    for row in receiving:
        sites = [site for site in row["gui_usage"] if site["scope"] == "receiving"]
        where = "<br>".join("[" + site["source"] + ":" + str(site["line"]) + "](" + site["link"] + ")" for site in sites)
        safe_signature = row["signature"].replace("|", "\\|")
        lines.append(f"| [{row['name']}]({row['link']}) | {where} | `{safe_signature}` |")
    lines.append("")
    for key, title in CATEGORIES:
        subset = [r for r in rows if r["category"] == key]
        lines.extend([f"## {title}（{len(subset)}）", "", "| 功能／原始碼 | Python 呼叫路徑 | 參數與回傳簽名 | 說明／製造範圍 |", "| --- | --- | --- | --- |"])
        for row in subset:
            safe = lambda s: str(s).replace("|", "\\|").replace("\n", " ").replace("  ", " ")
            routes = "<br>".join("\u0060" + p + "\u0060" for p in row["entrypoints"])
            lines.append(
                "| [" + safe(row["name"]) + "](" + row["link"] + ") | "
                + routes + " | \u0060" + safe(row["signature"]) + "\u0060 | "
                + safe(row["doc"]) + "；" + safe(row["status"]) + " |"
            )
        lines.append("")
    lines.extend([
        "## 自動更新方式",
        "",
        "GitHub Actions 每次 `localX` Engine、GUI／Phase6 或索引產生器相關變更會從當次 source 重建網頁查詢器並部署 GitHub Pages（必須啟用 Pages 的 Actions 來源）。",
        "新加入 \u0060ae_engine.manufacturing_api\u0060／\u0060ae_engine.integration_api\u0060／\u0060ae_engine.__init__\u0060 公開的 Python 函式會自動進入下一版 catalog，含函式簽名、說明與可點擊的原始碼位置。",
        "這份版本化 Markdown 在 PR 建立時使用 \u0060python tools/build_api_explorer.py\u0060 再產生，CI 可檢查是否與程式保持同步；不以 GUI 欄位或測試 helper 假冒正式公開 API。",
        "",
    ])
    return "\n".join(lines)


def render_html(rows: list[dict]) -> str:
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    options = "\n".join(
        '<option value="' + escape(key) + '">' + escape(title) + '</option>'
        for key, title in CATEGORIES
    )
    return """<!doctype html>
<html lang="zh-Hant">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>WHD API 功能／參數／原始碼查詢</title>
<style>
:root{color-scheme:light dark;font-family:system-ui,'Noto Sans TC',sans-serif}
body{max-width:1240px;margin:0 auto;padding:24px}
h1{font-size:1.6rem;margin-bottom:.5rem}
p{line-height:1.7}
.toolbar{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}
input,select{font:inherit;padding:12px;border:1px solid #888;border-radius:8px;flex:1;min-width:220px}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #8885;overflow-wrap:anywhere}
th{position:sticky;top:0;background:Canvas}
code{font-size:.86rem;white-space:pre-wrap}
.small{opacity:.75;font-size:.85rem}
a{color:LinkText}
.tablewrap{overflow-x:auto}
</style></head>
<body>
<h1>WHD API｜受電箱 GUI 與 Engine 接線查詢</h1>
<p>從 <code>ae_engine</code> 公開函式與 GUI／Phase6 實際呼叫位置自動產生。Engine 或 GUI 呼叫變更合入 <code>localX</code> 後，由既有 GitHub Actions 重建網頁。</p>
<p class="small">「受電箱 GUI」表示受電箱相關原始碼的直接靜態呼叫；共用 GUI 接口另可切換檢視。未命中不表示無間接呼叫。Python API 可見 ≠ 已完成真正 DXF 製造驗收；本網站不是 HTTP／Swagger endpoint。</p>
<p><a href="https://github.com/looaeedr/whd/blob/localX/HEADLESS_API.md">詳細 API 文件</a> · <a href="https://github.com/looaeedr/whd/blob/localX/API_INDEX.md">Markdown 功能表</a></p>
<div class="toolbar">
<select id="scope" aria-label="GUI 呼叫範圍"><option value="receiving">受電箱 GUI 直接呼叫</option><option value="gui">全部 GUI／Phase6 直接呼叫</option><option value="all">所有公開 Engine API</option><option value="unused">GUI 無直接呼叫記錄</option></select>
<input id="search" type="search" placeholder="搜尋功能、Python API、參數或說明" aria-label="搜尋 API">
<select id="cat" aria-label="功能分類"><option value="">所有功能</option>CAT_OPTIONS</select>
</div>
<p id="count" role="status"></p>
<div class="tablewrap"><table><thead><tr><th>功能／原始碼</th><th>Python 呼叫入口</th><th>參數與回傳</th><th>用途／製造範圍</th><th>GUI 呼叫證據</th></tr></thead><tbody id="items"></tbody></table></div>
<script>
const rows = API_DATA;
const search = document.getElementById("search"), cat = document.getElementById("cat"), scope = document.getElementById("scope");
const items = document.getElementById("items"), count = document.getElementById("count");
function el(tag, parent, value) {const n=document.createElement(tag);if(value!==undefined)n.textContent=value;parent.appendChild(n);return n}
function draw() {
 const q=search.value.trim().toLocaleLowerCase();
 const filtered=rows.filter(r=>(!cat.value||r.category===cat.value)&&
 (scope.value==="all" || (scope.value==="receiving" && r.gui_usage.some(s=>s.scope==="receiving")) ||
 (scope.value==="gui" && r.gui_usage.length>0) || (scope.value==="unused" && !r.gui_usage.length))&&
 (!q||[r.name,r.signature,r.doc,r.status,...r.entrypoints,...r.gui_usage.map(s=>s.source)].join(" ").toLocaleLowerCase().includes(q)));
 count.textContent="符合 "+filtered.length+" / "+rows.length+" 項公開函式（靜態呼叫證據，非製造認證）";
 items.replaceChildren();
 for(const r of filtered){
   const tr=el("tr",items);
   const c1=el("td",tr);const a=el("a",c1,r.name);a.href=r.link;a.target="_blank";a.rel="noopener noreferrer";
   const c2=el("td",tr);for(const path of r.entrypoints){el("code",c2,path);el("div",c2);}
   el("code",el("td",tr),r.signature);
   const c4=el("td",tr);el("div",c4,r.doc);el("small",c4,r.status);
   const c5=el("td",tr);const sources=scope.value==="receiving" ? r.gui_usage.filter(s=>s.scope==="receiving") : r.gui_usage;
   if(!sources.length){el("small",c5,"未發現 GUI 直接呼叫");}
   for(const site of sources){const a=el("a",c5,site.source+":"+site.line+"（"+(site.scope==="receiving"?"受電箱":"共用")+"）");a.href=site.link;a.target="_blank";a.rel="noopener noreferrer";el("div",c5);}
 }
}
search.addEventListener("input",draw);cat.addEventListener("change",draw);scope.addEventListener("change",draw);draw();
</script></body></html>
""".replace("API_DATA",data).replace("CAT_OPTIONS",options)


def generate(root: Path = ROOT) -> tuple[str, str, list[dict]]:
    rows = attach_gui_call_sites(root, find_public_api(root))
    return render_markdown(rows), render_html(rows), rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="fail if committed index is stale")
    args = parser.parse_args()
    markdown, html, rows = generate(args.root)
    files = ((args.root / "API_INDEX.md", markdown), (args.root / "docs/api/index.html", html))
    stale = [str(path) for path, content in files if not path.is_file() or path.read_text(encoding="utf-8") != content]
    if args.check:
        if stale:
            print("API_INDEX_OUTDATED: " + ", ".join(stale))
            return 1
    else:
        for path, content in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    print(f"API_CATALOG_BUILT functions={len(rows)} stale={len(stale)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
