---
name: research
description: Investigate a question against high-trust primary sources and capture cited findings. Use current-session tools by default; delegate only when the runtime actually provides a suitable background/subagent capability.
---

# Research

## RUNTIME_CAPABILITY_FALLBACK

Research must work in the runtime that actually exists. If a real background/subagent capability is available and useful, it may be used as an optimization; it is never required. Without it, the same executor performs the research **inline fallback** in the current session.

1. Investigate the question against primary/high-trust sources: official docs, source code, specs, first-party APIs, project authority files, or other sources that own the claim.
2. Follow each material claim back to its source; do not promote a secondary summary over the owning authority.
3. Capture findings in the artifact/location the current task actually requires. If the repo has a durable research-note convention, use it; otherwise keep the result in the current response unless a file is explicitly useful or requested.
4. Cite or link the evidence using the capabilities of the current runtime. Never claim a source, background worker, or command was used unless it actually was.
5. For WHD project work, project canonical authority and AI Library rules outrank generic external guidance.
