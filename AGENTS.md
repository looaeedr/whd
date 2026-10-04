---
whd_doc_role: CURRENT
whd_contract: agent-startup-process
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
<!-- WHD_DOC_ROLE role=CURRENT contract=agent-startup-process -->
> **[CURRENT — PROCESS ONLY]** `AGENTS.md` 擁有 Agent 啟動、Knowledge Preflight、派工與驗收流程入口；不擁有製造公式或 ae_engine 架構真值。
> Current authority pointers：
- `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md` — contract/role ownership map。
- `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md` — 現行 `ae_engine` 製造架構、公開 API 與 Certified Registry boundary。
- `AGENTS.md` — Agent 啟動、Preflight、派工與驗收流程入口。

# WHD 板金展開自動化系統

## AI 開發交接總覽

## -2. ENTRY_ROUTER_FIRST_HARD_GATE_V1：先找 canonical 入口，再做任何一般 discovery

<!-- ENTRY_ROUTER_FIRST_HARD_GATE_V1 -->

任何 WHD repository-content 任務、續作或修補，每個 invocation 的**第一個 routing sequence** 固定是：

`READ .agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json → READ .agents/skills/engineering/root-local-first/SKILL.md → ENTRY_ROUTER_READY`

`ENTRY_ROUTER_READY` 前只允許上述 bootstrap read。禁止 generic Drive/file search、Remote Desktop/local-machine search、GitHub content discovery、branch create、claim、Flow v2 discovery 或 mutation；聊天記憶、上一輪摘要、上一 invocation evidence 都不能代替 fresh read。

若已先走錯路，該段 discovery 不得算 execution evidence，固定 `FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY` 回 `/Google Drive/WHD` 重新進場；不得因「已經查到了」就沿錯路續做。

machine owner=`tools/root_local_first_gate.py::assert_entry_router_action_allowed`；contract=`.agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json`。

## -1. WORK_ROOT_BOOTSTRAP_HARD_GATE_V2：完整 Google Drive WHD repo root

<!-- WORK_ROOT_BOOTSTRAP_HARD_GATE_V2 -->

任何 WHD task/runtime/invocation 的 canonical root 固定是 `/Google Drive/WHD`，Drive folder id=`1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN`。

啟動固定硬閘門：

`WHD_ROOT_RESOLVED → ROOT_IDENTITY_VERIFIED → FULL_REPO_ROOT_VERIFIED → SHARED_UNPUSHED_LAYOUT_VERIFIED → ROOT_SHARED_UNPUSHED_GATE_READ`

root 至少必須存在 `.git/.agents/.github/AGENTS.md/tools/tests/ae_engine/gui_modules/.unpushed`。`source/state/work/artifacts` 不再是 CURRENT content-root 架構；舊 snapshot/control-root 不得再作 current authority。

canonical contracts：

- `.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json`
- `.agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json`
- `.agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json`

machine owners：`tools/work_root_gate.py`、`tools/shared_unpushed_integration.py`。

interactive/chat 直接讀 Google Drive root；scheduler/GitHub-only 可以從 repository contract 驗規則，但 repository-content authoring 仍只能回 canonical root，不得把 GitHub checkout 升格為施工 authority。

## -0.75. ROOT_LOOKUP_BEFORE_REMOTE_HARD_GATE_V1：先從根目錄找檔，遠端預設關閉

<!-- ROOT_LOOKUP_BEFORE_REMOTE_HARD_GATE_V1 -->

任何 repository-content task 的**第一個 file-discovery/baseline 動作**固定從 `/Google Drive/WHD` root 開始，沿 parent-folder chain 解析 exact repo path。

硬規則：

1. 全域 Drive search、GitHub search、remote checkout、Remote Desktop、backup、`.scratch`、`.unpushed` 同名檔只可作候選；未證明 exact canonical parent chain 前不得作 baseline。
2. 找檔、讀 baseline、判定目前版本、修改、測試、worker→0 merge 都在 canonical root 完成；找不到 root path 固定 fail closed，不得改連遠端找替代品。
3. 除非使用者明確要求，interactive/default invocation **不得連 GitHub 或遠端本機**。例外只有：
   - 「開工單」：只授權 Issue create/readback；
   - `/推推 文檔|主體`：只授權 selected lane delivery window；
   - 其他使用者明確點名的 GitHub/remote 操作；
   - user-authored scheduler entry contract 明確指定 GitHub-only 的該 invocation。
4. 「確認最新」「Preflight」「工具可用」「Git read-only」都不構成 remote authority。既有文字若宣告 pre-delivery 可 `READ/FETCH/COMPARE`，以本節為準：network remote 仍是 DENY。
5. **REMOTE_AUTHORITY_NON_PROPAGATION_HARD_GATE_V1**：Skill 自動觸發、Flow v2 bridge、工作槽/派工/closure、tracker=GitHub、Issue/PR reference、Connector/MCP 已連接、remote QA skill、read-only/status/log query 都不會產生或傳遞 GitHub authority。任何 GitHub repo metadata/code search/contents/branch/commit/Issue/PR/Actions/artifact/API/Connector/network-git action 都必須先通過 `tools/root_local_first_gate.py::assert_remote_connection_allowed(...)`；沒有 `WHD_REMOTE_CONNECTION_AUTHORITY_V1` 固定 `REMOTE_CONNECTION_DENIED`。
5. `/推推` 開啟 remote window 後，先鎖 exact delivery fileset(path+hash/delete marker)，fresh-read target；merge 前再驗 latest target/head/locked blobs；readback 成功後只清本次已交付 paths。

machine-readable behavior owner 必須由 root-local-first / 推推 Skill 與對應 contract tests 共同鎖定；後續文件不得重新長回 Git-first lookup。

## -0.5. ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1：共享 0、無 branch 施工、分 lane 交付

<!-- ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1 -->

任何 repository-content implementation 在 Phase6 Preflight 後固定使用：

- `.agents/skills/engineering/root-local-first/SKILL.md`
- `tools/shared_unpushed_integration.py`
- `.agents/skills/engineering/推推/SKILL.md`（只有 delivery 時）

唯一順序：

`ROOT_IDENTITY_CURRENT → LANE_CLASSIFIED → ZERO_INITIALIZED_OR_FRESH_READ → WORKER_BASE_LATEST_ZERO → WORKER_MUTATION_COMPLETE → WORKER_TESTS_GREEN → MERGE_TO_FRESH_LATEST_ZERO → CONFLICT_GATE_OR_MERGED → POST_MERGE_ZERO_TESTS_GREEN → ZERO_MANIFEST_FROZEN → DELIVERY_RESERVATION → GIT_WRITE_UNLOCKED`

硬規則：

