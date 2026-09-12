---
name: wizard
description: Generate a guided human-run procedure or script for steps only a human can perform. Use for credentials, dashboards, manual migrations or cutovers; do not invoke for steps the agent can safely perform itself.
---

# Wizard

## RUNTIME_CAPABILITY_FALLBACK

This Skill is self-contained. It does not require a bundled template. If bash/script tooling is available, author a small procedure-specific script inline; otherwise produce an executable human checklist. The **inline fallback** must preserve confirmation gates, secret redaction, idempotence where possible, and explicit irreversible-action warnings.

## Process

1. **Scope the procedure.** Read the repo/config first. List only steps the human truly must perform and every value produced. Never ask the human to do something the current runtime can already do safely.
2. **Map each stage.** Give concrete URLs/commands/fields only when verified from current docs or UI evidence. Do not invent third-party dashboard steps.
3. **Author the guide.** When a script helps, build it directly with ordinary shell primitives: numbered stages, hidden secret input, explicit confirmations, idempotent file updates, and clear output destinations. Do not depend on a missing repository template or helper library.
4. **Protect secrets.** Never echo credentials into chat/logs. Prefer environment variables or the platform's native secret store when available.
5. **Verify.** Run syntax/static checks only if those tools and a script actually exist. Otherwise statically trace every stage. Do not run human-only steps end-to-end on the user's behalf.
6. **Hand off.** Tell the human exactly how to execute the guide. Keep it ephemeral unless the user wants a repeatable repo artifact.

If a required external capability is unavailable and cannot be replaced safely, state the precise gap instead of fabricating a command or UI path.
