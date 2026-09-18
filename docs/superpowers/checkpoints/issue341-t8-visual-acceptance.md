# #341 / T8 visual acceptance checkpoint

- Production base: `97decd5f4a8e900d4ffd0cb64fbf5e371b3a5136`
- Branch: `qa/issue341-visual-acceptance-20260918`
- RED RUN: `35344095340` SUCCESS
- RED head: `779cb8d9ddb9ddc6a7d11b4bc055a2e5b6218cbb`
- GREEN harness commit: `f3761e89d08fd9b214cfbc154df076395fd14bdc`
- Product source drift: none; T8 is acceptance harness/evidence only.
- Required evidence: A geometry/reachability, B effective style/contrast, C screenshots/pixels/checklist.

## Harness retry

- `35344999798` / `35345030906`: harness-only failure before product execution — `ModuleNotFoundError: gui` from script path semantics.
- Fix commit: `ab5835e9b5d89f45d6d93414707179c33ff241a3`; repo root is now inserted into `sys.path` before importing product modules.
- Product source remains unchanged.