1. 正常修改與測試**不開 Git branch**。Git branch 只在 `/推推 文檔` 或 `/推推 主體` 的 delivery phase 建立。
2. 文檔 lane=`.unpushed/docs/0`（完整路徑 `/Google Drive/WHD/.unpushed/docs/0`）；主體 lane=`.unpushed/body/0`（完整路徑 `/Google Drive/WHD/.unpushed/body/0`）。分類看歸屬，不看副檔名。治理/Skill/AGENTS/流程 authority/治理 tests → 文檔；產品程式/產品 tests/UI/renderer/geometry/manufacturing → 主體；**主體必要文件屬於主體**。
3. 第一次碰某 path，從 CURRENT root 複製進 lane `0` 並建立 generation/hash lineage。後來者固定以最新 `0` 為 base，禁止回 root 舊版本施工。
4. worker 完成後 fresh-read 最新 `0` 做三方合併。成功才可 generation+1。
5. **任何 merge conflict 固定寫 `WHD_UNPUSHED_CONFLICT_CHECKPOINT_V1`，state=`BLOCKED_USER_DECISION`，記錄 path/hunks/base/latest/worker identities，通知使用者決定。沒有 `EXPLICIT_USER_CONFLICT_DECISION`，禁止 auto ours/theirs、禁止改寫、禁止 generation+1、禁止 merge 回 0、禁止 `/推推`、禁止 push/PR。**
6. worker GREEN 後，merge 回最新 `0` 還必須再跑 post-merge tests；只有最新 `0` GREEN 才可 freeze manifest。
7. Flow v2 path reservation 降為 **delivery reservation**；它不再是 root/content write 前置 single-writer gate。
8. `/推推 文檔` 只能送 docs manifest；`/推推 主體` 只能送 body manifest。`PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_MANIFEST`，跨 lane 夾帶 fail closed。
9. GitHub Actions / remote QA 只做 post-push verification。任何內容修正回 root/shared-0，禁止 Git-side hotfix。

使用者詢問進度不構成停止理由；只有上述 hard gate 的 fresh blocker 或 `BLOCKED_USER_DECISION` 才能暫停內容前進。

# 0. 啟動硬閘門：先完成 Phase6 Knowledge Preflight，才准做事

### 0.0.0 Skill 使用前 user-visible 公告硬閘門

<!-- SKILL_INVOCATION_ANNOUNCEMENT_GATE_V1 -->

當本回合**實際要使用任一 WHD canonical Skill** 時，在任何實質 user-visible 內容之前，必須先公告本回合要使用的 Skill。這是使用者可見的硬閘門，不得只留在內部 reasoning、checkpoint 或 tool log。

單一 Skill 的固定格式：

```text
使用「<技能名>」技能…
```

多個 Skill 已在本回合開始時確定時，第一行一次列出：

```text
使用「<技能A>」「<技能B>」技能…
```

硬規則：

1. 上述公告必須是本回合**第一個 user-visible 行／句**；不得先輸出計畫、狀態、問題、分析、工具操作說明、結果或其他前言，再補 Skill 名稱。
2. Skill 名稱使用 active canonical identity，中文 Skill 直接使用 canonical 中文 `name`；不得用 retired alias 或自創簡稱冒充。
3. 只有實際要使用 Skill 時才公告；沒有使用 Skill 的回合不得為了形式虛報。
4. 若本回合開始時已知會使用多個 Skill，必須在第一行全部列出。若因後續 evidence / scope expansion 才新增一個事前無法知道的 Skill，必須在**第一次實際使用該新增 Skill 之前**另行輸出 `追加使用「<技能名>」技能…`。
5. announcement 本身不算 Skill execution evidence。後續仍必須真正讀取／載入該 Skill，完成 Preflight、required references、checkpoint、tests 或該 Skill 自己要求的其他證據。
6. 不得先完成實質工作，再用「使用某 Skill」補述並宣稱符合本 gate；公告順序錯誤即屬本回合流程違規。

> **這是所有 AI / Agent / Subagent 接手本專案後的第一個執行規則。優先級高於本文後續章節。**

在進行任何實質的**程式分析、Bug 診斷、派工、規格判斷、程式/測試/SOP 修改、重構、回歸或出包**之前，必須先執行 Phase6 Knowledge Preflight。禁止先靠經驗、記憶或通用技能開始工作，再事後補讀。

第一步固定執行：

```powershell
python tools/phase6_skill_preflight.py --task "<本次任務完整描述>"
```

### GITHUB_ONLY_REMOTE_PHASE6_PREFLIGHT_V1

GitHub-only / scheduler runtime 若沒有 host shell 或任意命令執行能力，**不得**因無法直接執行上面的 Python command 就把 mandatory Preflight 降級、略過或永久 BLOCKED。固定 remote transport 為：

`.github/workflows/whd-phase6-preflight.yml`

#### SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1

GitHub-only scheduler A/B 若在 startup 時尚不知道 exact owning Issue，可在 AI Library gate、fresh per-invocation `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`、fresh-read `AGENTS.md` 與 canonical Flow v2 Skill 都完成後，先做一次 `READ_ONLY_BOOTSTRAP_ONLY` discovery，專門解除 remote Preflight 的 Issue-binding 循環。

- 只准讀 `coord/execution-v2`、derived `ready-index`、`coord/monitor-v2:.dispatch/monitor/runtime/*.json` 的 NON_AUTHORITY latest-owner runtime observations、`tools/execution_scheduler_view.py` 的純 read-only projection，以及取得 exact owning Issue / branch / HEAD 必需的 GitHub metadata。scheduler bootstrap decision 順序固定 same-lane current → `TAKEOVER_CANDIDATE` → READY → explicit ingress；monitor evidence 不得單獨授權 takeover。若 current/ready 都空，允許額外用 `tools/scheduler_ready_ingress.py` 只掃 repository-owner-authored open Issue 第一個 nonblank `WHD_SCHEDULER_DISPATCH_REQUEST_V1` marker 與 `lane=ANY|A|B`；普通 open Issue 仍不是 execution authority。
- bootstrap 唯一輸出用途是綁定 owning Issue 後送 `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1`；不得另造永久 bootstrap Issue。
- `PRE_PREFLIGHT_MUTATION_FORBIDDEN`：receipt GREEN 且 REQUIRED SKILLS / REQUIRED REFERENCES 全部 fresh-read 前，禁止 canonical lane/runtime WAKE / HEARTBEAT / PROGRESS monitor write、claim、ACQUIRE、transaction request、Guard、repository mutation、QA、merge、closure、takeover、lease / ExecutionRecord mutation，亦不得 dispatch 除 trusted Phase6 Preflight request 外的其他 workflow / mutation transport。唯一例外是 `tools/scheduler_entrypoint_observation.py` 對 fixed A00/A20/A40/B15/B45 host entrypoint file 的 `authority=NON_AUTHORITY` WAKE/HEARTBEAT/EXIT；它只證明 host occurrence，永遠不得授權 execution。
- Preflight 完成後必須丟棄 bootstrap projection，重新 fresh-read canonical ExecutionRecord / scheduler view，才可進正常 Flow v2 WAKE / ownership / next_action。
- 這是 read-only issue-binding bootstrap，不是 Preflight bypass、execution authority 或第二套 scheduler state machine。

owner-authored owning-Issue request 第一行固定 `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1`，並 exact 綁定 `issue + worker + executor_source + branch + head_sha + task`；預計修改檔已知時逐一加入 `changed_file=`。trusted runner 只允許 checkout/read exact HEAD、執行 canonical `tools/phase6_skill_preflight.py`、讀取 required Skill/reference 並發布 `WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1`；不接受 arbitrary command，也沒有 repository contents write 權限。

