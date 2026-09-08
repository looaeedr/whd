---
name: to-tickets
description: Use when a plan, spec, issue, or conversation needs to be decomposed into implementation tickets or tracker issues.
disable-model-invocation: true
---

# To Tickets

Break approved requirements into tracer-bullet tickets with explicit blocking edges. **Ticket boundaries are evidence-driven: first prove the requirements with executable REDs, then discuss those REDs with the user, and only after approval may ticket drafting begin.**

## Iron Rule

```text
NO TICKET BREAKDOWN BEFORE APPROVED REQUIREMENT-LEVEL RED EVIDENCE
```

The RED Gate is not a formality. RED evidence can reveal that several symptoms share one root contract and belong in one ticket, or that one apparent feature actually contains independent contracts and should be split.

## Process

### 1. Gather context

Read the current conversation, referenced spec/issue, relevant comments, project glossary, ADRs, **relevant project AI Library / 個人AI檔案庫 entries**, and existing code paths. At this stage collect **Requirements only**. Do not assign T-numbers, ticket titles, blockers, or issue boundaries yet.

### 1.1 AI Library traceability gate

For WHD/project work, AI Library is a mandatory engineering evidence source, not optional background context.

Before RED design:
- Search/read the relevant entries under `個人AI檔案庫/**` and record the **exact file paths** used.
- At minimum, include the project SOP/pitfall entries that materially constrain the task; do not merely say "AI 庫已讀".
- Build a short **Requirement Authority** note distinguishing:
  1. current user-approved requirement/spec;
  2. code/test behavior;
  3. AI Library historical guidance.
- **Authority rule:** a current explicit user-approved requirement overrides stale/conflicting AI Library content. Never silently let old AI Library text overwrite the current requirement.
- When a conflict, newly discovered pitfall, or durable invariant is found, mark **AI Library Writeback: REQUIRED** and name the target AI Library file(s) or the intended knowledge category.

### 2. Explore the codebase

Trace the existing public seams and find where each Requirement can be observed through real behavior. Prefer existing tests or public APIs; add the smallest test/probe needed when no executable seam exists. Before user RED approval, the only allowed project changes are RED tests/probes and their evidence—not production code, tickets, or tracker issues.

### 3. RED Gate — write, run, and argue the evidence first

Build a requirement-level matrix before any ticket drafting:

| RED ID | Requirement | RED command/nodeid | expected failure | observed failure | interpretation | user decision |
|---|---|---|---|---|---|---|

For every Requirement:

1. Write or identify an executable RED test/probe.
2. **實際執行** the exact `RED command/nodeid`.
3. Confirm it is a **正確失敗**: execution reaches the intended behavior seam and fails because the Requirement is not satisfied.
4. Record `expected failure` and `observed failure` verbatim enough to distinguish the contract violation from harness noise.
5. Present the matrix to the user and perform **使用者逐條論證**: discuss whether the RED matches the requirement, whether multiple REDs share a root contract, and whether any RED is testing the wrong seam.
6. Record the `user decision` for every RED. **使用者核准** all relevant REDs before continuing.

The following **不能算 RED**:

- 環境錯誤, DISPLAY/Xvfb/network/tooling failure
- 語法錯誤, import/collection error
- broken fixture or mock setup
- timeout without a complete assertion/error proving the requested behavior
- missing test file/path

If a supposed **RED 已是 GREEN**, **不得建立修復工單** from it. First **重新確認測試 seam**, existing implementation, or whether the reported symptom belongs to another path.

### 3.1 Fail closed before RED approval

If **RED 未核准**:

- **不得開始拆工單** or assign T-numbers/titles/blockers;
- **不得建立 issue** on GitHub, Linear, or another tracker;
- **不得寫入 local ticket** under `.scratch/**` or elsewhere;
- do not transition a dispatch workflow to an implementer based on an unapproved breakdown.

Only after the requirement RED matrix is approved **才可開始草擬工單**.

### 4. Draft vertical slices

Now use the approved RED evidence to choose ticket boundaries. Each ticket must be a narrow but complete tracer-bullet slice that is independently verifiable.

Rules:

