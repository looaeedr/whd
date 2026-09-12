from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH_MAP = "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
MFG = "個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md"


def path(rel: str) -> Path:
    p = ROOT / rel
    if not p.exists():
        raise SystemExit(f"missing required file: {rel}")
    return p


def read(rel: str) -> str:
    return path(rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path(rel).write_text(text, encoding="utf-8")


def prepend_once(rel: str, marker: str, block: str) -> None:
    text = read(rel)
    if marker in text[:1500]:
        return
    write(rel, block.rstrip() + "\n\n" + text)


def replace_once(rel: str, old: str, new: str) -> None:
    text = read(rel)
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"expected anchor missing in {rel}: {old[:120]!r}")
    write(rel, text.replace(old, new, 1))


def insert_before_once(rel: str, anchor: str, marker: str, block: str) -> None:
    text = read(rel)
    if marker in text:
        return
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit(f"anchor missing in {rel}: {anchor!r}")
    write(rel, text[:idx] + block.rstrip() + "\n\n" + text[idx:])


CURRENT_POINTERS = f"""Current authority pointers：
- `{AUTH_MAP}` — contract/role ownership map。
- `{MFG}` — 現行 `ae_engine` 製造架構、公開 API 與 Certified Registry boundary。
- `AGENTS.md` — Agent 啟動、Preflight、派工與驗收流程入口。"""

# Root README is a human overview, never the manufacturing architecture SSOT.
prepend_once(
    "README.md",
    "<!-- WHD_DOC_ROLE role=REFERENCE contract=repo-overview -->",
    f"""<!-- WHD_DOC_ROLE role=REFERENCE contract=repo-overview -->
> **[REFERENCE]** 本 README 只提供專案概覽；其中既有架構描述保留作歷史背景，不擁有 current manufacturing contract。
> {CURRENT_POINTERS}""",
)

# AI_HANDOFF is retained as a chronological ledger; dated claims cannot remain CURRENT.
prepend_once(
    "AI_HANDOFF.md",
    "<!-- WHD_DOC_ROLE role=REFERENCE contract=handoff-ledger -->",
    f"""<!-- WHD_DOC_ROLE role=REFERENCE contract=handoff-ledger -->
> **[REFERENCE / HANDOFF LEDGER]** 本檔保留歷史接手紀錄與 migration evidence，不是 current domain SSOT，也不是新的第一入口。
> {CURRENT_POINTERS}""",
)
replace_once(
    "AI_HANDOFF.md",
    "## [CURRENT] 2026-09-02 Runtime semantic guard",
    "## [HISTORICAL/SUPERSEDED] 2026-09-02 Runtime semantic guard",
)
replace_once(
    "AI_HANDOFF.md",
    "本文件是下一個 AI 的第一入口。需要細節時再讀 `handoff/`。",
    "[HISTORICAL] 本文件曾是下一個 AI 的第一入口；current first entry 已改為 `AGENTS.md`，domain authority 依 Canonical Authority Map 導航。",
)

# AGENTS remains CURRENT only for startup/process governance. Sections 1-10 are legacy architecture/roadmap.
prepend_once(
    "AGENTS.md",
    "<!-- WHD_DOC_ROLE role=CURRENT contract=agent-startup-process -->",
    f"""<!-- WHD_DOC_ROLE role=CURRENT contract=agent-startup-process -->
> **[CURRENT — PROCESS ONLY]** `AGENTS.md` 擁有 Agent 啟動、Knowledge Preflight、派工與驗收流程入口；不擁有製造公式或 ae_engine 架構真值。
> {CURRENT_POINTERS}""",
)
insert_before_once(
    "AGENTS.md",
    "# 1. 專案核心精神",
    "<!-- WHD_SECTION_ROLE role=HISTORICAL contract=legacy-v5-architecture-roadmap -->",
    """<!-- WHD_SECTION_ROLE role=HISTORICAL contract=legacy-v5-architecture-roadmap -->
> **[HISTORICAL/SUPERSEDED]** 第 1～10 節是 V5 / Layer A-B-C / GUI Preview 時代的架構與 roadmap snapshot，只保留 provenance，不參與 current routing。現行製造架構請讀 Canonical Authority Map 指向的 ae_engine 規範。""",
)
insert_before_once(
    "AGENTS.md",
    "# 11. Skill Preflight 強制啟動鏈",
    "<!-- WHD_SECTION_ROLE role=CURRENT contract=agent-startup-process RESUME -->",
    """<!-- WHD_SECTION_ROLE role=CURRENT contract=agent-startup-process RESUME -->
> **[CURRENT PROCESS RESUMES]** 以下 Skill Preflight / Registry / remote QA / execution governance 仍屬 current process contract；上方 HISTORICAL 標記不延伸到此處。""",
)