remote result `GREEN` 只證明 exact task/HEAD 的 canonical Preflight 已執行且 requirements 可解析；**呼叫端仍必須 fresh-read result列出的每一個 required Skill / required reference，並留下自己的 `READ_SKILL` / `READ_REFERENCE` evidence，才可開始 substantive analysis 或 mutation。** generic Remote Guard 內部的 preflight 若未綁本次完整 task，不得替代這個 startup Preflight。

當預計修改檔案已知後，必須再次帶入所有預計修改檔：

```powershell
python tools/phase6_skill_preflight.py --task "<本次任務完整描述>" --changed-file "<file1>" --changed-file "<file2>"
```

Preflight 輸出的兩類清單都屬於硬閘門：

1. `REQUIRED SKILLS`：讀 `.agents/skills/skill_registry.json` 的匹配結果，將每一個 required Skill 對應 `SKILL.md` **逐一讀完**。
2. `REQUIRED REFERENCES`：將每一個 required reference **逐一讀完**。其中全域踩坑庫永遠必讀；命中領域 route 時，再加讀任務領域踩坑庫與 canonical 規格 / registry / Source of Truth。
3. 全域踩坑庫固定為 `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`。任何任務都不得省略。
4. 組合／截角／Relief／3D／Joint 類任務的任務領域踩坑庫至少包含 `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`；實際清單以 registry 的 `required_references` 為準，不得只靠這一條手工白名單。
5. 讀完後建立 evidence 檔。Skill evidence 保留 Skill 名稱；每一個 reference 必須寫入精確標記 `READ_REFERENCE: <repo-relative-path>`。沒有 evidence 視同未讀。
6. 確認 required Skills、全域踩坑庫、任務領域踩坑庫、canonical 規格 / registry / Source of Truth 全部完成後，才可開始實質分析或修改。
7. 若任務途中新增修改檔、範圍擴大，必須重新跑 Preflight 並補齊新增 requirements。
8. 派工給 Subagent 時，Subagent 必須在自己的隔離工作上下文重新跑相同 Preflight、讀相同必讀來源並留下自己的 evidence；總控不得用自己的 evidence 代替 Subagent。
9. 正式交付前依第 11 節要求再次跑帶 verification evidence 的 Preflight。

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

所有新的 task/runtime/invocation 在任何 substantive analysis、Guard、claim、repository mutation 或 workflow dispatch 前，
必須先由 tools/execution_entry_contract.py 產生並 user-visible 顯示 canonical
WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1 startup declaration。
本入口只 bridge 到該 canonical owner，不複製固定 Authorization/Purpose/Scope 文案。
每次 crash/re-entry 都是新 runtime，必須重新產生 declaration；此聲明只是 provenance/intent，
不得取代 claim、Guard、Preflight 或擴張 authority。

### 0.0.0A Skill mutation Preflight pre-write 硬閘門

<!-- FLOW_V2_SKILL_MUTATION_PREFLIGHT_PREWRITE_V2 -->

任何 repo mutation 只要 target path 符合 `.agents/skills/**/SKILL.md`，不得只靠「我已經讀過 Skill」、聊天記憶或一般 execution authority 放行。

Flow v2 CURRENT hard gate 固定為：

1. 本 invocation 已先完成 `EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1`，並 user-visible 輸出 canonical `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`。
2. 已對 **exact branch + exact pre-write HEAD + 完整 task + 全部 planned changed files** 執行 canonical Phase6 Knowledge Preflight。GitHub-only runtime 固定使用 `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1` / `WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1`。
3. remote receipt 必須 `result=GREEN`，且 exact 綁定 issue、worker、branch、head_sha、task hash 與 changed_files；呼叫端再 fresh-read receipt 列出的全部 REQUIRED SKILLS / REQUIRED REFERENCES。
4. 寫入只能發生在 receipt 綁定的 branch。GitHub contents mutation 必須逐 target 使用 fresh blob SHA 做 CAS。若 branch HEAD 自 receipt HEAD 往後的新增 commits **全部由同一 invocation、且全部只修改 receipt.changed_files 內路徑**，可作為同一 authorized mutation chain 連續施工；任一 foreign/intervening commit、target blob 非預期 drift、branch rewrite 或 owner/invocation 不可證明時立即 fail closed，重新跑 Preflight。
5. mutation scope 不得超出 receipt 的 `changed_files`。途中新增 target 必須回到第 2 步重跑；不得用同一 receipt 擴張 scope。
6. Skill/governance mutation 只在 authoritative `cleanup/2d-3d-sync` 上走單一治理驗收：`WHD Control Plane Regression` + authority/Registry/semantic-doc consistency tests。**不再建立 main mirror PR、parity transaction 或 ancestry reconciliation。** Control Plane Regression 必須包含 startup hard-gate contract tests。
7. legacy Remote Guard / Claim Activation / Remote Finalization / Turn Exit workflow transports 已自 `.github/workflows` 移除；**不得把已退役 legacy Remote Guard 當 CURRENT Skill write gate，也不得重新新增相容 workflow 檔**。CURRENT write authority 只來自 Flow v2 ExecutionRecord + atomic transaction + root-local-first receipt。

CURRENT machine owners：
- startup provenance/intent：`tools/execution_entry_contract.py`
- project knowledge preflight：`tools/phase6_skill_preflight.py` + trusted `whd-phase6-preflight.yml`
- repo write concurrency：GitHub blob-SHA CAS
- execution authority：Flow v2 ExecutionRecord / transaction
- governance acceptance：Control Plane Regression + authority/Registry/semantic-doc consistency；governance authority 固定為 `cleanup/2d-3d-sync`，`main` 不再是治理 mirror authority。

這不是降低防線，而是把 cutover 後不可達的 legacy Guard 要求改綁到 CURRENT 可執行且可 machine-readback 的 owners。缺任一 gate 即 `FAIL_CLOSED`。

### 0.0.1 派工 / Subagent projection bridge

<!-- FLOW_V2_DISPATCH_PROJECTION_ONLY_V1 -->

當任務明確要求「派工」、使用 `.agents/skills/engineering/派工/SKILL.md`，或將工作拆成 PM / Implementer / QA 視角時，**派工只擁有入口 routing 與 user-visible projection，不擁有第二套 execution state machine**。

1. durable execution truth 唯一是 `WHD_EXECUTION_RECORD_V2`；owner、lease、generation、active_run、mutation_scope、next_action、closure 與 resume 都必須由 Flow v2 atomic transaction / readback 決定。
2. GitHub-backed ticketed work 仍必須有真實 owning Issue；Issue 是工作實體/provenance，不是另一份 claim/checkpoint state machine。
3. `[轉移至：實作者]`、PM / Implementer / QA、CHECKPOINT 等文字若需要顯示，只能是 observation/projection；缺少這些文字不得推翻有效 ExecutionRecord，也不得成為 ACQUIRE / QA / FINALIZE 的額外 prerequisite。
4. 禁止再要求每票建立 execution-authority checkpoint path、journal/state 或 `RUNNING / WAITING_REMOTE / RECOVERING` 第二套狀態。領域測試、長 log、批次 runner 若本身需要 journal/checkpoint，可保留為**領域 evidence**，但不得授權 execution transition、turn exit 或 closure。
5. 沒有真正背景 Subagent Runtime 時，由同一執行者依 Flow v2 structured `next_action` 繼續施工；不得回報「已派給其他人等待」。
6. remote QA 由同一 ExecutionRecord 的 `active_run + qa` 欄位與 `monitoring-remote-qa` bridge 投影；已有 exact-head terminal GREEN 且符合 fast path 時優先 `CONSUME_QA`，不得恢復 legacy `REMOTE_QA_ACTIVE_LOCK` / checkpoint waiting machine。
7. 派工、工作槽、排程模擬、issue closure 等入口只可 bridge 到 `.agents/skills/engineering/flow-v2-execution/SKILL.md`；任何新增 CURRENT 規則若重新指定 `派工`、checkpoint/journal、Remote Guard 或 retired continuity runtime 為 execution owner，固定視為 anti-regrowth regression。

