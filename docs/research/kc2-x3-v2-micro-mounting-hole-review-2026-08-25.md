# KC2 X3 V2 Micro Mounting Hole Review — 2026-08-25

## Summary

This document records the five independent reviews requested before adding mounting holes to the plateless KC2 X3 V2 PCB and its nominal 2.50 mm lower housing.

> **2026-09-01 supersession:** All P1/P2 counts, coordinates and recommendations below are historical. The active source is `CON-ARCH-006` P3: 8 left / 9 right at the exact SRS coordinates with 31/39 `2.40 mm` key supports.

The reviewed P1 snapshot used:

- M1.4 fastener envelope;
- 1.60 mm non-plated PCB clearance holes;
- eight mounting points on the left PCB and ten on the right PCB;
- conservative 3.00 mm maximum rounded pan/button-head diameter and 1.20 mm maximum head height until an exact tolerance drawing is locked;
- 3.00 mm vertical PH0 driver envelope;
- 3.00 mm minimum zero-gap housing support land at every mounting point;
- a nominal 1.10 mm-diameter by 2.80 mm-deep blind pilot-hole experiment extending into the local desk-contact column;
- all existing perimeter support and distributed interior supports retained.

The historical holes were not a substitute for that snapshot's load path. The active P3 design instead uses exact 31-left/39-right one-per-key `2.40 mm` coplanar supports while its 8-left/9-right mounting points provide clamp, provisional XY registration, anti-lift retention, and local zero-gap support/desk-contact columns. Actual full-pattern XY registration remains pending until the printed-fit coupon proves that the round-hole pattern seats without binding.

This is a digital prototype decision, not an order approval. The exact direct-plastic screw SKU, printed-pilot diameter, installation torque, stripping margin, repeated-service durability, keycap-skirt clearance, and 2 N deflection remain physical gates.

## SRS Linkage

- Active target: `kc2-x3-v2`
- Primary requirements: `CON-ARCH-004`, `CON-ARCH-006`
- Requirement state at review time: `Status=in_progress`, `Stability=evolving`
- SpecKiwi MCP was unavailable and the `speckiwi` CLI was not installed, so the checked-in SRS was inspected and updated directly.

## Five Independent Reviews

1. Switch, diode, controller, head, and driver-envelope review.
2. Micro-fastener, insert, PCBWay, and FDM manufacturing review.
3. Exhaustive PCB/housing feasible-region and Pareto placement search.
4. Structural load-path, clamp distribution, and anti-lift review.
5. Assembly, datum, serviceability, and procurement audit.

All five reviews agreed on these constraints:

- Kailh Deep Sea / Choc V2 and MX assembly modes must both remain valid.
- Keycaps may be removed for screw service, but installed switches must remain clear of the screw head and vertical driver path.
- Existing distributed supports must remain; screws alone are too sparse to control the typing-load span.
- M2 consumes too much head, driver, and support-land area.
- M1.6 can be made locally feasible but gives materially poorer right-side seam and anti-lift distribution.
- M1.4 is the only practical current-board candidate for robust distributed retention without moving switches or widening the outline.

## Official Part And Process Inputs

### Switch and socket envelopes

- Kailh PG1353 / Choc V2 public family drawing: 15.00 mm square upper body, 14.50 mm lower body, 5.00 mm center feature. The exact Deep Sea Mini storefront suffix should still be confirmed against a supplier drawing before order approval.
  - <https://www.kailhswitch.com/uploads/15927/files/CPG1353S01D01-01-data-sheet.pdf?rnd=494>
- Kailh `CPG135001S30` hot-swap socket: 13.15 +/-0.15 mm by 9.95 +/-0.15 mm and 2.20 +/-0.05 mm deep. The housing keeps the existing conservative 2.30 mm body envelope and a further 0.10 mm assembly allowance.
  - <https://www.kailhswitch.com/Content/upload/pdf/202115927/CPG135001S30-data-sheet.pdf>
- Cherry MX-compatible body envelope: 15.60 mm square was used as the common conservative top-side switch envelope because it is larger than the public PG1353 envelope.
  - <https://www.cherry.de/en-gb/product/mx2a-black/downloads>
  - <https://www.kailhswitch.com/uploads/15927/files/CPG151101S153.pdf?rnd=763>
- Jingdao ES1B / LCSC C437840: maximum package span 5.20 mm by 2.70 mm by 2.20 mm, with the repository's separate 0.30 mm solder-fillet allowance.
  - <https://www.lcsc.com/product-detail/C437840.html>
  - <https://datasheet.lcsc.com/datasheet/pdf/2343098076327222563a84c9a80dbd7d.pdf?productCode=C437840>

### Fastener and tool envelopes

