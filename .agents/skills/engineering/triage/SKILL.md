---
name: triage
description: Review a specifically scoped WHD GitHub Issue/PR for classification, reproducibility and next action; use existing tracker labels only when authorized, without creating a parallel ticket process.
disable-model-invocation: true
whd_doc_role: CURRENT
whd_contract: triage
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Triage

## RUNTIME_CAPABILITY_FALLBACK

### WHD_LOCALX_TRIAGE_SOURCE_AND_SCOPE_V1

- 先讀 GitHub `localX` **最新 exact HEAD** 的 `AGENTS.md`、本 CURRENT Skill、AI Library 09 Authority Map，並以指定的 GitHub Issue／PR 最新內容、相關 CURRENT owner 與程式證據判斷。正式 X 或歷史 `main` 不能代替日常 triage 來源。
- 使用者明確要求檢查／整理某 Issue、PR，或同一已授權工單的持續核對時，用**已連線的 GitHub read 工具**直接回讀，無須已退役的 `USER_EXPLICIT_REMOTE`、`WORKSPACE_DELIVERY` 交易憑證或第二次 remote-read 授權。單獨 bare `#42` 不足以確認 repository；需核對真實 repo 與 issue/PR 身分。
- **查核預設唯讀**。既有工單授權範圍內、使用者明確要求的 label／comment／close 才可寫入；不能因「整理／盤點」擅自改狀態、開新 Issue、建立新標籤、寫 rejected-feature 庫、或觸碰其他工單。寫入前核對 target 身分、使用者決定與實際 GitHub 工具權限，失敗就如實回報。
- 現有 GitHub Issues／PR 是唯一可驗證的 tracker；不存在的外部 tracker config、subagent、executor、本機 checkout 都不是前置。沒有本機執行器可做 source/diff review，但不得假稱已跑 pytest、GUI 或實機；標 `TARGETED_NOT_RUN`。GitHub 施工／合併仍依 `AGENTS.md`，正式 X 只由當次 `/推推` 發布。


Use the issue/PR tracker and runtime capabilities that actually exist. Parallel/subagent execution is optional; without it, the same executor performs verification, research, `深度質詢`, and `領域建模` as an **inline fallback**. Do not require an external setup Skill or retired English identity just to triage WHD work.

When the existing GitHub tracker already uses triage labels, use them as a **descriptive view**; do not invent a new WHD state machine or make new labels a delivery precondition.

For an explicitly named PR, read its real GitHub PR identity and attached code diff; for an Issue, read the real Issue identity. No external issue-tracker config is assumed to exist. A bare `#42` must be resolved against the user's actual repo/scope, never guessed.

When a triage comment is actually requested and authorized, write a clear evidence-based note on that existing Issue/PR; do not add mandatory boilerplate, separate process records or a new ticket merely to perform classification.
## Reference docs

- [AGENT-BRIEF.md](AGENT-BRIEF.md): how to write durable agent briefs
- [OUT-OF-SCOPE.md](OUT-OF-SCOPE.md): how the `.out-of-scope/` knowledge base works

## Roles

Two **category** roles:

- `bug`: something is broken
- `enhancement`: new feature or improvement

Five **state** roles:

- `needs-triage`: maintainer needs to evaluate
- `needs-info`: waiting on reporter for more information
- `ready-for-agent`: fully specified, ready for an AFK agent
- `ready-for-human`: needs human implementation
- `wontfix`: will not be actioned

For a PR, the same states read against the attached code: `ready-for-agent` means a brief is attached and an agent should take the next step on the diff; `ready-for-human` means it's ready for a human to merge.

If the current repository actually has a category/state label convention, preserve it. Missing labels, missing configuration or conflicting labels are diagnostic findings, **not** permission to introduce labels or force status transitions. Report unclear cases; do not mutate status without a scoped instruction.

These are canonical role names. Actual tracker labels may differ; discover the mapping from the tracker/project configuration that is really available. If no mapping exists, report that gap and use explicit state names rather than invoking a separate setup/governance system.