# handoff/00 becomes a pointer-only compatibility entry.
handoff00 = f"""<!-- WHD_DOC_ROLE role=MIRROR contract=handoff-entry POINTER_ONLY -->
# 00 — Handoff Compatibility Entry

> **[MIRROR / POINTER_ONLY]** 此路徑只保留舊入口相容性，不複製 current authority。

Current entry / authority：
- `../AGENTS.md` — Agent 啟動與 Preflight process。
- `../{AUTH_MAP}` — CURRENT / REFERENCE / MIRROR / HISTORICAL ownership map。
- `../{MFG}` — 現行 ae_engine manufacturing / Certified Registry contract。

`handoff/01_ARCHITECTURE.md`、`handoff/05_NEXT_STEPS.md` 等舊 handoff 檔保留為 historical snapshot；不得再由本 mirror 把它們升格為 current architecture / roadmap。
"""
write("handoff/00_AI_HANDOFF_README.md", handoff00)

historical_docs = {
    "handoff/01_ARCHITECTURE.md": (
        "<!-- WHD_DOC_ROLE role=HISTORICAL contract=architecture-snapshot -->",
        "architecture snapshot",
    ),
    "handoff/05_NEXT_STEPS.md": (
        "<!-- WHD_DOC_ROLE role=HISTORICAL contract=roadmap-snapshot -->",
        "roadmap snapshot",
    ),
    "目前主要任務.md": (
        "<!-- WHD_DOC_ROLE role=HISTORICAL contract=task-roadmap-snapshot -->",
        "task / migration roadmap snapshot",
    ),
    "docs/superpowers/CURRENT_API_INVENTORY_20260818.md": (
        "<!-- WHD_DOC_ROLE role=HISTORICAL contract=api-inventory-snapshot snapshot=2026-08-18 -->",
        "HISTORICAL SNAPSHOT dated 2026-08-18",
    ),
}
for rel, (marker, label) in historical_docs.items():
    prepend_once(
        rel,
        marker,
        f"""{marker}
> **[{label}]** 此檔保留當時 evidence / roadmap / API 盤點；**不參與 current routing**，不得以檔名中的 `CURRENT`、`目前`、`Next Steps` 或舊架構語氣覆蓋現行 authority。
> Current authority：`{AUTH_MAP}`；製造架構/API：`{MFG}`。""",
    )

prepend_once(
    "docs/superpowers/README.md",
    "<!-- WHD_DOC_ROLE role=REFERENCE contract=superpowers-history-index -->",
    f"""<!-- WHD_DOC_ROLE role=REFERENCE contract=superpowers-history-index -->
> **[REFERENCE / HISTORY INDEX]** 本目錄 README 索引 dated Superpowers/spec/verification evidence，不是 current manufacturing 或 project roadmap authority。
> Current authority：`{AUTH_MAP}`；製造架構/API：`{MFG}`。""",
)

# Global collaboration rules become a reference process companion, not architecture/domain owner.
prepend_once(
    "個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md",
    "<!-- WHD_DOC_ROLE role=REFERENCE contract=global-ai-collaboration-reference -->",
    f"""<!-- WHD_DOC_ROLE role=REFERENCE contract=global-ai-collaboration-reference -->
> **[REFERENCE]** 本檔補充跨任務 AI 協作原則；current startup/process gate 由 `AGENTS.md` + project Skills 擁有，domain owner 依 `{AUTH_MAP}` 查找。
> `{MFG}` 是 current manufacturing architecture authority。
> `06_踩坑記錄與防錯經驗庫.md` 是 REFERENCE / incident ledger，不是 domain SSOT；可提供事故背景，但不得覆蓋 focused CURRENT authority。""",
)
replace_once(
    "個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md",
    "- **邊界防護**：確認任務目標與模組職責（Layer A 純幾何、Layer B 轉接、Layer C GUI/拆圖），嚴禁越權或破壞分層。",
    f"- **邊界防護**：先依 `{AUTH_MAP}` 找到該 contract 的 CURRENT owner；製造架構以 `{MFG}` 為準。舊 Layer A/B/C 描述只屬 historical evidence，不得再當 current module boundary。",
)
replace_once(
    "個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md",
    "- **避坑檢核**：執行前主動查閱 `06_踩坑記錄與防錯經驗庫.md`，確認不觸碰禁忌。",
    "- **避坑檢核**：Preflight 要求時讀 `06_踩坑記錄與防錯經驗庫.md` 作 REFERENCE / incident ledger；真正 normative rule 必須再回到 Canonical Authority Map 指向的 focused CURRENT authority。",
)
replace_once(
    "個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md",
    "- 若修改源自踩坑、錯誤判斷或現場回報，必須同時追加至 `第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`。",
    "- 若修改源自踩坑、錯誤判斷或現場回報，優先更新該 domain 的 focused CURRENT spec/Skill/pitfall；`第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md` 只追加事件索引／歷史 lesson，禁止再造平行 CURRENT SSOT。",
)

