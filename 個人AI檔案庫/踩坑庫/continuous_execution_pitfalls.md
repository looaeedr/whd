# 長流程持續執行 / 停工點踩坑規則

## 事故模式：把派工完成當成停工點

WHD 曾發生：Master 與子工單已建立、第一張可執行子工單也已明確，但 AI 以「派工完成」作為回覆終點，把後續實作留給使用者再輸入「繼續」。這是流程缺陷，不是正常 checkpoint。

## 永久規則

- **進度回報不是工作終點。** branch created、issue created、commit/push、QA started、run_id acquired、focused PASS、下一步明確，都只是中間態。
- 只要**存在可自主執行的下一步**，且沒有真正 blocker / Runtime interruption，就必須在同一工作流程繼續執行；不得輸出 terminal/final 狀態把控制權交回使用者。
- **使用者不是續跑 scheduler。** 不得依賴使用者再輸入「繼續」「輪」「跑」「continue」「poll」才讓既有非終態工作前進。
- Gate RED / preflight FAIL 是 fail-closed boundary：禁止越過受保護階段，但仍要繼續完成 Gate 所要求的 evidence、readback 或修復，直到 GREEN 或出現真正 blocker。
- Test / QA FAIL 可自行診斷時要進 recovery：evidence → root cause → minimal fix → validation → retry；FAIL 本身不是停工理由。
- 只有 COMPLETE、真正需要產品決策/權限/不可推導資料的 BLOCKED，或平台實際 Runtime/tool interruption，才允許離開目前工作鏈。
- Runtime 被硬切時要留下 durable checkpoint；下一回合先驗 drift，再從 next exact action 續跑，不重新要求使用者交代已知上下文。

## CHECKPOINT 可見層事故

WHD 曾出現 durable checkpoint / resume contract 已存在，但只有內部流程責任、沒有 user-visible gate；結果長流程中的一般進度回報逐漸取代 CHECKPOINT，使用者長時間看不到可恢復狀態。這不是「checkpoint 不需要了」，而是可見層漏規則。

永久規則：

- durable checkpoint 與 user-visible CHECKPOINT 是同一狀態的兩個責任層；只做內部 durable state 不算完成 checkpoint 呈現責任。
- system hard-cut 前與重要 execution state transition 必須刷新固定標題 `CHECKPOINT`；一般 progress update 不得冒充或取代它。
- 可見 CHECKPOINT 仍是 non-terminal observation / recovery surface；只要 next action 可自主執行，就必須在顯示 CHECKPOINT 後繼續，不得把 CHECKPOINT 變成停工點。
- `.agents/skills/engineering/執行開發任務/SKILL.md` 的 `USER_VISIBLE_CHECKPOINT_GATE` 是唯一 canonical CHECKPOINT 呈現 authority；不得在其他 Skill 建第二套欄位、refresh 或 execution state machine。
- 所有可獨立進入長流程的入口目前至少包含 `.agents/skills/engineering/派工/SKILL.md`、`.agents/skills/engineering/monitoring-remote-qa/SKILL.md`、`.agents/skills/engineering/issue-closure-gate/SKILL.md`，都必須以 `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE` 強制 bridge 回 canonical gate；入口 Skill 的 progress/polling/closure domain responsibility 不取代 CHECKPOINT 呈現責任。
- machine guard 由 canonical `USER_VISIBLE_CHECKPOINT_GATE`、三個入口的 `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE` 與 `tests/process/test_checkpoint_resume_contract.py` 共同鎖定。

## Remote QA 邊界

Remote QA 的 polling 細節與 `REMOTE_QA_ACTIVE_LOCK` 仍以 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` 為唯一 authority；本規則不建立第二套 polling state machine。

## 對應 Machine Guard

- `.agents/skills/engineering/執行開發任務/SKILL.md` → `NONTERMINAL_NEXT_ACTION_GATE` + canonical `USER_VISIBLE_CHECKPOINT_GATE`
- `.agents/skills/engineering/派工/SKILL.md` → PM → Implementer 同工作流程轉移規則 + `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE`
- `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` → `REMOTE_QA_ACTIVE_LOCK` + `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE`
- `.agents/skills/engineering/issue-closure-gate/SKILL.md` → closure gate + `USER_VISIBLE_CHECKPOINT_GATE_BRIDGE`
- `tests/process/test_checkpoint_resume_contract.py`
- `tests/process/test_continuous_execution_durable_contract.py`
