---
name: issue-closure-gate
description: Use when GitHub ticketed work reaches QA acceptance, branch/PR merge, production integration, child/parent issue closure, Final Combined acceptance, or when reporting a ticket/Master as complete.
whd_doc_role: CURRENT
whd_contract: issue-closure
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# GitHub Issue Closure Gate

## EXECUTION_INTENT_ROUTING_V1_BRIDGE

Closure 只收斂**已授權 scope**，不建立新的 execution scope。

- `EXECUTE_TICKET`：把當前 ticket 收到 Issue close/readback + checkpoint CLOSED + claim RELEASED；單票 closure 完成不等於授權啟動 successor。
- `EXECUTE_CHAIN`：當 parent/master authority 與 checkpoint chain metadata 都允許時，closure 後可 handoff 下一 child。
- `SCHEDULER_LANE`：依 lane/chain authority可續 executable successor。
- `UPDATE_ONLY`：若只是 Issue body / automation / Skill / spec update，不得因 closure gate 或 open dependency 自動進 implementation chain。

因此後文 `NEXT_CHILD_EXECUTABLE` 的「立即進下一票」只適用已明確是 `EXECUTE_CHAIN` / `SCHEDULER_LANE` 的 execution scope；不得把單票 closure 或 update-only 誤升級成 chain execution。


## 必讀 Authority

執行本 Skill 時，同步讀取：

`個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md`

該檔記錄「code-state 與 process-state 不可混為一談」及 closure guard bypass 的事故模式與永久防錯規則。本 Skill 是執行契約，AI Library 是歷史踩坑與判斷背景；兩者不得只靠聊天記憶取代。

### USER_VISIBLE_CHECKPOINT_GATE_BRIDGE

本 Skill 一旦進入長流程、remote QA、recovery 或 closure chain，強制服從 `執行開發任務` 的 `USER_VISIBLE_CHECKPOINT_GATE`。該 gate 是 user-visible CHECKPOINT 的唯一 canonical authority；本 Skill 不複製其欄位／refresh state machine，且不得建立第二套 CHECKPOINT authority。

- 需要顯示 CHECKPOINT 時，沿用 canonical gate 的固定標題、欄位與重大 state transition refresh 規則。
- progress update 不得取代可見 CHECKPOINT；30 秒 observation 仍只屬 progress。
- non-terminal CHECKPOINT 不是停工點；顯示後仍依本 Skill 原有 owner contract 繼續 next action。
- 本 Skill 只保留自己的 domain responsibility；CHECKPOINT 呈現責任一律 bridge 回 canonical gate。

### EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE

本 Skill 的 closure 判定必須服從 `.agents/skills/engineering/executable-continuity-controller/SKILL.md` 與 `tools/continuity_controller.py`；GitHub issue state readback 與 executable continuity gate 兩者缺一不可。

`assert_finalizable` 只回答 checkpoint state 是否 terminal，**不是 closure authorization**。在 close leaf / closing ticket / Final Combined / Master，或對使用者輸出「正式完成／全部完成／已關單」前，必須使用 `OWNING_FINALIZATION_GUARD_V2`：

1. fresh 取得目前 owning issue/workflow、owning branch、owning HEAD SHA；
2. 載入目前 owning workflow 的 durable checkpoint；
3. 執行 `authorize-finalization`，要求 checkpoint 的 issue / branch / head_sha 與 fresh owner identity exact match；
4. 產生本次 guard invocation 的 `finalization-proof.json`；
5. **在真正不可逆 closure mutation 前**再次執行 `verify-finalization-proof`；
6. proof 驗證通過後才可進行 GitHub close/finalize action；完成後仍須 remote issue-state readback。

固定 CLI：

```bash
python -m tools.continuity_controller authorize-finalization <checkpoint.json> \
  --issue <exact-issue> --branch <exact-owning-branch> --head-sha <fresh-head> \
  --proof-out <finalization-proof.json>

python -m tools.continuity_controller verify-finalization-proof \
  <checkpoint.json> <finalization-proof.json> \
  --issue <exact-issue> --branch <exact-owning-branch> --head-sha <fresh-head>
```

以下任一情況一律 **fail closed**：

- 沒有 owning checkpoint；
- checkpoint malformed / non-terminal；
- issue / branch / HEAD 任一 owner identity 缺失或不匹配；
- 沒有本次 guard invocation proof；
- proof malformed、owner 不同、版本不符；
- guard 後 checkpoint 又被修改，造成 proof stale；
- 只有聊天文字、stdout 摘錄、舊 evidence 或人工聲稱「guard 已跑」而沒有 current proof verify。

