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

Read the current conversation, referenced spec/issue, relevant comments, project glossary, ADRs, and existing code paths. At this stage collect **Requirements only**. Do not assign T-numbers, ticket titles, blockers, or issue boundaries yet.

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

### 5. Quiz the user on the breakdown

Present the proposed breakdown as a numbered list showing:

- Title
- Approved RED IDs
- Blocked by
- What it delivers

Ask whether granularity, root-contract grouping, and blocking edges are correct. Iterate until the user explicitly approves the **ticket breakdown**. This is a second approval gate, separate from RED approval.

### 6. Publish the tickets

Publish only the approved breakdown.

- **Local files** → one file per ticket under `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.
- **GitHub** / Linear / another tracker → one issue per approved ticket, blockers first, using native blocking/sub-issue relationships when available.

Do NOT close or modify a parent issue unless explicitly requested.

## Ticket Template

```markdown
# <NN>: <Ticket title>

**What to build:** user-visible/end-to-end behavior.

**Approved RED IDs:** R1, R2

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