- Same root contract + inseparable implementation/verification usually belongs in one ticket.
- Independent contracts with separate GREEN conditions should remain separate tickets.
- Each ticket fits a fresh context window and declares only genuine blockers.
- Wide mechanical refactors may use expand–migrate–contract instead of forced vertical slicing.
- **每張工單** must include `Approved RED IDs` and reference the **已核准的 RED** evidence that defines its acceptance boundary.
- **每張工單** must include `Requirement Authority` and `AI Library References` with exact paths; `AI Library References` may not be omitted.
- **每張工單** must include `AI Library Writeback`: either exact target file(s)/knowledge to update, or `None — no durable knowledge change` with a reason.
- If current requirements supersede stale AI Library guidance, at least one closing/acceptance ticket must own the required writeback; the breakdown is incomplete without that ownership.

### 5. Quiz the user on the breakdown

Present the proposed breakdown as a numbered list showing:

- Title
- Approved RED IDs
- Requirement Authority
- AI Library References
- AI Library Writeback
- Blocked by
- What it delivers

Ask whether granularity, root-contract grouping, and blocking edges are correct. Iterate until the user explicitly approves the **ticket breakdown**. This is a second approval gate, separate from RED approval.

### 6. Publish the tickets

Publish only the approved breakdown.

- **Local files** → one file per ticket under `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.
- **GitHub** / Linear / another tracker → one issue per approved ticket, blockers first, using native blocking/sub-issue relationships when available.

Do NOT close or modify a parent issue unless explicitly requested.

### 6.1 GitHub owning Issue publication gate

For a GitHub-backed project, an approved ticket is **not dispatched** until its real GitHub Issue exists and has been read back.

Required sequence:

1. Create one GitHub Issue per approved ticket, blockers first.
2. Read the tool response using its actual schema; obtain the real `issue_number` and canonical URL.
3. Read the created Issue back from GitHub and verify title/body/dependencies.
4. Record the GitHub Issue number/URL in the dispatch state/journal.
5. Only then may the dispatch skill transition to Implementer.

`.scratch/<feature>/issues/*.md` is permitted as a local mirror, checkpoint, or durable planning artifact, but **it is never the owning tracker item when GitHub is the project tracker**.

The following do **not** count as an owning Issue:

- a T-number in chat;
- a Markdown ticket file under `.scratch/**`;
- a work branch;
- a commit message;
- a QA workflow;
- a checkpoint ZIP.

If work is discovered to have started without the owning Issue, create the Issue immediately with a visible **Retroactive provenance / created after work started** note. Include actual branch/commit/run evidence and do not backdate or imply the Issue existed before the work.

## Ticket Template

```markdown
# <NN>: <Ticket title>

**What to build:** user-visible/end-to-end behavior.

**Approved RED IDs:** R1, R2

**Requirement Authority:** current user-approved spec / issue / exact contract.

**AI Library References:** exact `個人AI檔案庫/**` paths used.

**AI Library Writeback:** exact target path(s) + intended update, or `None — no durable knowledge change`.

**Blocked by:** None, or exact blocking tickets.

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
```

## Red Flags

| Rationalization | Reality |
|---|---|
| "The spec is clear; I can split first and add tests later." | That bakes an unproven architecture into ticket boundaries. Run RED first. |
| "I know these two symptoms are separate." | Prove whether they share one failing contract before splitting. |
| "The test errors, so that's a RED." | Harness/setup failure is not requirement evidence. |
| "The test is already green, but we still need a bug ticket." | Re-check the seam; do not invent a repair ticket without a failing contract. |
| "I'll create draft GitHub issues and revise them after approval." | Creating issues is already publishing. Fail closed until both approval gates pass. |
| "I read the AI Library earlier, so I don't need to cite it in the tickets." | Reading is not traceability. Every ticket must carry exact AI Library references and explicit writeback ownership/None reason. |
| "The AI Library says X, so it overrides the user's new confirmed spec." | Wrong authority order. Current explicit user-approved requirements win; record the conflict and require AI Library writeback. |
| "A `.scratch` ticket exists, so GitHub publication can wait." | A local ticket file is only a mirror. In a GitHub-backed project, owning Issues must exist and be read back before dispatch/production work. |
| "We can add the GitHub Issue after implementation and treat it as if it was always there." | No. If retroactive creation is unavoidable, label it explicitly as retroactive provenance with actual commits/runs; never falsify chronology. |