- NBK `SNZS-M1.4-3` proves that a catalogued M1.4 x 3 precision machine screw exists with 0.30 mm pitch and a 2.00 mm diameter by 0.50 mm high PH0 head. It is historical low-head geometry evidence only and no longer defines the active rounded-head envelope.
  - <https://www.nbk1560.com/en/products/specialscrew/nedzicom/miniaturescrew/SNZS-M/SNZS-M1.4/SNZS-M1.4-3/>
- TR Fastenings lists 1.60 mm as the normal M1.4 clearance-hole recommendation.
  - <https://www.trfastenings.com/Knowledge-Base/Engineering-Data/tapping-sizes-and-clearance-holes>
- A traceable M1.4 x 4 P-type direct-plastic candidate exists as `TR00036455-117`, but availability is to be advised, the 4 mm family is non-preferred, and a public complete head drawing was not available during the review.
  - <https://www.trfastenings.com/Products/Catalogue/Screws-and-Bolts/Screws-for-Plastic/JCIS-P-Type-M1-point-4-to-M2-point-6/Pan-Head/TR00036455-117>
- A 3.00 mm diameter PH0 precision-driver shaft was used as the final vertical service envelope. It already includes the search model's 2.50 mm shaft plus 0.25 mm radial reserve and shall not receive a second reserve. The resulting nominal switch-body margin is only 0.025 mm, so the exact production driver MPN, maximum shaft diameter, runout, and measured assembly clearance are physical release gates.
- Bulten MINI-TECH includes M1.4 inserts, but the standard 2.20 mm insert plus 0.70 mm minimum wall needs at least a 3.60 mm boss.
  - <https://www.bulten.com/media/vd4jl4bi/minidsf-bulten.pdf>

A separate exhaustive 3.60 mm-boss search was performed. Feasible points exist away from the seam, but the right key-field seam has zero candidates with the required 0.25 mm reserve. Its best point provides only 0.18813 mm because the boss/support and driver/switch envelopes become limiting together. A 2.50 mm-long insert also consumes the full 2.50 mm structural plate thickness and cannot leave a closed plastic floor. The insert option is therefore rejected for the selected seam-distributed pattern; it remains a future non-seam redesign option only.

### PCBWay limits used

- Standard CNC-routed outline tolerance: +/-0.20 mm.
- Standard NPTH finished-size tolerance: +/-0.05 mm.
- Standard hole-position tolerance: +/-0.075 mm.
- Published normal NPTH-to-copper distance: 0.20 mm; this design uses at least 0.30 mm plus a separate 0.25 mm placement reserve in the search model.
- A 1.60 mm NPTH is routine. The active design keeps round 1.60 mm holes because enlarging or slotting them does not improve head-to-switch clearance and would reduce bearing and registration margin under the rounded head. Multi-axis fit remains a physical coupon gate.

Sources:

- <https://www.pcbway.com/capabilities.html>
- <https://www.pcbway.com/pcb_prototype/PCB_Manufacturing_tolerances.html>

## Alternative Comparison

| Candidate | Distribution | Result |
| --- | --- | --- |
| M2 | Large 2.4 mm clearance hole and at least 3.0 mm head | Rejected: no structural advantage once distributed supports are retained, and it consumes the most component/routing clearance. |
| M1.6, 5 left / 5 right | Larger and more traceable direct-plastic candidate | Rejected as final layout: right seam coverage and anti-lift distribution are materially poorer than the selected M1.4 arrangement. |
| M1.4, 8 left / 10 right | Smallest verified geometric envelope and best distributed coverage | Selected for digital prototype, conditional on physical pilot/torque/deflection testing. |

The existing rail/support load path remains better than the screw-only path. The current maximum switch-to-rigid-support distance is 15.464 mm left and 18.962 mm right. The new screws must not cause removal or relocation of those supports.

## Historical 2026-08-25 Low-Head Coordinates

These coordinates are KiCad board coordinates in millimetres and are retained only to explain the original low-head review. They are superseded by the rounded-head addendum and shall not be used to regenerate the active board. References remain `MH1...MH8` on the left and `MH1...MH10` on the right; legacy `H*` and `REG*` references remain forbidden.

### Left — eight points

| Ref | X | Y |
| --- | ---: | ---: |
| MH1 | 142.6125 | 68.0000 |
| MH2 | 128.6125 | 86.5000 |
| MH3 | 100.1125 | 93.5000 |
| MH4 | 57.1125 | 99.0000 |
| MH5 | 133.6125 | 131.5000 |
| MH6 | 55.1125 | 144.0000 |
| MH7 | 165.6125 | 145.0000 |
| MH8 | 102.6125 | 147.0000 |

### Right — ten points

