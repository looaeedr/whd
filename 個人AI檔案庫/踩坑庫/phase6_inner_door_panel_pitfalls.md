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
