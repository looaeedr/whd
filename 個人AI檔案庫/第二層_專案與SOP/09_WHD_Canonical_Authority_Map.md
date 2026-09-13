# WHD Canonical Authority Map

<!-- WHD_AUTHORITY_MAP_V1 -->

## T7 Current / History entrypoint roles

<!-- WHD_AUTHORITY_ROW contract=agent-startup-process role=CURRENT path=AGENTS.md -->
contract=agent-startup-process role=CURRENT path=AGENTS.md

<!-- WHD_AUTHORITY_ROW contract=repo-overview role=REFERENCE path=README.md -->
contract=repo-overview role=REFERENCE path=README.md

<!-- WHD_AUTHORITY_ROW contract=handoff-ledger role=REFERENCE path=AI_HANDOFF.md -->
contract=handoff-ledger role=REFERENCE path=AI_HANDOFF.md

<!-- WHD_AUTHORITY_ROW contract=manufacturing-architecture role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md -->
contract=manufacturing-architecture role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md

<!-- WHD_AUTHORITY_ROW contract=manufacturing-architecture role=HISTORICAL path=handoff/01_ARCHITECTURE.md -->
contract=manufacturing-architecture role=HISTORICAL path=handoff/01_ARCHITECTURE.md

<!-- WHD_AUTHORITY_ROW contract=api-inventory role=HISTORICAL path=docs/superpowers/CURRENT_API_INVENTORY_20260818.md -->
contract=api-inventory role=HISTORICAL path=docs/superpowers/CURRENT_API_INVENTORY_20260818.md

<!-- WHD_AUTHORITY_ROW contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md -->
contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md

本文件只負責回答「同一個工程 contract 現在到底由哪一份文件擁有」。它不複製各 domain 的完整規格，也不取代 domain canonical 文件本身。

## Authority roles

- `CURRENT`：該 contract 唯一的現行 canonical owner。**同一 contract 只能有一個 CURRENT。**
- `REFERENCE`：可提供背景、方法或 evidence，但不能覆蓋 CURRENT。
- `MIRROR`：只作相容入口／導覽；必須 `POINTER_ONLY` 指回 canonical owner，不得複製完整 current prose 後自行演化。
- `HISTORICAL`：保留日期化／已被取代的 evidence；不得進 current routing 或以「最高優先級／目前規則」語氣覆蓋 CURRENT。

若本表與某個 mirror/reference 的文字衝突，以 `CURRENT` 所指 canonical owner 為準；若 CURRENT owner 本身需要變更，必須在同一變更中更新本表、舊 owner 的角色與永久 guard，禁止先留下兩份 CURRENT 再「之後整理」。

## Machine-readable authority rows

<!-- WHD_AUTHORITY contract=phase6-dimension-semantics role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md -->
<!-- WHD_AUTHORITY contract=phase6-dimension-semantics role=MIRROR path=07_Phase6尺寸語意與標準截角母規則.md canonical=個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md -->

<!-- WHD_AUTHORITY contract=manufacturing-layer-classification role=CURRENT path=加工層分類與定義.md -->
<!-- WHD_AUTHORITY contract=manufacturing-layer-classification role=MIRROR path=標準基準檔格式.md canonical=加工層分類與定義.md -->

## T1 scope boundary

本輪只收斂已經證實的 dual-current / exact-duplicate authority：

1. Phase6 尺寸語意：AI Library `07_...` 為 CURRENT；repo root 同名檔降為 pointer-only MIRROR。
2. 加工層分類：`加工層分類與定義.md` 為 CURRENT；內容完全相同但名稱誤導的 `標準基準檔格式.md` 降為 pointer-only MIRROR。

README、AI_HANDOFF、handoff、舊 API snapshot、巨型 06 的 current/history sediment 由 T7/#180 負責；本文件不提前重寫那些 domain。

## T8 Combined Acceptance guard matrix

<!-- WHD_COMBINED_GUARD_MATRIX_V1 -->

下列 rows 只定義 **validation-only anti-drift coverage**，不得成為 production manufacturing authority；各 domain 的計算與規格 authority 仍只由上方 CURRENT owner 與其 canonical domain 文件負責。

<!-- WHD_COMBINED_GUARD requirement=R1 guard=tests/knowledge/test_knowledge_authority_contract.py -->
<!-- WHD_COMBINED_GUARD requirement=R1 guard=tests/knowledge/test_ae_engine_current_spec_contract.py -->
<!-- WHD_COMBINED_GUARD requirement=R1 guard=tests/knowledge/test_current_history_authority_contract.py -->
<!-- WHD_COMBINED_GUARD requirement=R2 guard=tests/test_issue175_dm7_navigation_authority_contract.py -->
<!-- WHD_COMBINED_GUARD requirement=R3 guard=tests/knowledge/test_skill_catalog_classification_contract.py -->
<!-- WHD_COMBINED_GUARD requirement=R3 guard=tests/knowledge/test_active_skill_runtime_contract.py -->
<!-- WHD_COMBINED_GUARD requirement=R4 guard=tests/knowledge/test_skill_registry_domain_reference_contract.py -->
<!-- WHD_COMBINED_GUARD requirement=R4 guard=tests/test_phase6_skill_preflight_gate.py -->
<!-- WHD_COMBINED_GUARD requirement=R5 guard=tests/knowledge/test_current_history_authority_contract.py -->

T8 Combined Acceptance 必須把 R1–R5 全部跑在同一個 tested head；若任一 listed guard 被刪除、改名或從 matrix 脫鉤，Combined guard 直接 fail closed。這個 matrix 不複製 domain 規則，只固定「哪一條永久 regression 對哪一個 requirement 負責」。

## Change contract

新增或搬移 authority 時，至少同時完成：

1. 先決定 contract id 與唯一 CURRENT owner。
2. 舊入口若仍需保留，只能降成 `REFERENCE` / `MIRROR` / `HISTORICAL`；MIRROR 必須 `POINTER_ONLY`。
3. 更新本 authority map。
4. 更新直接相關 AI Library / Skill / router（若有）。
5. 跑永久 authority contract guard，確認沒有雙 CURRENT 或 forked mirror。
6. 遠端反讀後才算 durable writeback 完成。