### DURABLE_TERMINAL_EXIT_HARD_GATE_V1

- **功能完成不是 terminal evidence**：QA GREEN、PR 已 merge、功能已生效、watchdog 已停、使用者可見問題已修好，都不得單獨授權「完成／可以停／turn exit」。
- user-visible completion/terminal claim 與 normal task exit 前，必須以 `tools/execution_invocation_exit.py::assert_durable_terminal_exit(record)` 驗 `WHD_EXECUTION_RECORD_V2`。
- 唯一 durable terminal tuple：`state=DONE`、`next_action=null`、`lease=null`、`active_run=null`、`owner_kind/owner_id=NONE`、`lane_id=null`、`closure.issue_closed=true`、`closure.released_at!=null`、`mutation_scope` 為 `RELEASED` 或不存在。
- 任一條未成立即 `DURABLE_TERMINAL_EXIT_BLOCKED`；同一 invocation 必須繼續 exact `next_action` 到 DONE，或留下 genuine machine blocker。**進度回報、功能面成功、merge/QA 成功都不是停止點。**
- **GREEN consume hard gate**：exact-head QA/CI terminal GREEN 不得作為 turn exit。GREEN 必須先被 `ACCEPT_QA` / `CONSUME_QA` 寫入 canonical record；若 continuation=`MERGE`，立即進 no-yield terminal tail。
- **terminal tail hard gate**：accepted exact-head QA + `next_action=MERGE`，以及 merged + `next_action=FINALIZE`，都固定由 `classify_invocation_exit` 回 `CONTINUE_TERMINAL_TAIL`；此時 host boundary / substantive progress 不得授權 YIELD。
- terminal tail 唯一正常終點是 `MERGE → Issue close/readback → FINALIZE → RELEASED/DONE`。`PR_MERGED` 本身仍是 nonterminal；只有 genuine machine blocker 可中斷。
- static contract：`.agents/contracts/WHD_DURABLE_TERMINAL_EXIT_HARD_GATE_V1.json`。
- **repository-content physical-cycle completion**：上述 `DONE` tuple 只代表 Flow v2 execution terminal。若本票產生 repository-content diff，user-visible「完成」與 normal cycle return 還必須呼叫 `tools.execution_invocation_exit.py::assert_repository_content_cycle_complete(record, source_manifest, workspace_location)`；若結果是 `CONSUME_SOURCE_EXPORT` 或 `ARCHIVE_WORKSPACE_TO_DONE`，同一 cycle 繼續 post-integration durability tail，直到 `DURABLE_CLEANUP_COMPLETE`。

### 0.0.2 超長 Log / Context-Safe Execution 硬閘門

<!-- LONG_LOG_CONTEXT_SAFE_EXECUTION_V1 -->
pytest、Xvfb、Combined Acceptance、remote CI 或其他長流程只要可能產生大量輸出，就必須讀並遵守：

`.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`

硬規則：完整 raw log 落檔／artifact，不得整包灌入執行或聊天 context；running 期間只讀 structured status、bounded tail/new chunk；FAIL 先定位 failure marker 再擷取有限上下文；分段讀取必須保存 offset/cursor；Runtime/聊天視窗被切斷後先反查 run/process + branch + HEAD + checkpoint + artifact + cursor，從同一工作續接，禁止因視窗中斷就重跑 full-suite。Remote QA 的 30 秒 active polling 仍由 `monitoring-remote-qa` 擁有，本 gate 不建立第二套 polling state machine。
<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->
### 0.0.2A QA Pipeline Fail-Closed 硬閘門

任何會影響 PASS/FAIL 判定的命令，只要透過 pipe（尤其 `tee`）輸出，必須啟用 `set -o pipefail` 或等價保留左側命令 exit status。`pytest ... | tee ...` / `python validator.py | tee ...` 若未 fail-closed，即使 GitHub Actions step/job 顯示 SUCCESS 也不是有效驗收證據。

正式接受前同時必須確認：

1. test / validator 的完整 terminal summary 或等價終態，而不是只看 workflow conclusion；
2. exact tested `head_sha`；
3. characterization / Move-Only baseline 使用 immutable accepted commit SHA，禁止 movable branch ref；
4. symbol owner/class 來自 AST/dependency inventory 或 exact source reread，不得由 public inheritance surface 猜測。

若歷史 run 違反任一條，狀態只能標記為 evidence invalid / rerun required；禁止拿假綠結果關單、合併或 release。

### 0.0.3 成品板件驗收硬閘門：Focused GREEN 不能直接合併

> 本節屬所有 AI / Agent 的第一閱讀規則。只要改動會影響實體板件使用路徑，issue-specific QA 通過後仍必須交接到 `驗證板件與DXF`。

下列任一情況，正式合併／關單／release 前都必須執行：

```text
.agents/skills/engineering/驗證板件與DXF/SKILL.md
```

觸發範圍至少包含：

- physical-part identity / dynamic part / multipart topology；
- 2D / 3D 顯示、navigation、sync、FinalScene；
- manufacturing Final Material / BEND / holes / placement；
- DXF export / physical-piece file set；
- Save→Reload / project persistence；
- GUI / Bridge 修改雖屬 adapter，但會改變操作員看到、切換或回讀的實體板件。

硬規則：

1. **Focused / issue-specific regression GREEN 只代表該 seam GREEN，不等於 Final Acceptance。**
2. 單一板件修改至少跑「驗該板件」；跨 2D/3D/DXF/persistence、multipart/dynamic IDs 時必須跑「完整板件驗收」。
3. multipart 必須逐 physical piece 驗；不得只驗 aggregate logical `box_body`。
4. DXF 相關必須 actual export → reopen → compare；Save/Reload 相關必須真的存檔再重建 canonical output。
5. Remote QA 建立後必須依 `monitoring-remote-qa` 輪詢到 terminal；cleanup 後做 tested-head → cleaned-head drift audit。
6. 若缺少 `驗證板件與DXF` 的 final evidence，狀態只能是 **focused GREEN / final acceptance pending**，禁止標記 ACCEPTED、merge 或 release。
7. `.agents/skills/skill_registry.json` 的 `part-dxf-acceptance` route 是機器可讀防線；命中相關 changed-file / task keyword 時，Preflight 必須自動要求此 Skill，禁止靠 AI 記憶決定要不要跑。

