# #341 / T8 visual acceptance v2 checkpoint

- Production base: `d28cd145811f131fe2714267a7a33d74267c40dd`
- Fresh branch: `qa/issue341-visual-acceptance-v2-20260918`
- Original T8 RED: `35344095340` SUCCESS.
- First A/B run passed but C-layer manual review found medium/large left-pane clipping and CJK tofu.
- Remediation #343 accepted: final RUN `35345795970`, **22 PASS**, protected drift GREEN.
- v2 must re-run A/B/C from remediated production and produce fresh screenshots before #341 closure.
- Product source changes are forbidden on this acceptance branch.
