---
whd_doc_role: REFERENCE
whd_contract: scheduler-prompt-authoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Scheduler Prompt Authoring / 排程「有醒但沒施工」踩坑

## SCHEDULER_PROMPT_AUTHORING_PITFALL_V1

### 事故

2026-09-24 的 WHD recurring lanes 出現一組可重複事故：

1. scheduler invocation 確實被喚醒，也留下 heartbeat，但沒有接著完成可執行 next_action，形成 **heartbeat-only**。
2. runtime 拿到 Remote Guard GREEN 後，在真正 consume / mutation / readback 前就結束 invocation，留下 **unconsumed GREEN**。
3. scheduler 把「自己其實能做的 run discovery / poll / readback」寫成 `BLOCKED`，再利用 BLOCKED 可結束 turn 的語意提前退出。
4. 為了縮短／重寫 automation prompt，authoring 過程曾把「fresh-read《遠端執行守門》」顯式 hard gate 刪掉，只剩《派工》，造成 transport / consume authority 依賴隱含記憶。
5. update API 回 SUCCESS 後若沒有 **post-update readback**，無法立即發現 schedule、lane identity、enabled 或 hard-gate marker 被誤改。

### 根因

- 把「prompt 有一句不能停」誤當成 machine enforcement。
- 把 heartbeat / Guard receipt / QA PASS 誤當 substantive progress。
- 把 `BLOCKED` 當成 turn-exit escape hatch，而不是 genuine external wait。
- 修改 prompt 使用 replacement semantics，卻沒有 baseline + invariant diff；刪一段文字就可能刪掉整個 Skill authority。
- 沒有把 schedule、durable lane owner、entrypoint identity 分開管理。

### 永久規則

1. 建立／修改 WHD scheduler prompt 必須使用 `.agents/skills/engineering/寫排程/SKILL.md`。
2. authoring 前先 baseline-read automation 的 id/title/schedule/timing_mode/enabled/full prompt/updated_at/last_run_time。
3. 施工型 scheduler prompt 必須顯式保留 **派工 + 遠端執行守門**；不可把後者假設成前者的隱含內容。
4. 有 exact-valid unconsumed GREEN 時，下一 wake first recovery = validate → consume → exact mutation → readback；heartbeat 不得搶在前面成為假終點。
5. heartbeat / progress / CHECKPOINT / Guard GREEN / QA PASS 都不是 substantive completion。
6. `BLOCKED` 只給真正 runtime 無法自行排除的 external authority/capability/dependency blocker。Discovery、poll、read、Guard、mutation、readback、reconcile 都不是 blocker。
7. exact remote run 存在時鎖 `run_id + head_sha` 到 terminal，不 duplicate dispatch。
8. 正常 return 前要實際經過 **machine turn-exit** authority；文字說「可以結束」沒有證明力。
9. 沒有 matching `WHD_SCHEDULER_RUNTIME_END_V1` 的 invocation 不得視為正常完成。
10. automation update 後必須做 post-update readback；驗 title/schedule/timing_mode/enabled/lane owner/entrypoint 與 required hard gates。
11. 同一 logical lane 的多 entrypoint 共用 owner是 mutex；不同 owner才可能真平行，但仍受 shared claim / dependency / integration scope 約束。
12. 修改一個 prompt 發現 reusable authoring defect 時，要搜尋 sibling / parallel lanes 是否有同型缺口，不能只補眼前入口。

### Documentation != enforcement

`寫排程` Skill 能避免 authoring 時刪錯 contract，但不能保證平台 runtime 永遠不會 hard-cut，也不能取代 executable continuity controller。

真正判斷必須區分：

- prompt contract：下一個 runtime 應該怎麼做；
- Remote Guard：這次 mutation 是否獲授權；
- continuity controller：目前 workflow state 是否允許 turn exit / finalization；
- durable GitHub evidence：上一輪實際做到哪裡。

因此禁止說：「prompt 補好了，所以排程不會再停。」

正確說法只能是：prompt authoring contract 已補；是否持續施工要看下一輪的 durable mutation、exact run、turn-exit proof 與 END readback。