### 0.0.3.1 Flow v2 durable completion / resume bridge

<!-- FLOW_V2_DURABLE_COMPLETION_BRIDGE_V1 -->
當任務具有 remote QA、runtime cut / resume，或準備宣告完成／關單時，唯一 CURRENT durable execution truth 是 `WHD_EXECUTION_RECORD_V2`。續跑依 live lease + structured `next_action`；completion/turn exit 依 `tools/execution_invocation_exit.py`；closure 只由 atomic `FINALIZE` 寫成 durable `DONE`。

retired continuity runtime、legacy checkpoint finalization 與 `assert-finalizable checkpoint.json` 只保留 historical knowledge provenance，**不得作 CURRENT finalization prerequisite、execution authority 或停止判定**。exact-head QA GREEN 必須先 `ACCEPT_QA / CONSUME_QA`，進入 terminal tail 後持續 `MERGE → FINALIZE → DONE`；只有 fresh machine evidence 的 genuine blocker 可以中斷。

### 0.1 知識載入優先級

```text
AGENTS.md 啟動硬閘門
    ↓
tools/phase6_skill_preflight.py
    ↓
全域踩坑庫（永遠必讀）
    ↓
.agents/skills/skill_registry.json
    ├─ 專案 required SKILL.md
    └─ required_references
         ├─ 任務領域踩坑庫
         └─ canonical 規格 / registry / Source of Truth
    ↓
通用 Superpowers / 其他一般技能
    ↓
production code
```

**通用技能不能取代專案技能；專案技能也不能取代踩坑庫與 canonical references。** 任一層未完成，都視為尚未取得分析／修改資格。

### 0.2 Fail-closed 禁止事項

以下行為一律視為流程違規：

- 只跑 Skill Preflight 卻未讀 `REQUIRED REFERENCES`。
- 漏讀全域踩坑庫，或命中領域 route 後漏讀任務領域踩坑庫。
- 只讀通用 Superpowers，未讀 `.agents/skills/`、踩坑庫或 canonical references。
- 憑記憶猜哪些 Skill / reference 適用，而不執行 `phase6_skill_preflight.py`。
- 派工給 Subagent 時未要求該 Subagent 重新完成同一套 Preflight。
- 宣稱已執行派工 Skill，卻沒有 PM / Worker / QA 角色標記、checkpoint path、journal/state path 與 resume command。
- evidence 只寫檔名但實際沒有讀取；reference evidence 必須使用 `READ_REFERENCE: <path>`。
- Preflight 有任何 required Skill / reference 未完成就修改 production / tests / SOP。
- 因任務「看起來很簡單」而跳過 Preflight。

若 Preflight 腳本無法執行、registry 缺失、required Skill / reference 找不到，**不得自行降級成無 Skill／無踩坑模式**；必須先修復/定位啟動鏈問題，或明確回報阻塞。

---

> 本文件是下一個 AI 的第一閱讀入口。
> 若需要了解完整架構、金庫型製造規則、零件拓撲對照、開發規範或後續計畫，請再閱讀 `handoff/` 目錄內的細節文件。

---

<!-- WHD_SECTION_ROLE role=HISTORICAL contract=legacy-v5-architecture-roadmap -->
> **[HISTORICAL/SUPERSEDED]** 第 1～10 節是 V5 / Layer A-B-C / GUI Preview 時代的架構與 roadmap snapshot，只保留 provenance，不參與 current routing。現行製造架構請讀 Canonical Authority Map 指向的 ae_engine 規範。

# 1. 專案核心精神

本專案為 V5 世代的：

> **鈑金自動展開與 DXF 生成引擎**

目前第一套完整驗證的製造體系為：

> **金庫型箱體**

但架構目標不是做成「金庫型專用程式」，而是：

> **以金庫型作為第一套 Factory Policy，建立可持續擴充的通用 2D Sheet-Metal Geometry Engine。**

---

## 1.1 揚棄 Hardcoded Vertex Arrays

新版已開始全面淘汰：

```python
cutting_points = [
    (...),
    (...),
    ...
]
```

這類針對特定零件人工排列 12 點、16 點、17 點主外框的作法。

現在主外框的核心思想為：

```text
母材 Base Polygon
        -
退讓 / 裝配切刀 Relief Polygon
        =
最終 Material Polygon
```

主要透過 Python `Shapely` 執行：

```text
difference
union
intersection
```

最終再取得 polygon exterior 作為 `CUTTING`。

---

## 1.2 Geometry 是唯一真相來源

系統正在收斂成：

```text
Config / 1.csv / 使用者參數
              ↓
      sheetmetal_geometry.py
              ↓
       Geometry Result
        ┌─────┴─────┐
        ↓           ↓
    GUI Preview   DXF Export
```

GUI 與 DXF 不應各自維護一套座標演算法。

---

## 1.3 Topology 與 Factory Policy 分離

必須區分：

```text
Topology
= 這塊板是怎麼折的
```

與：

```text
Factory Policy
= 因為裝配 / 生產需求，哪裡需要退讓
```

例如：

```text
FourSideFlange
```

是一種通用 Topology。

而金庫型封頭尾使用的：

```text
Assembly Insertion Relief
```

則屬於金庫型 Factory Policy。

禁止把目前金庫型規則直接當成所有鈑金箱體的宇宙通則。

---

# 2. 系統模組架構

目前系統主要分為三層。

---

## Layer A：幾何引擎

### `sheetmetal_geometry.py`

負責純 2D 板金幾何。

此層：

```text
不可依賴 ezdxf
不可處理 GUI
不可直接寫 DXF
```

目前主要幾何結構包含：

### FourSideFlange 系列

目前用於：

```text
Door
Indicator Box
Base Plate
End Cap / Tail
```

封頭尾雖然具有較特殊的二折與裝配退讓，但仍應盡可能建立在共用 FourSideFlange / topology 基礎上，而不是重新退化成獨立硬編碼外框引擎。

### StripFoldChain

目前用於：

```text
Box Body
Stretched Box Body
```

它代表沿單一方向連續折彎的板材。

BEND 位置由 segment cumulative sum 動態產生，不再由 exporter 自行維護：

```text
x1
x2
...
x8
```

---

## Layer B：參數整合與 DXF 輸出

### `ae.py`

### 目前開發版本可能為 `ae_3.py`

此層負責：

```text
讀 config.ini
接收尺寸參數
將舊參數轉成 Geometry / Policy
呼叫 sheetmetal_geometry
寫入 DXF layer
處理孔洞與其他 secondary features
```

加工層包括：

```text
CUTTING
BEND
MARKING
CHECK
STOCK
DATUM
```

原則：

> `ae.py` 可以做 Adapter，但不應重新實作 Shapely 主外框布林算法。

---

## Layer C：自動化產線與 GUI

### `batch_unfolder.py`

### `gui.py`

負責：

```text
讀取 1.csv
盤體分類
使用者輸入
批次派發
GUI Preview
```

目前主要待辦：

> 將 `gui.py` Canvas 裡既有的手算預覽座標移除，改為直接使用 `sheetmetal_geometry.py` 的 geometry result。

目標是：

```text
GUI Preview == DXF Structural Geometry
```

