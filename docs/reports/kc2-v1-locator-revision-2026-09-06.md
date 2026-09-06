# V1 shared locator revision

Requirements: `CON-ARCH-004`, `CON-ARCH-006`. This report is implementation and digital evidence, not fabrication approval or socket contact qualification.

The previous circular 1.70 mm holes at local X=+/-5.08 mm cannot contain the uncut official Choc V1 locator posts (diameter1.80 mm, local X=+/-5.50 mm). A nominal shared 2.30 x2.00 mm slot was rejected: [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities) specify non-plated slot dimensional tolerance +/-0.20 mm, which makes this candidate insufficient even before positional errors. No overlapping duplicate drills were used.

## Implemented geometry

- Both locator holes on all70 switches: single copper-free circular NPTH diameter2.60 mm at local X=+/-5.45 mm,Y=0. Existing MX locator-hole nominal envelopes remain contained.
- MX electrical pad2: unchanged drill center(-3.81,-2.54), unchanged diameter1.60 drill and2.50 x3.20 mm oval, rotated45 degrees locally so its positive-Y major-axis endpoint leans toward positive X. Pad1 remains unchanged.
- Oval copper area remains approximately6.6587 mm2, with minimum nominal drilled annulus0.45 mm. Both mask openings and no paste remain intact. No reduction in solderable area, net changes, switch movement, controller/service changes, or stabilizers.
- Exact actual KiCad polygon extraction from both serialized boards reports all70 minimum locator-hole-to-MX-copper distances >=0.419502 mm. The previous unrotated pad with the selected new hole would have only0.1860 mm; rotation fixes this without custom copper trimming.

## Dimensional bounds

The archived [official CPG135001D02 drawing](software-audit-20260906/reference-v1-CPG135001D02.pdf) supplies nominal V1 post diameter1.80 mm and general tolerance+/-0.10 mm. A deliberately conservative calculation uses diameter1.90 mm and independent post position+/-0.10 mm on each axis, plus board hole position+/-0.05 mm. [JLCPCB's NPTH guide](https://jlcpcb.com/blog/npth-design-guide), dated2026-07-22, states approximately+/-0.08 mm mechanical-hole tolerance. Under those specified bounds, the2.52 mm minimum finished hole retains minimum radial containment margin0.060 mm for V1. This assumes the switch central datum is aligned to the board; it does not absorb unbounded printed-ring error or assert socket engagement.

Nominal preserved MX diameter1.70 hole envelope at5.08 mm is contained with0.080 mm margin. Exact selected3-pin TTC has no side posts; this is preserved generic5-pin geometric support, not an invented TTC post tolerance.

## Routing and verification

The actual KiCad CLI initial candidates had40 left/52 right violations before routing. Local obstacle-aware repair at0.301 mm clearance produced876 left/1089 right track/via items. No project clearance was weakened. The existing70 lower-housing load-support keepouts (post radius1.20 +copper clearance0.30 mm, board-coordinate records) were checked against all new B.Cu tracks and vias: zero overlaps on both sides.

Fresh canonical KiCad DRC after promotion: left/right0 errors,0 warnings,0 unconnected. Exact library/pad traceability and revised embedded descriptions were retained. Geometry verifier signatures were strengthened to check oval orientation, with a mutation test proving that reverting pad2 to0 degrees is rejected. Generation and route replay use the current canonical footprint and source-bound snapshot.

Evidence working directory: `.codex-tmp/v1-round45-candidate-e/`, including `left-canonical-drc.json`, `right-canonical-drc.json`, `actual-copper-clearance.json`, and `canonical-before/` backups. Replaced boards and route snapshot are backed up there; no historical draft tree was modified.

Post-receipt physical insertion/contact/printing tests remain pending. First-order output regeneration and full independent component/circuit/mechanical review are still separate release tasks.

## Revised first-order output checker

`OPS-ARCH-007` packaging reads new raw outputs only from `hardware/kicad/fabrication_review/v1-recess-20260906-r3`; old raw and sealedr2 outputs are not overwritten or relabeled. Manual BOM now identifies the selected TTC Bluish White42gf3-pin listing, mutually exclusive ChocV1-with-ring/V2 alternatives and the recessed-lid7.5 mm screw contract. The fabrication profile names the round-NPTH tolerance assumptions and source rather than claiming a measured supplier guarantee.

Rotated MXpad2 is actually plotted as KiCad's `HorizOval` aperture macro. The new checker validates its complete primitive sequence (rounded thick line plus two end circles), diameter and both end-center coordinates against the actual board pad orientation. Macro-name reuse, missing end-circle primitive and wrong diagonal fail, even if nominal dimensions remain unchanged. Existing orthogonal U1/MX ovals are checked as the same capsule geometry; physically equivalent180-degree endpoint ordering is accepted. Fresh `inspect_side` on both new raw outputs returns errors[].

TDD evidence:6 V1 locator/orientation tests pass;4 new release-identity/BOM/capsule tests pass. The combined existing11 first-order gate +8 report-semantics +4 new release tests reports23 tests PASS in12.132 seconds (`.codex-tmp/v1-round45-candidate-e/package-tests.log`; PowerShell's native-stderr wrapper status is not the unittest result). No fabrication ZIP was built by this subtask.
