---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Phase6 Inner-Door Panel Pitfalls

## 2026-09-06：有 inner-door 設定與框，不代表已有真實內門板件
- **錯誤現象**：authoritative state 已能表示每扇外門有／無內門，3D 也可能看到上/左/右框，但實際 workspace / FinalScene 沒有 inner-door panel physical piece。
- **根本原因**：把「enable/config state」與「derived physical sheet part」混成同一能力；只有 frame derivation，沒有 panel derivation + manufacturing render。
- **正確做法**：`inner_doors` list 只負責 presence/config；family resolver 從 Door finished face 推導 panel dimensions；manufacturing 產生 real CUTTING/material/unfolded blank；workspace 只同步其 profile。

## 同 namespace derived sync 不得分兩次做
- **錯誤現象**：先 `sync_derived_parts(namespace="inner_door:", frames)`，再用同一 namespace sync panels，第二次會把 frames 當 stale parts 刪掉；反過來亦同。
- **正確做法**：frames + panels 先合併成同一 `part_profiles`，再對 `inner_door:` namespace 原子 sync 一次。

## UI checkbox 不可成為第二份 truth
- **錯誤現象**：畫面勾選狀態和 Save/Reload/3D presence 分叉。
- **正確做法**：BooleanVar 只是 adapter；每次 rebuild 從 `receiving_inner_doors` 重建。checked item presence 才是 panel presence。

## Stable ID
- cell 0:0 => inner-door id `upper`; 0:1 => `lower`;其他 cell 使用 deterministic `c{col}r{row}`。
- physical panel id 固定 `inner_door:<id>:panel`；uncheck/recheck 不得換 id。

## 2026-10-28：多連候選版本已存兩孔，按「套用」卻只更新標籤

- **錯誤現象**：受電箱 NFB 原生開孔編輯器顯示第 2 孔、候選版本也保存兩顆，但 3D 實體內門組合體仍只有原孔。
- **根因**：從「即時」建立內門候選後，`editor_saved(... keep_live=True)` 未選中新版本；緊接著的「套用」走 `apply_live`，它只改已套用版本標籤，不寫入所選實體 Bay 的 NFBConfig 與 FinalScene。
- **修法**：新內門候選儲存後將版本選單指向剛保存的 `inner-door-vN`；物理套用仍須操作員主動按「套用」，由 `ReceivingSetBayAdapter.apply_inner_door_candidate_to_bays` 原子提交。若要建立下一個新版本，操作者可重新選「即時」。
- **舊檔陷阱**：兩顆實體 CSV NFB 可能已存於 `nfb_config.holes`，但舊 `inner_door_models` 只有一顆、`part_features` 為零。首次 GUI 載入須恢復完整 Set/Bay，編輯器只能從目前 Bay 的已提交型號**補回可取消草稿**。不可猜來源 X、不能以清單數量代替實體開孔。
- **驗收**：原生 GUI 完整走開啟舊檔 → 內門候選編輯兩孔 → 確定全部 → 高亮連套用 → `inner_door:upper:panel` 的 `material.interiors == 2` → Save As → GUI reopen 後仍 2。只驗 Canvas 或版本庫都不是組合體驗收。
- **測試誤區**：用 Set/Bay 舊檔卻呼叫「單只設定」會切 quantity 模式，是錯誤重現路線，不應因此改掉正確載入邏輯。

## 2026-10-28：上層內門雙擊 3D → 受電箱頁加入第二 NFB → 主頁確定全部仍只一孔

- **重現**：使用者 受電箱.p6fold 原本士林 2P400，3D 雙擊上層內門，加入士林 3P125SN；主 Hole Editor 草稿為 2 孔，但舊版 Confirm All 只有 workspace.stash_features，已提交物理 NFBConfig 仍 1、組合體內門實際只 1。
- **根因**：settings_mode=None 的 direct physical edit 未走多連候選 callback；不要再要求使用者改走「多連設定 → 候選 → 套用」繞開缺陷。
- **正確修法**：在 on_confirm_features 直達實體板件時，原子提交暫存的完整 CSV 型號、層數、Features 與 NFBConfig 至當前 Bay／Quantity 版本，然後更新物理投影。確定前仍是純草稿，取消應不變。
- **驗收**：同檔修正前 3D 1、修正後 3D 2；兩孔 ID 不同、原本 2P400 + 新增 3P125SN 都在 NFBConfig。不能把 Canvas 兩孔或 candidate version 兩筆當驗收。X 保留 UNVERIFIED_BASIS。
