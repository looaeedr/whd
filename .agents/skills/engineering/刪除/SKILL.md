---
name: 刪除
description: 處理 WHD/Google Drive/repository 工作區的檔案或資料夾刪除、清空 active 0、移出 active scope，以及 provider 不支援 delete 時的封存 fallback。使用者說「刪除」「刪掉」「清除」「清掉」「清空」「移除 staging/0」時使用；必須區分真正實體刪除與 archive/move，並以 readback 證明結果。
whd_doc_role: CURRENT
whd_contract: deletion-lifecycle-v1
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 刪除

把「刪除」當成一個有可驗證 postcondition 的 lifecycle 操作，而不是把狀態字串改成 `EMPTY` 就算完成。

## 0. Authority 與遠端邊界

1. 使用者本輪明確指示最高。
2. Drive/shared-zero 已退役；有無 historical drift 都固定 WORKSPACE_DEFAULT，不得啟動 shared-zero fallback、merge/freeze 或 /推推 前置。 同一 exact user-authorized task 可沿 WORKSPACE_DELIVERY 完成 delivery/readback。
3. Google Drive / Library / connector 只是 transport；transport 顯示「不支援 delete」時，不得把 move/archive 冒充 delete。
4. 任何 destructive action 前先 fresh-read exact target identity：canonical path、file/folder kind、provider id、parent、必要時 hash/size/modified time。

## 1. 先分類「刪除」的真實語意

每次操作只允許下列其中一種結果語意：

- `PHYSICALLY_DELETED`：provider 已真正刪除/移入 provider 的 trash，fresh readback 證明原 target 不再存在於其原 parent/namespace。
- `MOVED_OUT_OF_ACTIVE_SCOPE`：target 仍存在，但已離開 active namespace；這是 scope cleanup，不是實體刪除。
- `ARCHIVED_NOT_DELETED`：target 被移到 history/archive/quarantine；資料仍存在。
- `DELETE_UNSUPPORTED`：目前 transport 沒有合法 delete 能力，而且沒有使用者接受的等價 scope-cleanup 路徑。
- `DELETE_FAILED`：有 delete 能力但 mutation/readback 失敗。

**不得把 archive/move 說成 delete**；最終回報必須使用上面 exact 語意。

## 2. PRE_DELETE_CAPABILITY_AND_IDENTITY_HARD_GATE_V1

刪除前固定：

```text
TARGET_PATH_RESOLVED
→ TARGET_IDENTITY_FRESH
→ PROVIDER_CAPABILITY_DETECTED
→ DELETE_SEMANTICS_SELECTED
→ MUTATION
→ READBACK_POSTCONDITION
```

硬規則：

- 不從聊天記憶、舊 id、同名搜尋結果直接刪；exact parent-chain 要先證明。
- capability detection 必須先枚舉 provider 原生刪除能力（例如 Google Drive `delete_file`），再檢查 Library/其他 transport；不得因其中一條 transport 回 unsupported 就推論 provider 整體不能刪。
- `files.manage_library delete`、Drive connector、OS/filesystem 各自是否支援 delete，要以本回合實際 tool contract/result 判定。
- API 回 `unsupported_operation` / 404 / permission denied 時，不得改口說「已清除」。
- destructive target 若是資料夾，先確認是否要 recursive；不得把「刪資料夾」偷偷擴張成不受限的 parent tree 刪除。

## 3. Protected targets

下列 path 不得因模糊的「清掉」「整理一下」直接刪除：

- `/Google Drive/WHD` repo root；
- `.git/`、`.agents/`、`AGENTS.md`；
- `.unpushed/` 根與 lane 根；
- canonical contract / registry / Source of Truth；
- 使用者未明確包含在 scope 的其他 worker / lane / issue 資料。

若使用者明確要求刪 protected target，仍要 fresh-read CURRENT governance 與 exact scope，再依可用 transport 執行；不得靠 inferred intent 擴大範圍。

## 4. Repository tracked path 的刪除

若刪的是正式 repository path，而不是 staging/archive：

1. 在 executor-local repo workspace 以 fresh `cleanup/2d-3d-sync` baseline 確認 exact tracked path / identity。
2. 在 workspace 建立 exact delete diff，執行適用 tests / validators，並 fresh-read target/touched-path drift。
3. 普通 route=`WORKSPACE_DEFAULT`：tested exact delete diff → delivery branch → push/PR/CI → merge/readback → FINALIZE。
4. 使用者已明確要求 exact repository-content delete task 時，可沿同 scope `WORKSPACE_DELIVERY` 完成 remote QA 與 owning-Issue finalization，不得到 push/PR/close 再重問相同授權。
5. Drive/shared-zero 已退役；有無 historical drift 都固定 WORKSPACE_DEFAULT，不得啟動 shared-zero fallback、merge/freeze 或 /推推 前置。 同一 exact user-authorized task 可沿 WORKSPACE_DELIVERY 完成 delivery/readback。
6. production target仍禁止直接 patch；target advancement只走正常 PR/merge/readback。

