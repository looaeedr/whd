# Misc

Tool-specific or rarely used helpers.

> Navigation only. `.agents/skills/skill_catalog.json` owns classification. `misc/**` defaults to `tool-specific`; an explicit higher-priority catalog rule is required to promote a WHD canonical exception.

## tool-specific navigation

- **[git-guardrails-claude-code](./git-guardrails-claude-code/SKILL.md)**: Claude Code-specific git hooks; not WHD canonical governance.
- **[migrate-to-shoehorn](./migrate-to-shoehorn/SKILL.md)**: TypeScript migration helper.
- **[scaffold-exercises](./scaffold-exercises/SKILL.md)**: Exercise scaffolding helper.
- **[setup-pre-commit](./setup-pre-commit/SKILL.md)**: JS/Husky pre-commit setup helper.

## WHD canonical override

- **[git-remote-sync-fallback](./git-remote-sync-fallback/SKILL.md)**: WHD project-local remote sync fallback；catalog 明確 override 為 `canonical`。

檔案存在不代表 active canonical；以 catalog classification 為準。