# Giant 06 becomes a reference/incident ledger. Preserve incidents, mark known superseded ownership claims in place.
global06 = "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md"
prepend_once(
    global06,
    "<!-- WHD_DOC_ROLE role=REFERENCE contract=pitfall-ledger -->",
    f"""<!-- WHD_DOC_ROLE role=REFERENCE contract=pitfall-ledger -->
> **[REFERENCE / INCIDENT LEDGER]** 本檔保存踩坑、事故、歷史修正與跨域索引；**不是 CURRENT domain authority**，也不得因內容較長就覆蓋 focused spec / Registry / Skill。
> Current owner 查找一律先讀 `{AUTH_MAP}`；manufacturing 架構/API 讀 `{MFG}`。若本檔段落與 CURRENT owner 衝突，以 CURRENT owner 為準，並在舊段落原位置標 `HISTORICAL / SUPERSEDED`。""",
)
insert_before_once(
    global06,
    "### 50. 先用截角公式猜 Assembly Relief，沒有從真實 Collision Region 反推 CUTTING",
    "SUPERSEDED_BY_CERTIFIED_RELIEF_REGISTRY",
    f"""<!-- WHD_SECTION_ROLE role=HISTORICAL SUPERSEDED_BY_CERTIFIED_RELIEF_REGISTRY -->
> **[HISTORICAL/SUPERSEDED]** 本段 collision-first/backprojection ownership 是早期 discovery 架構 evidence。Registry HIT 的 current production authority 已改由 `{MFG}` + Certified Registry 擁有；3D collision/backprojection 對 HIT 只做 shadow validation，MISS 才可 discovery/candidate。""",
)
insert_before_once(
    global06,
    "## 2026-09-07 — Receiving Divider / 多件式箱身 / Dynamic 2D 單源規則",
    "WHD_SECTION_ROLE role=HISTORICAL superseded_contract=receiving-divider-2026-09-07",
    f"""<!-- WHD_SECTION_ROLE role=HISTORICAL superseded_contract=receiving-divider-2026-09-07 -->
> **[HISTORICAL/SUPERSEDED]** 本節保留 2026-09-07 Receiving/Divider 施工 evidence；後續 Certified Registry、current Family/Topology 與 focused rules 已取代其中 current-looking ownership。不得由本節反推 production。Current owner 請依 `{AUTH_MAP}` / `{MFG}`。""",
)
text = read(global06)
recv_anchor = "## 2026-09-07 — Receiving Divider / 多件式箱身 / Dynamic 2D 單源規則"
pos = text.find(recv_anchor)
if pos < 0:
    raise SystemExit("Receiving Divider historical anchor missing")
next_section = text.find("\n## ", pos + len(recv_anchor))
if next_section < 0:
    next_section = len(text)
segment = text[pos:next_section]
if "CURRENT Requirement Authority" in segment:
    segment = segment.replace("CURRENT Requirement Authority", "HISTORICAL Requirement Evidence", 1)
    text = text[:pos] + segment + text[next_section:]
    write(global06, text)

# Extend the canonical map with machine-readable T7 role rows; no duplicated prose authority.
auth_rows = f"""
## T7 Current / History entrypoint roles

<!-- WHD_AUTHORITY_ROW contract=agent-startup-process role=CURRENT path=AGENTS.md -->
contract=agent-startup-process role=CURRENT path=AGENTS.md

<!-- WHD_AUTHORITY_ROW contract=repo-overview role=REFERENCE path=README.md -->
contract=repo-overview role=REFERENCE path=README.md

<!-- WHD_AUTHORITY_ROW contract=handoff-ledger role=REFERENCE path=AI_HANDOFF.md -->
contract=handoff-ledger role=REFERENCE path=AI_HANDOFF.md

<!-- WHD_AUTHORITY_ROW contract=manufacturing-architecture role=CURRENT path={MFG} -->
contract=manufacturing-architecture role=CURRENT path={MFG}

<!-- WHD_AUTHORITY_ROW contract=manufacturing-architecture role=HISTORICAL path=handoff/01_ARCHITECTURE.md -->
contract=manufacturing-architecture role=HISTORICAL path=handoff/01_ARCHITECTURE.md

<!-- WHD_AUTHORITY_ROW contract=api-inventory role=HISTORICAL path=docs/superpowers/CURRENT_API_INVENTORY_20260818.md -->
contract=api-inventory role=HISTORICAL path=docs/superpowers/CURRENT_API_INVENTORY_20260818.md

<!-- WHD_AUTHORITY_ROW contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md -->
contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
""".strip()
auth_rel = AUTH_MAP
text = read(auth_rel)
if "contract=agent-startup-process role=CURRENT path=AGENTS.md" not in text:
    marker = "<!-- WHD_AUTHORITY_MAP_V1 -->"
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit("authority map marker missing")
    idx += len(marker)
    text = text[:idx] + "\n\n" + auth_rows + "\n" + text[idx:]
    write(auth_rel, text)

print("T7 current/history cleanup applied successfully")
