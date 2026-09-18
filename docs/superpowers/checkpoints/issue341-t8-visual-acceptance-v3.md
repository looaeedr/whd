# #341 T8 visual acceptance v3

- Production base: `6b04fb2bb72d9c251c979167530dee04ab4a372e`
- Prior v2 machine GREEN: `35346311075`, but manual C-layer review found medium/large clipping.
- #343 second remediation accepted and production now uses reviewed left-width floors:
  - small: 338
  - medium: 430
  - large: 480
- v3 must produce fresh real-Tk A/B/C evidence and fresh screenshots.
- Manual screenshot review remains mandatory before #341 closure.

## Run identity trigger

- Acceptance harness commit: `95ff11dd9cd80ef0430e79c138e3ad267b23d1f9`
- This checkpoint exists only to trigger a concrete T8 v3 RUN identity; product source is unchanged.