---

# 3. Relief / Clearance 的正確定位

不是所有尺寸都必須是 `T` 的倍數。

例如：

```text
ytop1
FW
yl1
yr1
```

這些是真實折邊尺寸，仍然來自：

```text
config
工單
使用者輸入
```

但加工與裝配 clearance 若本質上和板厚有關，應優先表示為：

```text
0.5T
1T
2T
fold - T
```

而不是固定毫米值。

例如金庫型封頭尾目前已確認：

```text
Top Secondary X extra = 0.5T
Top Secondary depth   = 2T
Bottom extra          = 0.5T
```

詳細金庫型規則請讀：

```text
handoff/02_VAULT_FACTORY_RULES.md
```

---

# 4. 理論幾何與加工補償的界線

本 Geometry Engine 應負責：

```text
零件真實外形
折彎拓撲
裝配必要退讓
結構性 interference relief
```

例如：

> 金庫型封頭尾為了插入箱身而產生的 Primary / Secondary Relief

這些屬於零件設計本身，必須留在 Geometry / Factory Policy。

但是下列後加工細節不應污染理論幾何：

```text
Laser Kerf compensation
Corner over-cut hole
一字清角
折床加工補刀
CAM 特殊過切
NC 加工補償
```

這些應由後端 CAM / NC 層處理。

---

# 5. 下一個 AI 的嚴格規則

## 禁止依盤名新增主幾何演算法

錯誤方向：

```python
if part_type == "NEW_PANEL":
    build_new_panel_17_points()
```

正確流程：

```text
先辨識 Topology
↓
尋找現有 Policy
↓
若已有相同物理關係，直接共用
```

---

## 禁止手算主外框 Vertex Array

不得為新截角重新推導：

```text
12 點
16 點
17 點
```

應建立：

```text
Base Polygon
+
Relief / Tool Polygon
```

再做布林差集。

---

## 禁止把金庫型 Rule 當成所有箱型 Rule

目前主要 regression 與製造規則來自：

```text
金庫型
```

未來若新增：

```text
落地盤
壁掛盤
戶外箱
其他箱型
```

應先確認實際裝配方式。

Topology 可以共用。

Factory Policy 不一定相同。

---

## 必須維持 API 邊界

`sheetmetal_geometry.py`：

```text
不可 import ezdxf
```

`ae.py`：

```text
不要自己實作主 Shapely boolean geometry
```

GUI：

```text
不得再自行維護另一套 Structural Geometry
```

---

# 6. 目前進度

目前第一階段通用化已涵蓋：

```text
Box Body
Stretched Box Body
End Cap / Tail
Door
Stretched Door
Base Plate
Indicator Box
```

目前核心方向已由：

```text
每個零件一套座標公式
```

轉成：

```text
Part Parameters
→ Topology
→ Factory / Relief Policy
→ Polygon Boolean
→ CUTTING
→ Material-clipped BEND
```

---

# 7. 下一步任務

目前下一個主要任務：

> **GUI Preview 重構**

將 `gui.py` Canvas 裡原本負責畫零件預覽的手工座標邏輯逐步刪除。

改成：

```text
GUI Parameters
      ↓
Part Adapter
      ↓
sheetmetal_geometry.py
      ↓
Outline / Bend Result
      ↓
Canvas Rendering
```

這樣才能保證：

```text
使用者畫面看到的形狀
=
最終輸出的 DXF 形狀
```

---

# 8. 接手 AI 的閱讀順序

本文件只負責「快速建立全局認知」。

需要細節時依序閱讀：

```text
handoff/00_AI_HANDOFF_README.md
```

快速接手說明。

```text
handoff/01_ARCHITECTURE.md
```

完整 Geometry / Topology / DXF 分層。

```text
handoff/02_VAULT_FACTORY_RULES.md
```

金庫型封頭尾與相關 Factory Rules。

```text
handoff/03_PART_TOPOLOGY_MAP.md
```

Door / Indicator / BasePlate / EndCap / BoxBody 的 Topology 對照。

```text
handoff/04_DEVELOPMENT_RULES.md
```

TDD、Hard-Code 禁令、Regression 與驗證規則。

```text
handoff/05_NEXT_STEPS.md
```

後續重構方向與 roadmap。

---

# 9. 接手後第一個動作

下一個 AI 不要拿到專案就立刻修改。

正確流程：

```text
1. 讀本 AI_HANDOFF.md
2. 按需求閱讀 handoff/ 細節文件
3. 讀 sheetmetal_geometry.py
4. 找目前實際使用中的 ae.py / ae_3.py
5. 讀現有 tests
6. 跑完整 test suite
7. 確認 green baseline
8. 再開始 GUI Preview 重構
```

---

# 10. 一句話核心

> **Geometry 是共用的，Factory Rule 是可配置的，Part Name 不是幾何規則；GUI 與 DXF 最終必須共用同一份 Geometry Result。**

---

<!-- WHD_SECTION_ROLE role=CURRENT contract=agent-startup-process RESUME -->
> **[CURRENT PROCESS RESUMES]** 以下 Skill Preflight / Registry / remote QA / execution governance 仍屬 current process contract；上方 HISTORICAL 標記不延伸到此處。

# 11. Skill Preflight 強制啟動鏈

Skill 決定「AI 怎麼改」。截角資料庫決定「程式算什麼」。兩者是不同強制鏈，禁止互相取代。

修改任何程式、測試、SOP、registry 或 release policy 前，必須先執行 Skill Preflight：

```powershell
python tools/phase6_skill_preflight.py --task "<本次任務描述>" --changed-file "<預計修改檔案>"
```

機器可讀觸發表固定在：

```text
.agents/skills/skill_registry.json
```

AI 不需要靠記憶猜有哪些 Skill；必須依 registry 列出的 `required_skills` 逐一讀完 `SKILL.md`，並留下 verification evidence。沒讀完、沒 evidence，禁止修改 production code，release gate 也不得出包。

任務類型的最低要求：

```text
截角 / relief / INSERT / INSERT_OVERLAY / WRAP / 3D / FinalScene / AssemblyJoint
→ 必讀 phase6-corner-3d-model-integrity

OVERLAY / flat-X / formed FW / BOX_BODY_FORMED_FW
→ 必讀 phase6-corner-3d-model-integrity
→ 再必讀 phase6-overlay-relief-basis

release / FULL / UPDATE / packaging / 出包
→ 必讀 phase6-release-packaging

GUI 效能 / 卡頓 / live-sync / Tk trace / 重算 / DXF cache / debounce / 3D designer
→ 必讀 phase6-gui-performance-integrity

bug / debug / regression / 修正
→ 必讀 diagnosing-bugs
→ 必讀 tdd

git push / GitHub Connector / DNS / remote sync / 遠端同步
→ 必讀 .agents/skills/misc/git-remote-sync-fallback/SKILL.md

同步遠端QA / 遠端 QA / GitHub Actions / workflow run
→ 必讀 .agents/skills/engineering/monitoring-remote-qa/SKILL.md
→ workflow run 建立後必須持續監控 run / job / step 到終態；不得只觸發後停止。

remote QA / GitHub Actions QA / 同步遠端 QA
→ 必讀 monitoring-remote-qa
```

