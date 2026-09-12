---
name: handoff
description: Compact current work into a durable handoff so another session or agent can continue without relying on hidden conversation state.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

# Handoff

## RUNTIME_CAPABILITY_FALLBACK

Prefer durable project state that the next executor can actually read: owning Issue/PR, checkpoint/journal, spec, ADR, commit/branch, and repo-local handoff when the project requires one. An OS temporary directory is only an optional ephemeral **inline fallback**, not a hard requirement.

Write a concise handoff that summarizes only context not already captured elsewhere. Reference existing artifacts by path/URL instead of duplicating specs, plans, ADRs, issues, commits or diffs.

Include a `Suggested Skills` section only when useful. Name each Skill by its **canonical identity** and path/classification where known; do not instruct the next agent to use a generic product-specific loader. The next runtime decides how to load or apply it. For WHD, active status comes from `.agents/skills/skill_catalog.json` and only `canonical` is active by default.

If the runtime provides native compaction/handoff support, it may be used. Otherwise the same executor writes the handoff inline. Never claim a fresh/background agent was started unless the runtime actually started one.

Redact secrets, credentials, account identifiers, and unnecessary personal information. If the user supplied a next-session focus, make that the resume target and include the exact next safe action, blockers, branch/HEAD and active remote QA lock when relevant.
