---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Deterministic repo migration 踩坑庫

## Validator 不是 authority

Migration 的 desired state 必須來自已釘住 SHA 的 authoritative matrix/registry。Validator 只能判定結果是否符合 authority；不得把 validator 的 expected value、錯誤訊息、snapshot 或測試資料反向灌回 migration，否則 validation 會偷變成第二套 authority。

固定防錯：先讀 authority、列完整 governed scope、再產生 mapping；遇到 duplicate mapping、missing mapping、unknown role、nonexistent target 一律 fail closed，不靠猜測補值。

## Idempotence 不能只看「第二次也 PASS」

相同 repository state、**same authority input** 下做 **second execution**，必須得到 **zero diff**。若第二次還會重排、重寫 metadata、加入時間戳、改換行或改內容，即使 validator PASS 也不是 deterministic migration。

需要保留原資料時，依契約做 byte-for-byte 驗證；不要用「看起來一樣」代替。

## Scope inventory 先於 mutation

如果邊掃邊改，就無法證明 governed inventory 完整，也容易漏掉 role/path。先固定 inventory count 與 mapping，再一次套用；任何 changed-file set 超出計畫都由 drift audit 擋下。

## T6 實際踩坑：strict FAIL 不能反推 authority

#252 第一次 full regression 出現 4 個 FAIL 時，根因是 pre-T6 stale test contract / legacy marker，而不是 strict metadata authority 錯誤。正確處理方式是回查 frozen T1 matrix + #255 resolution overlay，證明舊測試已 stale 後只更新測試；禁止為了讓測試變綠而改 authority metadata。

T6 accepted evidence：migrated HEAD `2ef002cc6cc9476fc36eccbbe6b8b64acda6a777`，governed/mapped `398/398`，second pass `CHANGED_COUNT=0`，focused `29 PASS`，full `tests/knowledge` `102 PASS / 0 FAIL`，remote run `34905919429` / job `104182413876`，scope drift `0`。

後續 T7 不得重新分類這批 metadata；只能在 accepted strict-mode state 上增加永久 governance guard。

## T8 Combined Acceptance 必須驗同一 tested HEAD

#235 的 combined acceptance 固定同時驗：R1–R7 permanent governance、完整 `tests/knowledge`、durable Skill/AI readback、`config.ini`、`基準檔/**` byte manifest，以及 working-tree clean。不可把不同 branch／不同 run 的綠燈拼成 Combined Acceptance。

第一輪 combined run `34907199320` / job `104186513540` 證明 accepted T7 head 上：permanent governance `GREEN governed=398`、`tests/knowledge` `107 PASS / 0 FAIL`、durable readback GREEN、`config.ini` SHA256 `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67` 不變、protected `基準檔/**` 共 `24` files manifest 不變、working tree clean。

T8 最終驗收仍必須在包含本 durable writeback 的 exact HEAD 重新跑同一 Combined Acceptance；第一輪 run 只能作 pre-write evidence，不能代替 final tested-head proof。

## T9 Production Integration：外部 drift 先 reconcile，再 non-force

#236 refetch production 時，`cleanup/2d-3d-sync @ 591a7127e09f8ab537e6de4ca84d5ec8c148c237` 與 #225 work-order T8 lineage 發生預期 divergence。production-only 淨變更來自已完成的 #256 execution-claim hard gate；禁止 force 覆蓋，也禁止直接拿 production 舊版 `派工/SKILL.md` 覆掉 T6 metadata-aware Skill。

正確處理是：建立 two-parent reconciliation，保留 T8 lineage tree、補回 #256 durable files；對 post-T6 新增 pitfall 補上已接受的 `REFERENCE / pitfall-ledger / WHD_DOC_META_V1` metadata；保持 frozen T6 matrix/overlay 為原本 `398` 路徑歷史 authority，而第 `399` 份 post-T6 governed document 由 current strict/permanent governance 驗證，不回寫 frozen authority；最後恢復 #256 `EXECUTION_CLAIM_PREWRITE_HARD_GATE` 到 current metadata-aware `派工` Skill。

verified reconciliation candidate `11b359dbab1936ab88d306557e3de12a9459f31a` 在 run `34908327071` / job `104189997798` 通過：production ancestry PASS、permanent governance `GREEN governed=399`、`tests/knowledge` `107 PASS / 0 FAIL`、#256 execution-claim guard `14 PASS / 0 FAIL`、config invariant PASS、protected `基準檔/**` 24 files invariant PASS、clean tree。

production 隨後以 **non-force fast-forward** 整合到 `11b359dbab1936ab88d306557e3de12a9459f31a`。post-integration exact-production run `34908535340` / job `104190648538` 先證明 remote `cleanup/2d-3d-sync` 正是該 SHA，再 detached checkout 同一 SHA 驗收：permanent governance `GREEN governed=399`、`tests/knowledge` `107 PASS / 0 FAIL`、#256 guard `14 PASS / 0 FAIL`、durable readback GREEN、`config.ini` SHA256 `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67` invariant、protected `基準檔/**` 24 files invariant、working tree clean。

本段 final production readback 本身也是 required durable output，因此它的 commit 必須再以 exact-head acceptance 驗證，並只可對 production 做下一次 non-force fast-forward；不得把前一輪 `11b359db...` 的 GREEN 證據冒充成包含本段 writeback 的 final production 證據。

## 不跨越 domain authority

這個流程不能拿來修 production geometry、DXF 或 manufacturing truth。若 migration 發現 domain truth 有問題，停止並交給該 domain 的 authority/Skill；不要藉 migration 順手改製造資料。
