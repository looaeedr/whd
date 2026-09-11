---
name: issue-closure-gate
description: Use when GitHub ticketed work reaches QA acceptance, branch/PR merge, production integration, child/parent issue closure, Final Combined acceptance, or when reporting a ticket/Master as complete.
---

# GitHub Issue Closure Gate

## 核心原則

**合併不等於關單。** `integration != completion`。

`target integration 只是 code-state gate`；GitHub ticket / parent / Master 是否完成，是另一個 process-state gate。只要任何 required `open issue` 尚未依 contract 收尾，就不得回報正式完成。

若 code 已進 production target，但工單鏈仍未終態，固定回報：

`code integrated, process incomplete`

不得把 target 已整合當成工單完成，也不得因為 PR/branch 已 merge 就假設 GitHub 會自動關票。

## GitHub completion gate

任何 GitHub ticketed work 在宣告完成前，都必須先建立並反讀本輪 active issue chain：

1. `leaf/current ticket`
2. `closing/acceptance ticket`
3. `closing/Final Combined ticket`（若有）
4. `Master/parent`
5. 所有 required child / dependency ticket

必須**逐票反讀** canonical issue state，不用聊天記憶、branch 名稱、commit message 或 PR merge 狀態代替。

正常完成票的 terminal state 必須同時看到：

- `state=closed`
- `state_reason=completed`

除非該票自己的 authority 明確允許 `duplicate` / `not_planned`，否則其他 state reason 不可當作完成證據。

## 關單順序

關單固定**依 dependency 順序**由葉節點往上：

### 1. leaf/current ticket

只有本票 acceptance criteria、terminal QA、必要 AI Library writeback、workflow cleanup / drift audit（若適用）都完成，並把 evidence 回寫 issue 後，才可 close。

Close 後立刻遠端反讀，確認 `state=closed` + `state_reason=completed`。

### 2. closing/Final Combined ticket

只有它依賴的所有 required child 都已 CLOSED/completed，且自己的 Combined Acceptance / integration / cleanup / drift audit / completion evidence 全部完成，才可 close。

不得因 target 已 fast-forward / merge 就跳過這張 closing ticket。

### 3. Master/parent

只有**所有 required child**、所有 closing/acceptance ticket、closing/Final Combined ticket（若有）都**全部 CLOSED/completed**，才可 close Master/parent。

任何 required child 仍 open 時，**不得宣告 Master 完成**，也不得只手動關 Master 來掩蓋缺失流程。

Master close 後必須再次反讀 Master + required children，確認整條鏈 terminal。

## Issue Closure owner

拆工單時必須指定明確的 `Issue Closure owner`。

- closing/acceptance ticket 負責逐票關單與 terminal readback。
- 有 Final Combined ticket 時，Final Combined ticket 預設同時是 chain closure owner，除非 breakdown 明確指定其他 owner。
- 不得寫成「大家負責」或依賴 GitHub 自動 close。

Issue Closure owner 的責任不是只 merge code，而是把 acceptance evidence、issue state 與 parent/child chain 收到一致。

## 宣告完成的硬閘門

在對使用者說下列語意前：

- 「正式完成」
- 「全部完成」
- 「已關單」
- 「Master 完成」
- 「這一段完成」

必須重新讀 GitHub，至少確認：

- target before/after HEAD（若有 integration）
- tested head / final accepted head
- terminal run id + PASS/FAIL counts（若有 QA）
- 每張 required child 的 issue number + state + state_reason
- closing ticket state + state_reason
- Master/parent state + state_reason
- temporary QA workflow cleanup / tested→cleaned drift audit（若該工單要求）

只要其中任一 required issue 還 open，輸出只能是 `code integrated, process incomplete` 或等價的精確狀態，不得回報正式完成。

## 禁止的捷徑

- PR merged → 當成 issue completed：禁止。
- target fast-forward → 當成 Master completed：禁止。
- Combined QA GREEN → 直接關 Master、跳過 T5/T6/closing ticket：禁止。
- Issue body 有 `#child` / `depends on` → 假設 dependency 已完成：禁止，必須逐票反讀。
- GitHub autoclose keyword 沒有實際 readback → 不算 evidence。
- code 已進 target 後發現票還 open → 不准改口說「其實已完成」；繼續把 process 收完。

## 快速檢查

- [ ] 已辨識 active issue chain。
- [ ] 已指定 `Issue Closure owner`。
- [ ] leaf/current ticket evidence 已回寫並 CLOSED/completed。
- [ ] closing/Final Combined ticket（若有）已在 children terminal 後 CLOSED/completed。
- [ ] Master/parent 只在所有 required child terminal 後關閉。
- [ ] 每次 close 後都有 remote readback。
- [ ] target integration 與 issue closure 分開判定。
- [ ] 沒有 open required issue 時才宣告正式完成。
