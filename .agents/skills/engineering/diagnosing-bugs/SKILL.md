---
name: diagnosing-bugs
description: /debug and diagnosing-bugs route for bugs or performance regressions; read the real source code, call chain, CURRENT specifications and tests before any edits, then reproduce RED, fix and verify GREEN.
whd_doc_role: CURRENT
whd_contract: diagnosing-bugs
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Diagnosing Bugs

## RUNTIME_CAPABILITY_FALLBACK

Use the tightest loop the current runtime can actually execute. Specialized browser/debugger/subagent helpers are optional; when absent, build the repro and diagnosis as an **inline fallback** with available commands/tests. If a human must perform a step, generate a self-contained checklist or small temporary script from current evidence; do not depend on a missing supporting template.

A discipline for hard bugs. Skip phases only when explicitly justified.

When exploring the codebase, read `CONTEXT.md` (if it exists) to get a clear mental model of the relevant modules, and check ADRs in the area you're touching.

## Phase 0: SOURCE_READ_BEFORE_MUTATION_V1（`/debug` 前置必讀）

`/debug` is an explicit invocation alias of this **existing** `diagnosing-bugs` Skill, not a second independent debug implementation. It does not grant local/RC/DC execution permission.

**Before changing product source code, tests, fixtures or expected values:**

1. Fresh-read official `X` `AGENTS.md`, the exact working ref/HEAD, the actual implicated source modules, and the authoritative CURRENT requirements (including relevant diagrams / CSV / JSON / DXF and customer-approved rules). Search hits, file names, issue summaries and a previous agent's claims are **not** proof that a file has been read.
2. Follow and inspect the **real entrypoint → caller/callee → intermediate coordinate and state transforms → 2D/3D/collision/manufacturing/output** path. Read complete affected functions and all necessary adjacent code before deciding what to replace; inspect existing regression tests, version differences, and product data. Scope reading to relevant modules rather than blindly opening the entire repository.
3. Show a concise `SOURCE_READ_EVIDENCE` summary: source ref/HEAD, code paths and functions actually read, document/data authority, factual symptom and RED-capable test plan, and proposed minimal touched paths. Reading a passing test, existing screen output or code-derived constant never establishes manufacturing truth.
4. If required sources or a normative rule cannot be verified, return `SOURCE_READ_PRECONDITION_FAILED`. Continue read-only investigation and ask about genuinely missing domain authority only; **do not patch product code or fabricate regression expected values**. Once evidence is available, proceed directly within the already-authorized scope.

This prerequisite is for **source grounding**, not permission to speculate about the fix. Next build a targeted test that fails on the user's *actual* symptom (Phase 1/2) before attempting a repair. A GUI crash being absent is not proof that collision, alignment or geometry was fixed.

## Redact

This skill has you show commands, outputs and captured artifacts. **Redact every secret first**: write `<REDACTED>` in its place. Build loops against env vars, so the credential stays in the environment rather than in what you show. Captured artifacts carry auth headers: quote only the lines that carry the signal.

If the redacted output is not enough to diagnose the bug, say so and ask the user.

## Phase 1: Build a feedback loop

**This is the skill.** Everything else is mechanical. If you have a **tight** pass/fail signal for the bug (one that goes red on _this_ bug), you will find the cause; bisection, hypothesis-testing, and instrumentation all just consume it. If you don't have one, no amount of staring at code will save you.

Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to give up.**

### Ways to construct one, in roughly this order

1. **Failing test** at whatever seam reaches the bug: unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright / Puppeteer) that drives the UI and asserts on DOM/console/network.
5. **Replay a captured trace.** Save a real network request / payload / event log to disk; replay it through the code path in isolation.
6. **Throwaway harness.** Spin up a minimal subset of the system (one service, mocked deps) that exercises the bug code path with a single function call.
7. **Property / fuzz loop.** If the bug is "sometimes wrong output", run 1000 random inputs and look for the failure mode.
8. **Bisection harness.** If the bug appeared between two known states (commit, dataset, version), automate "boot at state X, check, repeat" so you can `git bisect run` it.
9. **Differential loop.** Run the same input through old-version vs new-version (or two configs) and diff outputs.
10. **HITL guided loop.** Last resort. If a human must click, generate a self-contained numbered checklist or temporary script that captures the exact signal needed; do not depend on a repository template that may not exist. Captured redacted output feeds back into the loop.

