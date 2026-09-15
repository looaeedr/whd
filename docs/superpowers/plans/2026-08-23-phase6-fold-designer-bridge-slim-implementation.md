# Phase6 Fold Designer Bridge 瘦身實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 將 EndCap 狀態語意與 Fold Profile 機械規則從 `fold_designer_bridge.py` 移到真正 owner module，讓 Bridge 回到 adapter 角色且不改行為。

**Architecture:** `phase6_endcap_semantics.py` 擁有 assembly/FW/corner raw 語意；`phase6_fold_profiles.py` 擁有 Fold Profile 與 linked mating chain。Bridge 僅 import/re-export 相容名稱並保留 Fold Designer/Tk adapter。

**Tech Stack:** Python 3、pytest、Tk/Xvfb、現有 AE contracts。

**Spec:** `docs/superpowers/specs/2026-08-23-phase6-fold-designer-bridge-slim-design.md`

## Global Constraints

- 不改 `.p6fold` schema。
- 不改 UI 外觀/操作。
- 不改製造幾何公式。
- `config.ini` 不得修改。
- 所有新增/修改說明使用繁體中文。

---

### Task 1: EndCap semantics owner

**Files:**
- Create: `phase6_endcap_semantics.py`
- Modify: `fold_designer_bridge.py`
- Test: `tests/test_phase6_bridge_domain_ownership.py`

**Interfaces:**
- Produces: `selection_to_raw`, `selection_from_raw`, `resolve_box_assembly_type`, `apply_box_assembly_type_to_raw_state`, `normalize_endcap_fw_state`, `resolve_endcap_fw`, `set_endcap_fw_follow`, `set_endcap_fw_override`, assembly labels。

- [x] Step 1: 寫 RED，直接 import 新 module 並驗證 assembly/FW 行為。
- [x] Step 2: 執行單檔測試，確認因 module 尚不存在而失敗。
- [x] Step 3: 移動既有實作，不改公式；Bridge 改成 import alias。
- [x] Step 4: 重跑測試轉 GREEN，並跑 shared assembly regression。

### Task 2: Fold Profile owner

**Files:**
- Create: `phase6_fold_profiles.py`
- Modify: `fold_designer_bridge.py`
- Test: `tests/test_phase6_bridge_domain_ownership.py`

**Interfaces:**
- Produces: profile build/read/merge、linked EndCap chain、UI length/angle conversion、`profile_to_fold_segments`。

- [x] Step 1: 寫 RED，直接 import Fold Profile module，鎖 5/20 segment、OVERLAY flat X、bridge compatibility。
- [x] Step 2: 執行單檔測試確認 RED。
- [x] Step 3: 移動既有 pure functions，Bridge 改成 import/re-export；`_phase6_rebuild_linked_endcaps` 留在 Bridge adapter。
- [x] Step 4: 重跑 linked fold/shared assembly regressions。

### Task 3: Production caller ownership

**Files:**
- Modify: `gui.py`
- Modify: `fold_designer_bridge.py`
- Test: `tests/test_phase6_bridge_domain_ownership.py`

**Interfaces:**
- Consumes: Task 1/2 owner modules。
- Produces: GUI 直接依賴 owner，Bridge 無 domain implementation。

- [x] Step 1: 寫 ownership RED：GUI 不得從 Bridge import domain names；Bridge 不得重新 def domain names。
- [x] Step 2: 改 production imports 與必要 internal references。
- [x] Step 3: 執行 ownership test + GUI/3D/EndCap regressions。

### Task 4: 全套驗證與交付

**Files:**
- Modify: `使用說明書.md`
- Modify: `DELIVERY_README.md`
- Modify: `修改日誌/20260823.md`
- Create: `docs/superpowers/verification/2026-08-23-phase6-fold-designer-bridge-slim-verification.md`

- [x] Step 1: `py_compile`。
- [x] Step 2: 聚焦回歸。
- [x] Step 3: 原始完整 suite，保留既知 `/mnt/data/自訂.p6fold` 缺件證據。
- [x] Step 4: 明確排除 4 個既知 fixture 後完整 0-failure suite。
- [x] Step 5: 驗證 `config.ini` SHA256 不變。
- [x] Step 6: 產出同一 Asia/Taipei 時間戳 FULL/UPDATE，UPDATE 不含 `config.ini`，兩包 CRC 驗證。
