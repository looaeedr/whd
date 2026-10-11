---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Deterministic repo migration 踩坑庫

## 舊 workspace-first 假設與現行 GitHub 權限的區分（HISTORICAL）

> **2026-10-11 現行權責提醒**：此文為 `REFERENCE` 事故庫，不能授予 DC／RC、本機 shell 或舊 `root-local-first` 施工權限；不得把舊 `WORKSPACE_DEFAULT` 當作每件 WHD 任務的強制入口。現行 `/派工`、當次明確 `/接手`、治理直送 X 及 `localX`→X 發布分流，均以正式 X `AGENTS.md`／CURRENT Skills 和 GitHub exact HEAD readback 為準。

**當時的工作區規則（HISTORICAL／SUPERSEDED）**：Drive/shared-zero 已退役；舊流程曾要求 executor-local workspace、fresh `cleanup/2d-3d-sync` baseline、exact-tested-diff delivery。這是舊事故背景，不得重建 `WORKSPACE_DEFAULT` 或把使用者本機當預設施工地點。

## Validator 不是 authority

Migration 的 desired state 必須來自已釘住 SHA 的 authoritative matrix/registry。Validator 只能判定結果是否符合 authority；不得把 validator 的 expected value、錯誤訊息、snapshot 或測試資料反向灌回 migration，否則 validation 會偷變成第二套 authority。

固定防錯：先讀 authority、列完整 governed scope、再產生 mapping；遇到 duplicate mapping、missing mapping、unknown role、nonexistent target 一律 fail closed，不靠猜測補值。

## Idempotence 不能只看「第二次也 PASS」

相同 repository state、**same authority input** 下做 **second execution**，必須得到 **zero diff**。若第二次還會重排、重寫 metadata、加入時間戳、改換行或改內容，即使 validator PASS 也不是 deterministic migration。

需要保留原資料時，依契約做 byte-for-byte 驗證；不要用「看起來一樣」代替。

## Scope inventory 先於 mutation

如果邊掃邊改，就無法證明 governed inventory 完整，也容易漏掉 role/path。先固定 inventory count 與 mapping，再一次套用；任何 changed-file set 超出計畫都由 drift audit 擋下。

## T6 實際踩坑：strict FAIL 不能反推 authority（HISTORICAL／已驗收）

#252 第一次 full regression 出現 4 個 FAIL 時，根因是 pre-T6 stale test contract / legacy marker，而不是 strict metadata authority 錯誤。正確處理方式是回查 frozen T1 matrix + #255 resolution overlay，證明舊測試已 stale 後只更新測試；禁止為了讓測試變綠而改 authority metadata。

T6 accepted evidence：migrated HEAD `2ef002cc6cc9476fc36eccbbe6b8b64acda6a777`，governed/mapped `398/398`，second pass `CHANGED_COUNT=0`，focused `29 PASS`，full `tests/knowledge` `102 PASS / 0 FAIL`，remote run `34905919429` / job `104182413876`，scope drift `0`。

**當時 T7 的限制（HISTORICAL）**：當次 accepted strict-mode state 保留 T6 的 frozen metadata／matrix；不能憑這句話限制今日合法更新的 CURRENT 權威或新增另一個 gate。

## T8 當次 Combined Acceptance 必須驗同一 tested HEAD（HISTORICAL）

#235 的 combined acceptance 固定同時驗：R1–R7 permanent governance、完整 `tests/knowledge`、durable Skill/AI readback、`config.ini`、`基準檔/**` byte manifest，以及 working-tree clean。不可把不同 branch／不同 run 的綠燈拼成 Combined Acceptance。

第一輪 combined run `34907199320` / job `104186513540` 證明 accepted T7 head 上：permanent governance `GREEN governed=398`、`tests/knowledge` `107 PASS / 0 FAIL`、durable readback GREEN、`config.ini` SHA256 `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67` 不變、protected `基準檔/**` 共 `24` files manifest 不變、working tree clean。

**當時的 T8 final acceptance（HISTORICAL）**：該次 durable writeback 要求以 final exact HEAD 重跑 Combined Acceptance，第一輪 run 僅是 pre-write 證據。這不代表今日任務須重新執行 T8／舊 combined workflow；目前驗收依當次適用 CI 與 GitHub 回讀。

## T9 當次 Production Integration：drift reconcile 與 non-force（HISTORICAL）

#236 refetch production 時，`cleanup/2d-3d-sync @ 591a7127e09f8ab537e6de4ca84d5ec8c148c237` 與 #225 work-order T8 lineage 發生預期 divergence。production-only 淨變更來自已完成的 #256 execution-claim hard gate；禁止 force 覆蓋，也禁止直接拿 production 舊版 `派工/SKILL.md` 覆掉 T6 metadata-aware Skill。

正確處理是：建立 two-parent reconciliation，保留 T8 lineage tree、補回 #256 durable files；對 post-T6 新增 pitfall 補上已接受的 `REFERENCE / pitfall-ledger / WHD_DOC_META_V1` metadata；保持 frozen T6 matrix/overlay 為原本 `398` 路徑歷史 authority，而第 `399` 份 post-T6 governed document 由 current strict/permanent governance 驗證，不回寫 frozen authority；最後恢復 #256 `EXECUTION_CLAIM_PREWRITE_HARD_GATE` 到 current metadata-aware `派工` Skill。

verified reconciliation candidate `11b359dbab1936ab88d306557e3de12a9459f31a` 在 run `34908327071` / job `104189997798` 通過：production ancestry PASS、permanent governance `GREEN governed=399`、`tests/knowledge` `107 PASS / 0 FAIL`、#256 execution-claim guard `14 PASS / 0 FAIL`、config invariant PASS、protected `基準檔/**` 24 files invariant PASS、clean tree。

production 隨後以 **non-force fast-forward** 整合到 `11b359dbab1936ab88d306557e3de12a9459f31a`。post-integration exact-production run `34908535340` / job `104190648538` 先證明 remote `cleanup/2d-3d-sync` 正是該 SHA，再 detached checkout 同一 SHA 驗收：permanent governance `GREEN governed=399`、`tests/knowledge` `107 PASS / 0 FAIL`、#256 guard `14 PASS / 0 FAIL`、durable readback GREEN、`config.ini` SHA256 `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67` invariant、protected `基準檔/**` 24 files invariant、working tree clean。

本段 final production readback 本身也是 required durable output，因此它的 commit 必須再以 exact-head acceptance 驗證，並只可對 production 做下一次 non-force fast-forward；不得把前一輪 `11b359db...` 的 GREEN 證據冒充成包含本段 writeback 的 final production 證據。

## 不跨越 domain authority

這個流程不能拿來修 production geometry、DXF 或 manufacturing truth。若 migration 發現 domain truth 有問題，停止並交給該 domain 的 authority/Skill；不要藉 migration 順手改製造資料。