| Ref | X | Y |
| --- | ---: | ---: |
| MH1 | 71.6875 | 68.0000 |
| MH2 | 181.1875 | 85.5000 |
| MH3 | 147.6875 | 93.5000 |
| MH4 | 109.6875 | 96.5000 |
| MH5 | 71.6875 | 105.5000 |
| MH6 | 42.1875 | 106.0000 |
| MH7 | 181.1875 | 134.5000 |
| MH8 | 143.1875 | 134.5000 |
| MH9 | 51.6875 | 144.0000 |
| MH10 | 95.6875 | 147.0000 |

The right-side set leaves points on both printable housing parts rather than using the PCB as the only retaining member of the split housing.

## Historical Low-Head Search Margins

The exhaustive placement search included the complete closed Edge.Cuts polygons, all routed copper and vias, Choc socket and fillet envelopes, MX pins/pads/fillets, switch mechanical NPTHs, ES1B body/pads/fillets, U1/reset, battery slot, antenna/service exclusions, current housing cutouts, the right split, and existing supports.

For the superseded 2026-08-25 8/10 points:

| Metric | Left minimum | Right minimum |
| --- | ---: | ---: |
| 3.00 mm housing land to current support/cutout boundary | 0.3831 mm | 0.3000 mm |
| 1.60 mm NPTH edge to copper, excess above the 0.30 mm rule | 0.3050 mm | 0.3627 mm |
| NPTH to via | 3.1902 mm | 3.5307 mm |
| Final 3.00 mm driver envelope to switch/controller body | 0.0250 mm | 0.0250 mm |
| 2.00 mm head to Edge.Cuts | 3.5000 mm | 1.4000 mm |
| Additional separation from current support/foot | 0.4364 mm | 6.9165 mm |

These are nominal CAD margins. They do not include an unmeasured 3D-printed keycap skirt, printed-hole drift, driver runout, or fastener tilt.

## Housing Stack For The Active Digital Prototype

- PCB thickness: nominal 1.60 mm.
- Structural support plane: housing top Z = 2.50 mm.
- Each mounting point has a 3.00 mm minimum-diameter zero-gap annular support land at Z = 2.50 mm.
- Each mounting point also extends to the Z = -1.00 mm desk datum as a local support foot so a clamped PCB load is not carried by a floating 2.50 mm plate span.
- Initial direct-thread coupon pilot assumption: 1.10 mm nominal diameter and 2.80 mm nominal blind depth from the housing top, ending at Z = -0.30 mm in the local 1.00 mm desk-contact column and leaving a 0.70 mm nominal closed bottom.
- The provisional under-head screw length is 4.00 mm. With PCBWay's 1.6 mm PCB thickness tolerance of +/-10%, nominal plastic penetration is 2.24–2.56 mm; the 2.80 mm pilot therefore leaves 0.24 mm clearance at the maximum penetration and shall not break the desk-contact bottom.
- That penetration is only 1.60–1.83 times the M1.4 diameter and is below the usual 2d direct-plastic guidance. It is an explicit prototype exception requiring measured tapping/stripping/pull-out evidence, not a validated reusable joint.
- The installed screw, head, thread form, pilot, and torque dimensions remain provisional until the exact direct-plastic fastener and printed coupon are selected. Direct-plastic service life is expected to be lower than a metal insert and shall not be represented as repeatedly serviceable before the ten-cycle gate passes.

## Registration And Service Strategy

- Keycaps must be removed before servicing the screws; switches may remain installed.
- The complete vertical 3.00 mm PH0 driver cylinder must clear installed Choc V2/Deep Sea and MX switch bodies.
- All PCB holes are 1.60 mm round NPTHs. This preserves registration and radial bearing beneath the provisional 3.00 mm rounded head; changing the hole diameter does not solve head-to-switch interference.
- Multi-hole binding is a known risk. PCBWay hole-position/size tolerance and printed pilot-pattern error shall be exercised in a full-pattern coupon before the hole pattern is treated as fit evidence.
- If the full round-hole pattern binds, the next revision must use a separately verified round-datum/one-axis-relief/floating-hole stack with a larger traceable head or washer; it must not silently enlarge holes under the current head.

## Required Physical Coupon And Release Gates

The board and housing remain `DRAFT / NOT ORDERABLE` for production until all of the following are recorded. A deliberately limited prototype/coupon PCB-and-housing fabrication is permitted only after the complete digital PCB/housing preflight, Gerber/Excellon review, and component-by-component review pass; that prototype authorization is not production fabrication or general parts-order approval.