正式出包前必須再次執行：

```powershell
python tools/phase6_skill_preflight.py --task "release FULL UPDATE" --changed-file "release_required_artifacts.json" --evidence "<本輪 verification evidence>"
```

若有動到對應 production 檔，但 preflight 顯示任何 `✗`，禁止打包交付。

---

# 12. 截角資料庫強制鏈

截角資料庫不是 Skill。它是 runtime 製造規則 Source of Truth：

```text
基準檔/截角資料庫/certified_relief_rules.json
→ ae_engine/certified_relief_registry.py
→ lookup_certified_endcap_relief()
→ manufacturing geometry
→ 2D / 3D / DXF
```

任何修改 Corner / Relief / Assembly Intent / Registry / 3D backprojection 前，必須先讀：

```text
基準檔/截角資料庫/README_母規則說明.md
基準檔/截角資料庫/certified_relief_rules.json
基準檔/截角資料庫/certified_relief_rules.schema.json
```

Registry HIT 時，Certified JSON 的公式與 metadata 是 canonical 製造答案；production code 禁止另寫第二套公式。Registry MISS 才能進 3D discovery / candidate flow，且 PROVISIONAL 結果不得冒充 CERTIFIED。



---

## 0.0.2 2026-09-06 事故硬閘門：Remote Source of Truth、Exact Seam、真派工、Harness 分類

> 本節來自 2026-09-06 Receiving 工單事故。屬永久 fail-closed 規則；優先級與 0.0.1 派工硬閘門相同。後續 AI 每次讀 AGENTS.md 都必須看到並遵守。

### A. GitHub 專案已指定 branch 時，ZIP / sandbox / 聊天 checkpoint 一律不得冒充施工 Source of Truth
- GitHub 專案即使已在文件中指定 branch，也**不自動授權 remote connection**。interactive/default 先以 `/Google Drive/WHD` canonical root parent-chain identity 作施工 baseline；只有本輪使用者已明確授權 GitHub/`/推推` 時，才 fresh-read remote branch HEAD 作 delivery/provenance anchor。remote branch HEAD 永遠不得取代 root 施工面。
- 上傳 ZIP 只能是 fixture / archive / 參考輸入；除非使用者明確指定「這個 ZIP 就是本輪施工基準」，否則禁止拿 ZIP 當 production baseline、A/B good version、checkpoint parent 或 regression oracle。
- 若已在錯誤 tree 做過修改、PASS/FAIL、checkpoint，發現後必須整批宣告 evidence 作廢；禁止挑其中看起來有用的結果續工。
- 每張工單 checkpoint / journal 必須寫明 repository、branch、parent HEAD SHA；branch HEAD 漂移時先重新 compare / rebase execution plan。

### B. 使用者回報 GUI / live-sync Bug 時，RED 必須逐步重現完全相同操作順序
- fresh-open target family GREEN 不能證明「3D 已開啟 → live switch 到 target family」GREEN。
- 驗收 seam 必須包含使用者回報的前置狀態、開啟順序、切換動作與 observable result。
- 錯 seam 得到 GREEN，只能作 guard，不得關閉原 bug 工單。
- 正式拆工單前，必須把 exact user path 跑成真 RED 或明確證明已 GREEN。

### C. 使用者已確認的產品 datum / 語意，不得被文件片語重新解釋
- 「後方內側安裝」「折邊落在後面板」等裝配描述，不等於可擅自更換 Base Plate datum、placement kind 或產品基準。
- 使用者已確認「基準正確、錯在幾何跑出箱體」時，修正必須鎖住該 datum，只查尺寸、origin、transform、cell placement。
- 任何與使用者明示產品語意衝突的推論，先停下並建立 exact RED，不得先改 production。

### D. 「派工」必須先有實體工單，再進 Worker
- 使用者核准拆票並要求派工後，若本專案以 GitHub Issues 作 owning tickets，必須先建立並反讀 Issues，確認標題、Issue number、依賴、RED、驗收內容正確，再出現 `[轉移至：實作者]` 或修改 production。
- 只有聊天中的 T1/T2 清單、角色標記、sandbox checkpoint，不算已推工單。
- 正式規格若要作施工 Source of Truth，也必須落 repo / owning Issue；聊天 copy 不是 durable execution artifact。

### E. 外部工具回傳 schema / URL 不得猜；任何 undefined 關聯都視為阻塞
- 建立 Issue / PR / workflow、讀 branch / commit metadata 後，先檢查工具 schema 與第一筆真 response，再引用 ID、SHA、tree 或 URL。
- 禁止自行假設 `issue.number`、commit 的 nested `tree` 欄位、或擅自 URL-encode branch path；Connector 的 schema/URL contract 以工具定義與真 response 為準。
- 依賴欄、checkpoint、comment 出現 `#undefined` / 空 SHA / 空 run_id 時，立即停止下游施工，修正資料並遠端反讀確認。
- 批量建立工單後至少反讀一次 owning tickets，確認 cross-link 全部可解析。

### F. Harness / Setup failure 永遠不是 requirement RED
- 缺 dependency、錯 import、collection/setup error、runner bootstrap failure，全部先分類為 harness failure。
- 只有 harness 成功進入目標 seam 後，由 pytest assertion / error 明確命中使用者症狀，才能記為 requirement RED。
- 修 harness 後只重跑 unresolved 範圍；已取得終態的 RED/GREEN 不得為方便整批重跑。
- remote QA 必須保存 `run_id + head_sha` 並追到 terminal state。

### G. 發現錯誤證據後必須明確撤銷
- 錯 baseline、錯 seam、harness failure 產生的 PASS/FAIL 必須在 journal / Issue / 回覆中標記 INVALID / REVOKED。
- Combined Acceptance 只能引用同一 execution tree、正確 seam、terminal harness 的證據。


### H. One-shot Remote QA 不得由 journal/state/docs push 誤觸發
- 工單用的一次性 GitHub Actions workflow 若監看 work branch push，必須用 `paths` / `paths-ignore` 或等價條件，讓它只因 production/test/harness 真變更觸發。
- 更新 `docs/superpowers/checkpoints/**`、`logs/preflight/**`、Issue provenance、state/journal 等 durable evidence 時，禁止再次啟動同一 focused QA，除非該 evidence 本身就是被測目標。
- 若已誤觸發，該 run 必須追到 terminal state並標記 `ACCIDENTAL_RERUN / NON_ACCEPTANCE_EVIDENCE`；不得重算 RED/GREEN totals。
- workflow trigger 自身也是工單 harness 的一部分，第一次建立前要檢查「哪些檔案會觸發」。

### I. Orchestration / Code Mode 模板在任何遠端寫入前先做變數與 parent preflight
- 任何批量建立 blob/tree/commit、Issue、workflow 的 orchestration script，在第一個副作用呼叫前必須完成：所有 template 變數已宣告、branch parent SHA 已鎖定、base tree SHA 可解析。
- 出現 `ReferenceError` / `NameError` / undefined template variable 時，分類為 orchestration harness failure；不得算 production RED。
- 若錯誤發生在第一個 blob/commit 前，必須反讀 branch 確認零副作用；若已有副作用，必須列出並清理後才能重送。


