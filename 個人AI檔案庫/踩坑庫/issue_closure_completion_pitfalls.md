# GitHub Issue Closure / Completion 踩坑規則

## 事故模式：把 code integrated 誤報成 process completed

WHD 曾發生以下錯誤流程：

1. production target 已完成合法 fast-forward / merge；
2. Combined / regression QA 也已 GREEN；
3. 但對應 T5 / T6 / Final Combined / Master Issue 仍是 OPEN；
4. AI 卻因「code 已在 target」直接對使用者宣告「正式完成」。

這是流程錯誤。**合併不等於關單；integration != completion。**

## 永久判定邊界

### Code-state gate

只回答：程式碼是否已進 authoritative target、target HEAD 是否正確、tested→cleaned drift 是否可接受。

常見證據：

- target before/after SHA；
- merge / fast-forward relationship；
- tested head / cleaned head；
- regression run / invariant；
- temporary QA workflow cleanup。

### Process-state gate

只回答：GitHub 工單鏈是否真的完成。

常見證據：

- leaf/current ticket `state=closed` + `state_reason=completed`；
- closing / Final Combined ticket CLOSED/completed；
- 所有 required child / dependency ticket terminal；
- Master/parent 最後才 CLOSED/completed；
- 每次 close 後 remote readback。

兩套 gate 都完成，才可說「正式完成／全部完成／已關單」。

若 code 已進 target 但仍有 required open issue，固定分類：

`code integrated, process incomplete`

## 關單順序

依 dependency 由葉節點往上：

`leaf/current ticket → closing/acceptance → Final Combined（若有） → Master/parent`

禁止：

- target fast-forward 後直接關 Master；
- Combined GREEN 後跳過仍 OPEN 的 T5/T6；
- 看到 PR merged 就假設 issue 自動 closed；
- 只靠 issue body 的 Depends on / child list 猜 dependency 已完成；
- 沒有遠端反讀就聲稱 `state_reason=completed`。

## 對應 Skill / Machine Guard

Canonical Skill：

`.agents/skills/engineering/issue-closure-gate/SKILL.md`

Machine guard：

`tests/test_issue_closure_completion_skill_contract.py`

Registry route：

`.agents/skills/skill_registry.json` → `issue-closure-gate`

任何派工收尾、Final Combined、production integration、關單、Master completion 都必須讓 Preflight 命中此 Skill，不得靠聊天記憶。