Proof 不得跨 issue / branch / HEAD / checkpoint mutation 重用；任何 owner 或 checkpoint drift 都必須重新 authorization。Proof 是 process-integrity receipt，不是對 malicious writer 的 cryptographic signature；因此它只在 canonical closure path 中作 machine gate，不能被文字聲明取代。

`RUNNING / WAITING_REMOTE / RECOVERING / BLOCKED` 全部都是 non-terminal；即使 GitHub code 已 merge、focused/Combined tests 已 PASS、或文字 Skill 寫著可見 checkpoint，也不得通過 executable closure gate。

只有 acceptance / invariant / cleanup / drift / required issue-state evidence 全部收齊後，才允許 durable state 落成 `TERMINAL_SUCCESS`；之後仍須 owning guard proof + 逐票 GitHub readback 才能關單。

若 executable guard 與 GitHub process-state 不一致，採 fail-closed：不能以其中任一方單獨宣告完成。

Primary behavior authority：`tests/process/test_finalization_owner_guard.py` + `tests/process/test_continuity_controller.py`。Markdown marker/string tests 僅保護文件 routing，不能取代 behavior guard。

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

只有本票 acceptance criteria、terminal QA、必要 AI Library writeback、workflow cleanup / drift audit（若適用）都完成，並把 evidence 回寫 issue，且 owning finalization proof 在 closure 前 fresh verify，才可 close。

Close 後立刻遠端反讀，確認 `state=closed` + `state_reason=completed`。

### 2. closing/Final Combined ticket

只有它依賴的所有 required child 都已 CLOSED/completed，且自己的 Combined Acceptance / integration / cleanup / drift audit / completion evidence 全部完成，並 fresh 通過自己的 owning finalization proof，才可 close。

不得因 target 已 fast-forward / merge 就跳過這張 closing ticket。

### 3. Master/parent

只有**所有 required child**、所有 closing/acceptance ticket、closing/Final Combined ticket（若有）都**全部 CLOSED/completed**，且 Master 自己的 owning checkpoint + current proof 已通過，才可 close Master/parent。

任何 required child 仍 open 時，**不得宣告 Master 完成**，也不得只手動關 Master 來掩蓋缺失流程。

Master close 後必須再次反讀 Master + required children，確認整條鏈 terminal。

## Issue Closure owner

拆工單時必須指定明確的 `Issue Closure owner`。

- closing/acceptance ticket 負責逐票關單與 terminal readback。
- 有 Final Combined ticket 時，Final Combined ticket 預設同時是 chain closure owner，除非 breakdown 明確指定其他 owner。
- 不得寫成「大家負責」或依賴 GitHub 自動 close。

Issue Closure owner 的責任不是只 merge code，而是把 acceptance evidence、owning checkpoint、guard proof、issue state 與 parent/child chain 收到一致。

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
- exact owning checkpoint identity
- current `FINALIZATION_GUARD_PASS` + `FINALIZATION_PROOF_VALID` evidence
- 每張 required child 的 issue number + state + state_reason
- closing ticket state + state_reason
- Master/parent state + state_reason
- temporary QA workflow cleanup / tested→cleaned drift audit（若該工單要求）

只要其中任一 required issue 還 open，或 owning checkpoint / proof gate 任一缺失，輸出只能是 `code integrated, process incomplete` 或等價的精確狀態，不得回報正式完成。

## 禁止的捷徑

- PR merged → 當成 issue completed：禁止。
- target fast-forward → 當成 Master completed：禁止。
- Combined QA GREEN → 直接關 Master、跳過 T5/T6/closing ticket：禁止。
- Issue body 有 `#child` / `depends on` → 假設 dependency 已完成：禁止，必須逐票反讀。
- GitHub autoclose keyword 沒有實際 readback → 不算 evidence。
- bare `assert_finalizable` → 當成 closure authorization：禁止。
- 聊天／stdout 說「guard 已跑」但沒有 current proof verify → 禁止。
- 舊 proof 跨 issue/branch/HEAD/checkpoint drift 重用 → 禁止。
- code 已進 target 後發現票還 open → 不准改口說「其實已完成」；繼續把 process 收完。

## 快速檢查

- [ ] 已讀 `個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md`。
- [ ] fresh owning issue / branch / HEAD 已鎖定。
- [ ] owning checkpoint 與 fresh owner exact match。
- [ ] `authorize-finalization` 已實際執行並產生 proof。
- [ ] closure mutation 前 `verify-finalization-proof` 已 fresh GREEN。
- [ ] 已辨識 active issue chain。
- [ ] 已指定 `Issue Closure owner`。
- [ ] leaf/current ticket evidence 已回寫並 CLOSED/completed。
- [ ] closing/Final Combined ticket（若有）已在 children terminal 後 CLOSED/completed。
- [ ] Master/parent 只在所有 required child terminal 後關閉。
- [ ] 每次 close 後都有 remote readback。
- [ ] target integration 與 issue closure 分開判定。
- [ ] 沒有 open required issue 時才宣告正式完成。

