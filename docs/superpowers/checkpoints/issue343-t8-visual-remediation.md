# #343 T8 visual remediation checkpoint

- Base production: `97decd5f4a8e900d4ffd0cb64fbf5e371b3a5136`
- Blocking visual evidence: #341 RUN `35345120562` / branch-head `35345148322`
- C-layer manual FAIL: medium/large left workspace clipping; Matplotlib Traditional-Chinese missing-glyph boxes in Xvfb evidence.
- Scope: presentation only.

## GREEN candidate

- Candidate: `9d823aa299f059bb05df38fca83bf49a5932aa2f`
- Left workspace width now follows text-scale factor while preserving the right viewport.
- Shared Matplotlib theme now declares cross-platform Traditional-Chinese capable font fallbacks.

- Drift-gate harness corrected at `436c7e9e8130931608a458fa1b369d99968ad0ae` to allow only this issue's checkpoint evidence path in addition to the presentation files/tests/workflow.