### J. Automated GUI Tests 不得把使用者偏好寫回 repository config.ini
- `config.ini` 是專案 canonical configuration；除非測試目的本身就是 persistence，任何 GUI/Designer 測試都不得因操作文字大小、全域設定、預設值等 UI 而改寫它。
- 只要測試會觸發 `_apply_ui_text_size_preference`、`persist_defaults`、Save Defaults 或等價 persistence callback，必須使用 `persist=False`、temporary settings backend、monkeypatch 或其他隔離 seam。
- 「pytest assertion 全 PASS」不能證明測試沒有副作用。Combined / release / 高風險 GUI gate 必須在測試前後驗 `config.ini` SHA256 + `git diff --exit-code -- config.ini`。
- 若 focused test 過去已 PASS 但後來被 invariant gate 證明會改 config，原 PASS 只能算 functional assertion evidence，不能算完整 QA evidence；修 isolation 後必須重跑 invariant gate。

### K. Code Mode / Orchestration 工具呼叫預算也屬 fail-closed 邊界
- 大型 orchestration 不得在單一 Code Mode 呼叫內串過多 fetch/blob/tree/commit/update_ref；先做純讀取與模板構造，再分小批執行副作用。
- 若出現 `Code Mode exceeded the maximum number of tool calls`，不得猜前半段是否已寫入；第一步固定反讀 branch/ref HEAD 與必要檔案，確認實際 side effects。
- branch/ref 未前進時，任何未引用 blob 都不得當成已完成修改；重新從反讀到的 parent HEAD 開始。
- 為了「原子」而把工具呼叫塞成超長腳本不是原子性；真正原子性由 tree/commit/ref 更新與 parent SHA gate 保證。

### L. 機械語意不確定：不懂就問，禁止假會

- WHD 涉及實體鈑金製造。對 CornerType、mating face、尺寸空間（料／包外／formed）、固定值／可變參數、參數 owner、DXF feature meaning 任一項不確定時，**先問使用者再寫規格或 production**。
- 禁止用目前程式行為、測試 expected、collision/probe、bbox、畫面外觀或「看起來合理」補成產品真值。
- 使用者已指定既有模型（例如 `CROSS / 十字截角`）時，優先保留該模型並以參數擴充；schema 不足不能成為另造 CornerType 的理由。
- 不確定期間可以做只讀調查、列出已知/未知，但不得把假設寫入 Registry、production、Skill、AI Library 或驗收 oracle。
- 使用者更正後，所有 durable knowledge 中衝突的舊說法必須標示 **SUPERSEDED / REVOKED**；不能只在聊天中更正。

### M. 使用者更正／新規則的 Durable Knowledge 自動同步

- **不得等使用者提醒「補技能／補 AI 庫」。** 只要使用者糾正了 AI、確認了新的產品語意、指出一個可重複踩坑，或本輪診斷得到會影響未來工作的永久規則，AI 必須在本輪主動判斷並同步 durable knowledge。
- 最低同步面：
  1. 直接相關的 `.agents/skills/**/SKILL.md`；
  2. 全域 AI 踩坑庫 `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`；
  3. 命中領域的 AI/踩坑庫、canonical spec、Registry README / schema 說明；
  4. 若已有 owning Issue / PR，補 durable correction/provenance。
- 不必每次四處亂加：只寫**真正會讓下一個 AI/Agent 做出不同決策**的永久規則；純一次性進度、run id、臨時數值不進知識庫。
- 使用者更正若與舊規則衝突，必須主動搜尋並標記舊內容 `SUPERSEDED / REVOKED`；禁止只新增新段落而讓兩套互相衝突的 authority 同時有效。
- 完成後必須遠端反讀確認 marker/內容真的存在；不能只口頭宣稱「已補」。
- 若不確定這次更正是否屬永久知識，**先問使用者是否要固化**；但對明確的產品規則、AI 行為規則、踩坑防線，不應再等使用者第二次提醒。

### N. Git phase branch gate（只在 `GIT_WRITE_UNLOCKED` 後）

- interactive/default content work 的前置 owner 是 `WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1`；root mutation / RED→GREEN / full gate / diff freeze 都發生在 canonical root，**不是先建 Git branch 再開工**。
- `GIT_WRITE_UNLOCKED` 前只允許 canonical root 的 offline `.git` identity/diff；**GitHub network READ / FETCH / COMPARE 也禁止**，除非本輪已有使用者明確 remote authority。
- `/推推` 或其他明確 remote authority 生效後，第一個 GitHub content step 才是：fresh-read authoritative target HEAD → 鎖定 exact delivery fileset → 建立新的 work branch → fresh-read parent/base SHA。
- 禁止直接修改 `cleanup/2d-3d-sync`、`main` 或其他 production target；target 只接受完成驗收後的正常 non-force merge / PR。
- Git work branch 只能接收 `EXACT_TESTED_DIFF_ONLY`。若 branch 上發現要補任何實質內容，回 root workspace 修改、重測、refreeze，再重新做 drift audit。
- target 在 freeze 後前進時，先 compare touched/base drift；命中 drift 固定 `RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE`，不得把 stale tested diff 硬套進新 base。
- branch existence 不能取代 final acceptance、config invariant、workflow cleanup、tested-head→closing-head drift audit。
- remote scheduler/control-plane scope 依 Flow v2 自己的 authority；本節不得用來把 interactive root-local-first 改回 Git-first。

### 0.0.4 Authoritative View freshness 硬閘門

> **authoritative state 已更新，不代表操作員目前看到的 View 已刷新。兩者是不同 invariant。**

凡 Main GUI / Fold Designer / 2D / 3D 共用 authoritative state 的同步或入口收斂任務，必須同時驗證資料同源與可見 View freshness：

1. authoritative mutation / external sync 必須先完成 commit/apply/invalidate，再由 View 重新讀 authoritative projection / render data。
2. 若 `corner_data` / 截角資料 View 當下可見，每個新的 authoritative revision 套用成功後**剛好刷新一次**。
3. hidden View 不得 eager refresh；replayed / stale revision 必須 no-op，不得重刷。
4. repeated authoritative revisions 必須維持「一個 commit 對應一次 visible refresh」，不得漏刷或雙刷。
5. 禁止 widget-to-widget 抄值作同步；View refresh / destroy / recreate 不得寫回 manufacturing state、available parts、CornerType、Fold Profile、holes/features 或 persistence payload。
6. 驗 dual-view parity 不得只比 Final Material / DXF / Save→Reload；還必須有 visible refresh、hidden no-refresh、replayed revision no-op、repeated revisions、View recreate zero-mutation 的證據。
7. 發現「資料正確但畫面仍舊」時，先查 authoritative commit → invalidate/apply → visible View refresh orchestration，不得另建第二套 geometry/state 當 workaround。


### ISSUE100_LEGACY_2D_ENTRY_RETIREMENT_RULE

退役 UI 入口時，先切斷「使用者可達入口 / navigation authority / identity authority」，不得因名稱看似 legacy 就盲刪仍被新入口共用的 renderer/helper/callback state。若暫留 compatibility state，必須 user-unreachable、non-navigation、non-manufacturing-authority，並以 runtime navigation + capability preservation 驗收。