1. Exact direct-plastic screw MPN and drawing, including head min/max diameter and height, recess, thread length, and allowed torque.
2. Pilot matrix printed in the production material, nozzle, layer height, orientation, and slicer: 1.00, 1.05, 1.10, 1.15, and 1.20 mm.
3. Measured pilot and boss diameters.
4. Tapping and stripping torque ratio at least 2.0, with a target of at least 3.0.
5. Ten install/remove cycles with no boss crack, spin, pull-out, permanent PCB bow, or loss of clamp.
6. Full-pattern assembly without sequential forcing or misalignment.
7. Actual Deep Sea/Choc V2 and MX switch plus printed-keycap skirt clearance.
8. A 2.0 N load at every worst support span with no more than 0.30 mm PCB deflection, no rocking, and no support disengagement.
9. Fresh KiCad DRC, route/zone review, Gerber/Excellon inspection, 1:1 overlay, STEP/STL collision review, and component-by-component fabrication review.

## 2026-08-29 Rounded-Head Addendum

The user selected a rounded rather than reduced/low head. M1.4 has no single ISO pan-head maximum that can be inferred from the thread designation alone: ISO 7045 starts at M1.6. Supplier examples range from nominal `2.50 x 0.80 mm` to approximately `2.90 x 1.12 mm`. Until a complete direct-plastic order code and tolerance drawing are locked, the active digital envelope is therefore a conservative round cylinder `3.00 mm` in diameter and `1.20 mm` high.

Sources reviewed for the new envelope include the following deliberately limited evidence classes. None is the selected production order code:

- Fastenright MF14 is a supplier-family, nominal `2.50 x 0.80 mm` plastic thread-forming reference; its public page does not close exact order-code tolerances: <https://www.fastenright.com/general-fixings/micro-pozi-pan-thread-forming-screw-for-plastic/mf14>
- EJOT DELTA PT establishes a direct-plastic M1.4 family, not the active maximum-head MPN/drawing: <https://www.ejot.com/Industrial-Fasteners-Division/Products/DELTA-PT%C2%AE/p/VBT_DELTA_PT>
- SAIMA miniature tapping screw `3Mi101440ZP` is a head-geometry comparison only: <https://en.saima.co.jp/product/miniature-screws/3mi10_zp/>
- SKDIN `0498FA00002` is a rounded-pan geometry upper-bound example intended for metal substrates, not evidence of direct-plastic suitability: <https://www.skdin.com/products/productid-0498FA00002>

The conservative installed switch envelope is `15.60 mm` wide on a `19.05 mm` pitch. The straight inter-switch corridor is only `3.45 mm`, while a `3.00 mm` head plus `0.25 mm` clearance on both sides requires `3.50 mm`. The earlier centers therefore could not be repaired by tiny moves. The following P1 set was selected temporarily and is now historical:

| Ref | Left X | Left Y | Ref | Right X | Right Y |
| --- | ---: | ---: | --- | ---: | ---: |
| MH1 | 142.6125 | 67.9000 | MH1 | 71.6875 | 67.9000 |
| MH2 | 128.6125 | 86.5000 | MH2 | 181.0875 | 85.5000 |
| MH3 | 108.5125 | 87.0000 | MH3 | 156.1875 | 87.0000 |
| MH4 | 57.4125 | 99.0000 | MH4 | 109.6875 | 104.8000 |
| MH5 | 124.7125 | 125.1000 | MH5 | 71.6875 | 105.5000 |
| MH6 | 55.1125 | 144.0000 | MH6 | 62.0875 | 69.3000 |
| MH7 | 165.6125 | 145.0000 | MH7 | 181.1875 | 143.0000 |
| MH8 | 102.6125 | 147.0000 | MH8 | 143.0875 | 143.0000 |
| - | - | - | MH9 | 66.8875 | 153.4000 |
| - | - | - | MH10 | 95.6875 | 147.0000 |

The historical P1 digital analysis reported minimum head-to-installed-body clearance `0.2591 mm` left and `0.2553 mm` right, head-to-edge clearance `2.90 mm` left and `2.3201 mm` right, mounting-hull preservation `99.90%` left and `97.22%` right, and sparse primary-support load spans `15.4640/18.9619 mm`. The user rejected that combined clamp/support compromise.

## Final Decision

The 2026-08-30 P2 recommendation was an intermediate 8-left / 9-right clamp geometry with a separate one-to-one 31-left / 39-right switch-load support network. It restored right `MH5`, added left `MH8 (75.0000,134.0000)`, and moved the only retained right reinforcement to `MH9 (177.5000,118.0000)`; it was superseded by the exact 1N4148W/P3 coordinates and `2.40 mm` support contract in `CON-ARCH-006`. The `3.00 x 1.20 mm` head, 1.10 mm blind pilot and 4.00 mm under-head length remain provisional prototype envelopes, not procurement-approved hardware. Do not claim physical retention, deflection compliance, repeated serviceability, fabrication readiness, or order readiness until the exact MPN/drawing and coupon gates above pass.
