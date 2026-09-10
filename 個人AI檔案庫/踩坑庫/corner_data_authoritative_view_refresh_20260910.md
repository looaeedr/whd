# 截角資料：authoritative state 已更新但 View 仍可能停舊畫面（2026-09-10）

## 問題

#99 T6 驗證時發現：Fold Designer「截角資料」的新 2D View 雖然只讀 authoritative `PartRenderData`，但 Main GUI 的 authoritative external sync 套用完成後，若沒有顯式刷新目前可見的新 View，畫面仍可能暫時顯示上一版資料。

## 根因

`_phase6_apply_external_sync()` 原本只做 external settings apply 後 return；新「截角資料」View 的刷新入口只有進入 mode、選板件、canvas resize 等 UI 事件。這代表「資料 SSOT 正確」與「可見 View freshness 正確」是兩個不同 invariant。

## 正確規則

唯一同步路徑仍是：

`authoritative mutation/commit -> invalidate/apply -> visible views refresh`

禁止 legacy widget 與新 widget 互抄值。

若 `corner_data` View 當下可見：每個新的 authoritative revision 套用完成後刷新一次；hidden View 不主動刷；replayed/stale revision 不刷；refresh/recreate 只能重新讀 authoritative projection/render data，不得寫回 manufacturing state。

## TDD 證據

- diagnostic run `34482582019`：缺少 refresh seam，預期 RED。
- regression RED run `34482740641`：`2 failed / 2 passed / 1 warning`；可見 refresh 與 repeated revisions 兩條紅，hidden/replayed 兩條綠。
- focused GREEN run `34482885812`：`30 passed / 1 skipped`，source guard PASS。
- T6 Final Acceptance `34483025331`：`63 passed / 59 skipped / 1 warning`；`T6_AUTHORITATIVE_REFRESH=PASS`、`T6_NO_WIDGET_TO_WIDGET_SYNC=PASS`、`T6_VIEW_RECREATE_STATE_MUTATION_GUARD=PASS`；`config.ini` 前後 SHA256 同為 `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`。

## 防錯檢查

驗 dual-view parity 時不能只比 final geometry / save-reload / DXF；必須另外驗：

1. visible View 在 authoritative commit 後是否真的刷新；
2. hidden View 是否避免多餘刷新；
3. replayed revision 是否 no-op；
4. repeated revisions 是否一個 commit 對應一次 refresh；
5. View refresh/recreate 是否零 manufacturing state mutation。
