# T16 Receiving Authoritative Placement Contract

## Contract
Receiving family coordinate -> outer Door placement -> inner-door panel/frame placement -> divider placement.

- Family coordinate owner supplies front skin, outer-door plane, outward/inward vectors.
- Door X/Y comes only from authoritative Door layout topology.
- Inner panel/frame X/Y comes only from the owning outer Door finished face and family insets.
- Divider placement remains topology-boundary owned.
- 2D, 3D, collision consume `resolve_assembly_placement()`; Receiving consumers do not recreate `depth/2`, origin fallback, or 50px offsets.
- T16 establishes the relative placement seam. T17 owns the configurable 80 mm inward datum.

## Fresh Receiving reference
For W=800 H=1600 D=350 T=2 FW=29 and layout 800 x (1100,500):
- body front skin Z=174
- outer Door reference plane Z=175
- upper Door center=(0,250,175)
- upper inner panel center=(0,225,175) before T17 inward offset
- top frame=(0,730,175)
- left frame=(-313.5,225,175)
- right frame=(313.5,225,175)
- horizontal divider=(0,-300,0), world material stays within box-body depth.
