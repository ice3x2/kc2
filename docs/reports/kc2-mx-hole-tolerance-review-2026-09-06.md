# MX hole and mask manufacturing review

Requirements: CON-ARCH-004 AC-3/AC-8/AC-10; CON-ARCH-007.

JLCPCB's published [PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities), checked 2026-09-06, specify ordinary through-hole tolerance +0.13 / -0.08 mm, hole position tolerance +/-0.05 mm, and nominal 1.60 mm board thickness +/-10%. Its mask process supports 1:1 pad/mask openings. For 2-layer 1 oz PTH lands it recommends a 0.25 mm annular ring. These are supplier capabilities, not incoming measurements or a socket fit guarantee.

Derived from those published limits:

| Design | Finished hole range | Conservative nominal-copper annular ring at maximum hole and 0.05 mm offset |
|---|---|---|
| MX 1.60 mm drill / 2.50 mm minor land axis | 1.52–1.73 mm | 0.335 mm |
| U1 0.95 mm drill / 1.80 mm minor land axis | 0.87–1.08 mm | 0.310 mm |

The selected socket barrel is nominally 1.45 mm, leaving only 0.07 mm diametral space at the smallest permitted finished hole **before unknown socket OD tolerance**. The seller drawing does not publish that tolerance or MX flat-blade contact limits. Do not claim worst-case fit from nominal values alone.

Nominal open-bottom socket projection below the PCB is 1.20 mm. Using only board-thickness variation gives 1.04–1.36 mm, before socket/flange tolerances, solder, and switch-pin projection. The housing must not use 1.20 mm as a proven maximum.

No fabrication files were produced by this review; order readiness remains unproven.