## CLOSING_TURN_EXIT_BRIDGE

`code integrated, process incomplete` 是精確 observation，不是合法停工點。只要 owning checkpoint 仍是 `RUNNING` 且 `next_action` 為 workflow cleanup、tested→closing drift、close/readback leaf、closing ticket 或 Master，本 Skill 在任何 user-visible response boundary 都必須呼叫 `assert_turn_exitable`；machine guard 拒絕時立即續做 next action。

### MASTER_CHAIN_TURN_EXIT_HARD_GATE_V1

關閉一張 child Issue 後，**不得只看到 child checkpoint terminal 就結束 turn**。如果 parent/Master 尚有 required child：

1. fresh-read Master/child dependency 與下一票狀態；
2. child terminal checkpoint 寫入 `master_issue + chain_state + next_issue + chain_next_action/chain_reason`；
3. 外層 turn-exit boundary 以 fresh `expected_master_issue` 呼叫 canonical guard；
4. `NEXT_CHILD_EXECUTABLE` 必須立即進下一票 claim/start，禁止 user-visible close report 後 return；
5. checkpoint 漏 handoff、Master mismatch、next child authority 不完整，一律 fail closed，不得用聊天記憶補。

只有 `CHAIN_COMPLETE`、genuine `NEXT_CHILD_BLOCKED`，或 explicit `USER_STOPPED` 才能讓 terminal child 成為合法 turn-exit 邊界。**child close != Master-chain complete**。

只有 genuine `BLOCKED`（需要外部 authority/capability）或上述 chain gate 允許的 terminal checkpoint 才能合法結束 turn。Workflow 是否真的完成仍另外要求 owning finalization guard + current proof + 全 issue chain readback；turn-exit 與 closure gate 不得合併。

## BRANCH_CLEANUP_OPEN_PR_REF_GATE

任何 remote branch cleanup 都必須在**每一批刪除前 fresh live-fetch 所有 OPEN PR**，並把每張 OPEN PR 的 **`head.ref` 與 `base.ref` 兩端同時列為 protected refs**。Canonical executable guard：`tools/branch_cleanup_ref_guard.py`。

- 刪除候選在執行 `git push origin --delete ...` 或等價 remote-ref deletion 前，必須先通過 `assert_delete_candidates_safe(candidates, open_pulls)`。
- 任一候選命中 OPEN PR 的 `head.ref` **或** `base.ref`，立即 fail closed；branch 已是 production/X ancestor、對應 issue 已 CLOSED、或看起來只是 QA/runner branch，都不能繞過 OPEN PR ref protection。
- 任一 OPEN PR 的 `head.ref` / `base.ref` 缺失、空白、型別錯誤或資料不完整，分類為 malformed OPEN PR ref evidence，**禁止刪除任何候選**直到 fresh evidence 可被驗證。
- OPEN PR list 必須是刪除當下的 live evidence；不得使用聊天記憶、過期 branch inventory 或先前 cleanup run 的快照代替。
- branch cleanup 只處理 ref hygiene，不會自動形成 integration / acceptance / issue-completion evidence。

Primary behavior guard：`tests/process/test_branch_cleanup_ref_guard.py`。文件 marker 只能保護 routing/知識不漂移，不能取代 executable guard。

## REMOTE_FINALIZATION_EVIDENCE_HARD_GATE

當 closure 由 scheduler/no-shell runtime 執行時，`OWNING_FINALIZATION_GUARD_V2` 必須由 trusted narrow executor `.github/workflows/whd-remote-finalization.yml` 真正執行。合法 evidence 至少同時包含：

- exact trusted workflow run terminal success；
- `WHD_REMOTE_FINALIZATION_RECEIPT_V1`，`result=GREEN` / `reason=FINALIZATION_PROOF_VALID`；
- uploaded `finalization-proof.json` artifact；
- receipt/proof 的 issue、worker、branch、HEAD、checkpoint blob/fingerprint、claim blob、authority SHA 全部與 closure 前 fresh identity exact match。

只有 Issue comment / chat / markdown 出現 `FINALIZATION_GUARD_PASS` 或 `FINALIZATION_PROOF_VALID`，但沒有上述 run + artifact，固定分類 `INVALID_FINALIZATION_EVIDENCE`。若 Issue 已因此誤關，必須 reopen，保留有效 code/integration evidence，先完成 process-state repair，再 fresh machine proof → close/readback；禁止直接再關一次。