Build the right feedback loop, and the bug is 90% fixed.

### Tighten the loop

Treat the loop as a product. Once you have _a_ loop, **tighten** it:

- Can I make it faster? (Cache setup, skip unrelated init, narrow the test scope.)
- Can I make the signal sharper? (Assert on the specific symptom, not "didn't crash".)
- Can I make it more deterministic? (Pin time, seed RNG, isolate filesystem, freeze network.)

A 30-second flaky loop is barely better than no loop; a 2-second deterministic one is tight, a debugging superpower.

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the trigger 100×, parallelise, add stress, narrow timing windows, inject sleeps. A 50%-flake bug is debuggable; 1% is not, so keep raising the rate until it's debuggable.

### When you genuinely cannot build a loop

Stop and say so explicitly. List what you tried. Ask the user for: (a) access to whatever environment reproduces it, (b) a redacted captured artifact (HAR file, log dump, core dump, screen recording with timestamps), or (c) permission to add temporary production instrumentation. Do **not** proceed to hypothesise without a loop.

### Completion criterion: a tight loop that goes red

Phase 1 is done when the loop is **tight** and **red-capable**: you can name **one command** (a script path, a test invocation, a curl) that you have **already run at least once** (show the invocation and its output, redacted), and that is:

- [ ] **Red-capable**: it drives the actual bug code path and asserts the **user's exact symptom**, so it can go red on this bug and green once fixed. Not "runs without erroring"; it must be able to _catch this specific bug_.
- [ ] **Deterministic**: same verdict every run (flaky bugs: a pinned, high reproduction rate, per above).
- [ ] **Fast**: seconds, not minutes.
- [ ] **Runnable in the available environment**: unattended when possible; if a human is unavoidable, use the self-contained HITL guide described above and keep the pass/fail signal explicit.

Phase 0 source/spec reading is mandatory. If, after that grounding, you keep reading code only to justify a speculative patch instead of constructing a real red-capable check, **stop**. No red-capable command, no Phase 2.

## Phase 2: Reproduce + minimise

Run the loop. Watch it go red as the bug appears.

Confirm:

- [ ] The loop produces the failure mode the **user** described, not a different failure that happens to be nearby. Wrong bug = wrong fix.
- [ ] The failure is reproducible across multiple runs (or, for non-deterministic bugs, reproducible at a high enough rate to debug against).
- [ ] You have captured the exact symptom (error message, wrong output, slow timing) so later phases can verify the fix actually addresses it.

### Minimise

Once it's red, shrink the repro to the **smallest scenario that still goes red**. Cut inputs, callers, config, data, and steps **one at a time**, re-running the loop after each cut, and keep only what's load-bearing for the failure.

Why bother: a minimal repro shrinks the hypothesis space in Phase 3 (fewer moving parts left to suspect) and becomes the clean regression test in Phase 5.

Done when **every remaining element is load-bearing**: removing any one of them makes the loop go green.

Do not proceed until you have reproduced **and** minimised.

## Phase 3: Hypothesise

Generate **3–5 ranked hypotheses** before testing any of them. Single-hypothesis generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state the prediction it makes.

> Format: "If <X> is the cause, then <changing Y> will make the bug disappear / <changing Z> will make it worse."

If you cannot state the prediction, the hypothesis is a vibe: discard or sharpen it.

**Show the ranked list to the user before testing.** They often have domain knowledge that re-ranks instantly ("we just deployed a change to #3"), or know hypotheses they've already ruled out. Cheap checkpoint, big time saver. Don't block on it; proceed with your ranking if the user is AFK.

## Phase 4: Instrument

Each probe must map to a specific prediction from Phase 3. **Change one variable at a time.**

Tool preference:

1. **Debugger / REPL inspection** if the env supports it. One breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and grep".

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup at the end becomes a single grep. Untagged logs survive; tagged logs die.

**Perf branch.** For performance regressions, logs are usually wrong. Instead: establish a baseline measurement (timing harness, `performance.now()`, profiler, query plan), then bisect. Measure first, fix second.

