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
2. WHD repository-content 工作固定遵守 CURRENT `root-local-first`：tracked-path 刪除只走 `WORKSPACE_DEFAULT` executor-local workspace。Drive/shared-zero historical drift 不得改變 route；同一 exact user-authorized task 可沿 `WORKSPACE_DELIVERY` 完成 delivery/readback，不得強迫先有 `/推推` 或 Drive mount。
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

- `/Google Drive/WHD/WHD_MIRROR/CURRENT` 等 backup/mirror storage（不是 repo root）；
- `.git/`、`.agents/`、`AGENTS.md`；
- 歷史 `.unpushed/` evidence / lane 資料（若仍存在，只能依明確 cleanup scope 處理）；
- canonical contract / registry / Source of Truth；
- 使用者未明確包含在 scope 的其他 worker / lane / issue 資料。

若使用者明確要求刪 protected target，仍要 fresh-read CURRENT governance 與 exact scope，再依可用 transport 執行；不得靠 inferred intent 擴大範圍。

## 4. Repository tracked path 的刪除

若刪的是正式 repository path，而不是 staging/archive：

1. 在 executor-local repo workspace 以 fresh `cleanup/2d-3d-sync` baseline 確認 exact tracked path / identity。
2. 在 workspace 建立 exact delete diff，執行適用 tests / validators，並 fresh-read target/touched-path drift。
3. 普通 route=`WORKSPACE_DEFAULT`：tested exact delete diff → delivery branch → push/PR/CI → merge/readback → FINALIZE。
4. 使用者已明確要求 exact repository-content delete task 時，可沿同 scope `WORKSPACE_DELIVERY` 完成 remote QA 與 owning-Issue finalization，不得到 push/PR/close 再重問相同授權。
5. shared `.unpushed/{docs|body}/0` / `SHARED_ZERO_FALLBACK` 已退出 CURRENT routing；historical staging 若需清理，只能作資料 cleanup，不得建立 delete marker、latest-0 merge/freeze 或 `/推推` fallback route。
6. production target仍禁止直接 patch；target advancement只走正常 PR/merge/readback。

**Missing Drive mount / missing shared-0 不是普通 tracked-path刪除的 blocker。** 不得因歷史 shared-0 流程把 Codex 拉回固定 `/Google Drive/WHD`。

## 5. HISTORICAL_SHARED_ZERO_CLEANUP_ONLY

`.unpushed/docs/0` / `.unpushed/body/0` 已不是 CURRENT authoring/delivery namespace。若使用者明確要求清理殘留 historical staging，這是**資料清理**，不是 repository-content routing、施工或 finalization gate。

- 不得因 historical staging 存在而切換 `WORKSPACE_DEFAULT`；
- 不得把 `CURRENT.json` / manifest / worker payload 當 CURRENT execution authority；
- 不得因 provider 不支援 child delete 而重建新的 active `0`；
- 能安全刪除／移出 historical scope 就做 exact cleanup；不能則回 `DELETE_UNSUPPORTED`；
- cleanup readback 只證明資料清理結果，不得影響 Git merge/Flow v2 DONE/Issue closure。

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