**Missing Drive mount / missing shared-0 不是普通 tracked-path刪除的 blocker。** 不得因歷史 shared-0 流程把 Codex 拉回固定 `/Google Drive/WHD`。

## 5. ACTIVE_ZERO_PHYSICAL_CLEANUP_HARD_GATE_V1 — HISTORICAL DATA ONLY

本節只適用使用者明確要求的歷史資料清理，不是 repository-content startup、delivery、FINALIZE 或 closure 前置。

`.unpushed/docs/0` / `.unpushed/body/0` 的「清乾淨」必須同時滿足**狀態**與**實際 active namespace**。

**只改 `CURRENT.json` / manifest 為 `EMPTY` 不算清乾淨**。

delivery/readback 後：

1. 先依 delivery receipt 判斷哪些 path 已交付、哪些 path 必須 preserve；
2. 只處理已交付且目前 hash/identity 沒有後續變更的 staging；
3. fresh-list active `0`；舊 `files/` staging tree、舊 worker payload、舊 conflict staging 不得繼續留在 active `0` 冒充待推內容；
4. 歷史 manifest / receipt 若需要保留，應留在明確 history/audit 位置，或只保留 active contract 明確要求的最小檔案；
5. cleanup 後再 fresh-list active `0`，以實際 namespace readback 作完成證據。

### Provider 不支援 child delete 時

若 connector 能列出 staging，但對 child delete/move 回 `unsupported_operation` / `NOT_FOUND`，而 parent folder 本身可 move/rename：

```text
舊 active 0
→ rename/move 成 history snapshot
→ 重新建立乾淨的 active `0`
→ 只回填 CURRENT + current empty manifest + delivery receipt
→ fresh-list 驗 active 0 exact allowlist
```

此結果分類為 `MOVED_OUT_OF_ACTIVE_SCOPE` / `ARCHIVED_NOT_DELETED`；**不是** `PHYSICALLY_DELETED`。

若連 parent move/rename 都不可用，回 `DELETE_UNSUPPORTED`，不得只把 pointer 改 EMPTY 後宣稱清除完成。

## 6. Exact allowlist readback

當任務是「清空 active 0」時，若 delivery 已完成且沒有 preserved paths，active `0` 預期只保留 CURRENT contract 所需最小 evidence，例如：

```text
CURRENT.json
manifest.<current>.empty.json
delivery-receipt.<delivered>.json
```

若 fresh-list 還看到舊 `files/`、superseded CURRENT、舊 conflict/staging，而且這些不是 CURRENT 明確要求的 active evidence，cleanup 不得回報完成。

## 7. Result evidence

每次刪除/清理至少回傳：

- requested_semantics；
- target canonical path + exact id/kind；
- provider / capability；
- mutation 實際採用 delete / trash / move / archive / parent rollover 哪一種；
- readback postcondition；
- final classification：`PHYSICALLY_DELETED | MOVED_OUT_OF_ACTIVE_SCOPE | ARCHIVED_NOT_DELETED | DELETE_UNSUPPORTED | DELETE_FAILED`；
- preserved paths / objects（若有）。

沒有 readback，不得宣告成功。

## 8. 常見禁止事項

- 把 `state=EMPTY` 當成資料夾已空。
- API 不支援 delete 後，仍回「已刪除」。
- 只看 `files/` manifest 不 fresh-list active folder。
- 為了刪 staging 去碰 repository 真實檔案。
- 清 docs lane 時順手清 body lane。
- archive 後不說 archive location，讓使用者以為資料消失。
- 以舊 Drive id / alias 404 猜測「檔案已不存在」。404 只能證明該 transport/id 無法解析，不能單獨證明 logical target 已刪除。

## 9. 完成條件

只有下列其一成立才可結束：

1. `PHYSICALLY_DELETED` 且 readback 證明 target 已不存在；
2. 使用者要的是 active cleanup，且 `MOVED_OUT_OF_ACTIVE_SCOPE` / `ARCHIVED_NOT_DELETED` 已使 active namespace 達 exact postcondition；
3. `DELETE_UNSUPPORTED` / `DELETE_FAILED`，並精確列出哪一層 capability/identity/readback 阻塞。

不得用「工具看起來成功」「CURRENT 已 EMPTY」「manifest 沒 entries」代替實際 namespace readback。