## Phase 5: Fix + regression test

Write the regression test **before the fix**, but only if there is a **correct seam** for it.

A correct seam is one where the test exercises the **real bug pattern** as it occurs at the call site. If the only available seam is too shallow (single-caller test when the bug needs multiple callers, unit test that can't replicate the chain that triggered the bug), a regression test there gives false confidence.

**If no correct seam exists, that itself is the finding.** Note it. The codebase architecture is preventing the bug from being locked down. Flag this for the next phase.

If a correct seam exists:

1. Turn the minimised repro into a failing test at that seam.
2. Watch it fail.
3. Apply the fix.
4. Watch it pass.
5. Re-run the Phase 1 feedback loop against the original (un-minimised) scenario.

## Phase 6: Cleanup

Required before declaring done:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop)
- [ ] Regression test passes (or absence of seam is documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` the prefix)
- [ ] Throwaway prototypes deleted (or moved to a clearly-marked debug location)
- [ ] The hypothesis that turned out correct is stated in the commit / PR message, so the next debugger learns

## Domain uncertainty: ask before inventing

For WHD mechanical/manufacturing bugs, an unknown domain rule is **not** a hypothesis to silently promote into production.

- If the correct CornerType, mating face, dimension space, fixed-vs-variable status, or parameter ownership is not explicitly supported by authoritative project data, **ask the user** before writing the spec or fix.
- Do not infer product truth from current code behavior, a passing/failing test, a collision probe, a screenshot, or a convenient existing enum.
- When the user has already named an existing model (for example `CROSS / 十字截角`), test whether that model plus parameters can represent the requirement before proposing a new type.
- Diagnosis may continue read-only while waiting for clarification, but production/Registry/AI-library writes must not encode the unresolved guess.

## Durable correction propagation

When the user corrects the diagnosis, clarifies a product rule, or identifies a repeatable failure mode, do not leave the correction only in chat.

- Proactively update the directly relevant project Skill plus the global AI pitfall library.
- Also update the relevant domain pitfall/spec/Registry guidance and owning Issue/PR when the correction changes future implementation decisions.
- Search for conflicting durable guidance and mark it `SUPERSEDED / REVOKED`; do not leave contradictory authorities active.
- Do not wait for the user to say "add this to the skill / AI library" again.
- Keep transient run IDs, temporary measurements, and one-off progress out of durable knowledge unless they establish a reusable rule.
- Re-read the remote file after writing so the update is proven durable.

## WHD bug-fix execution and delivery boundary

本 Skill 只提供診斷與 RED→GREEN 方法，**不會授權 DC／本機施工**。每次修復依 GitHub `localX` 最新 HEAD 的 `AGENTS.md` 與相應 CURRENT Skill 判斷；正式 X 的舊工作規則不可反向覆蓋：

1. `/派工`：由 GitHub／排程／雲端執行器以最新 `localX` 建工作分支，完成 BUILD／TEST／COMMIT／PR／CI；PR base=`localX`，exact HEAD CI GREEN 後預設 `GITHUB_LOCALX_FIRST` 合回遠端 `localX`，readback 並標 Windows 同步待辦。不可自動連 RC／DC／CoreELEC。
2. `/接手`：僅使用者當次明確指示，才允許 RC → `whd-dev:/workspace/whd` 的產品施工、測試與交付。
3. 純非產品治理／技能／治理專用測試：同樣以 GitHub `localX` 建分支並 PR 合回 `localX`，使用治理專項 CI；不得按舊治理直送 X 的指示 bypass `localX`。正式 X 發布仍需人工驗收與當次 `/推推`。
4. 每次記錄診斷重現證據、規格來源、source/tested SHA、exact diff、適用測試及最終回讀。CI 失敗必須回到合法施工路線修復並重新驗證新 SHA；target/touched-path drift 應重驗。
5. 舊 `WORKSPACE_DELIVERY`、Drive/shared-zero、claim／lease／工作槽及 `FINALIZE` 交易要求已退役，不能當作啟動或交付前置；更不能以此放寬平台安全審查。不得直接 patch 正式 X 或 `main`。