These state names are optional upstream examples, **not** a WHD mandatory process. Follow actual existing tracker values and the user's intended outcome; never add new state labels to make a sample flow work.

## Invocation

The maintainer invokes `/triage` and describes what they want in natural language. Interpret the request and act. Examples:

- "Show me anything that needs my attention"
- "Let's look at #42" (issue or PR)
- "Move #42 to ready-for-agent"
- "What's ready for agents to pick up?"

## Show what needs attention

Query the issue tracker and present three buckets, oldest first:

1. **Unlabeled**: never triaged.
2. **`needs-triage`**: evaluation in progress.
3. **`needs-info` with reporter activity since the last triage notes**: needs re-evaluation.

When PRs are in scope, include external PRs in these buckets and tag each line `[PR]` or `[issue]`. Discovery surfaces only *external* PRs (the tracker config defines who counts as external), so a collaborator's in-flight PR is not triage work. This filter is discovery-only; an explicitly named PR is always triaged regardless of author.

Show counts and a one-line summary per item. Let the maintainer pick.

## Triage a specific issue or PR

1. **Gather context.** Read the exact GitHub Issue/PR body, comments, labels, author and dates (for a PR also read the actual diff), then the relevant `localX` code/CURRENT authority. Check existing implementation and previously decided scope from the actual Issue history; consult `.out-of-scope/*.md` **only if this directory already exists**. Currently it is not part of the WHD source tree, so its absence is not a blocker and no directory should be created.

2. **Recommend or apply the already authorized action.** Explain category, evidence and recommended next step. For a read-only request, report findings; if the same request already explicitly authorizes an existing Issue/PR label/comment/close and its target is confirmed, perform that action without demanding a second instruction.

3. **Verify the claim.** Read the real implementation and independent CURRENT requirements; for a bug, seek a RED reproducer, for a PR compare exact GitHub head/base and test claims. Execute relevant tests **only in an authorized available executor**. With GitHub-only read capability, analyze source/diff and check actual CI; say `TARGETED_NOT_RUN` for tests not executed, never invent a checkout or treat CI queued as GREEN. A confirmed verification makes a much stronger agent brief.

4. **Deep interview (if needed).** Use canonical `深度質詢` to flesh out the request a round at a time; when domain terms settle, use canonical `領域建模` and update `CONTEXT.md`/ADRs when their gates are met. If no separate Skill loader exists, follow the canonical Skills inline.

5. **Apply the outcome:**
   - `ready-for-agent`: post an agent brief comment ([AGENT-BRIEF.md](AGENT-BRIEF.md)).
   - `ready-for-human`: same structure as an agent brief, but note why it can't be delegated (judgment calls, external access, design decisions, manual testing).
   - `needs-info`: post triage notes (template below).
   - For an **explicitly authorized** `wontfix` decision, close the existing issue with reason and readback:
     - **Already implemented**: the change already exists in the codebase. Point to where it lives; do **not** write to `.out-of-scope/` (that KB is for *rejected* requests, not built ones).
     - **Rejected (bug)**: give a polite explanation, then close.
     - **Rejected (enhancement)**: record the explicit decision in the existing Issue comment; only update an already-existing out-of-scope record if independently authorized. Do not create a new `.out-of-scope/` workflow ([OUT-OF-SCOPE.md](OUT-OF-SCOPE.md) is REFERENCE only).
   - `needs-triage`: apply the role. Optional comment if there's partial progress.

## Quick state override

If the user explicitly requests a specific existing GitHub Issue label change, verify the repo, Issue identity, label availability and scope, then act with the connected GitHub tool and read back. No second approval prompt, new label, or forced agent-brief creation; skip unrelated discovery.

## Needs-info template

```markdown
## Triage Notes

**What we've established so far:**

- point 1
- point 2

**What we still need from you (@reporter):**

- question 1
- question 2
```

Capture everything resolved during grilling under "established so far" so the work isn't lost. Questions must be specific and actionable, not "please provide more info".

## Resuming a previous session

If prior triage notes exist on the issue or PR, read them, check whether the reporter has answered any outstanding questions, and present an updated picture before continuing. Don't re-ask resolved questions.
