# Closed-floor component impact review

Requirements: `CON-ARCH-006`, `OPS-ARCH-007`, with preserved circuit/component constraints under `CON-ARCH-004` and physical power/RF gates under `CON-ARCH-007`/`REL-ARCH-001`.

This is an incremental independent component-impact review, not a claim that a closed shell thermally or physically qualifies unknown purchased parts. The current floor CAD/native review is separate; older open-bottom r3 housing evidence is not sufficient.

## Unchanged electronics and fabrication

A fresh raw-byte comparison against sealed r3 review bindings checked35 PCB/project/Gerber/drill/owned-footprint inputs and found zero differences. [Full input comparison](kc2-solid-floor-component-inputs-2026-09-07.json) lists every selected path and both hashes. No copper, physical pad center, polarity, controller/service pinout, socket footprint, matrix circuit or manufacturer component identity changes merely because the floor is added. The [r3 component-by-component review](kc2-v1-recess-component-review-2026-09-06.md) therefore remains electrical/part-orientation evidence for those identical bytes, but not proof of the new mechanical cavity.

## Inner-floor clearance is bounded, not assumed unlimited

PCB underside remains Z2.50 mm; inner floor is Z-1.00 mm. Available nominal depth is3.50 mm. The current SRS maximum permitted actual projection is2.90 mm, leaving0.60 mm nominal clearance. Reserving0.30 mm for engineering print error leaves0.30 mm residual clearance. This is an assembly limit to inspect after receipt, not a measured maximum of unknown headers, posts, wires or solder.

| Item | Existing dimensional evidence | Floor impact |
|---|---|---|
| Open-bottom hat socket | Nominal length3.00, flange0.20, PCB1.60 mm; nominal below-PCB projection1.20 mm | Nominal floor gap2.30 mm. PCB-only1.44..1.76 variation gives projection1.36..1.04 and minimum2.14 mm gap. Supplier socket dimensions remain nominal; solder is additional. |
| Choc socket | Current generator uses2.30 mm controlled maximum body depth +0.10 mm assembly allowance =2.40 mm modeled projection | Modeled floor gap1.10 mm (3.50-2.40), not the historical2.20 mm bare-body reference's1.30 mm gap. Selected-lot body/contact qualification remains separate. |
| SOD-123 diode | Controlled body height limit1.35 mm +0.30 mm solder-fillet depth allowance =1.65 mm modeled projection | Modeled floor gap1.85 mm (3.50-1.65). The bare-body-only2.15 mm result excludes the modeled solder allowance and is not the assembled clearance. |
| Switch pins, locator posts, controller socket tails, service pins | No complete exact-lot protrusion inventory | Require every actual rigid projection and solder accumulation to remain<=2.90 mm below PCB. A nominal reference switch-pin analysis is not selected-part measurement. |
| Battery leads/insulation | Battery lead slot and controller/battery placement unchanged | Wire loops now enter an internal cavity. Route and restrain without pinching against floor, screw, post or split; do not infer fit from copper clearance. |

These assembled-envelope values follow `CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM`, `CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM`, `DIODE_OFFICIAL_BODY_DEPTH_MAX_MM` and `DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM` in [the current housing generator](../../tools/generate_kc2_x3_v2_housings.py). Its `closed_floor_parameters().nominal_clearance_by_component_mm` and [the housing contract verifier](../../tools/verify_kc2_mx_housing_contract.py) agree on Choc1.10/diode1.85/hat2.30 mm. The separate0.30 mm engineering print reserve would leave0.80/1.55/2.00 mm respectively under those modeled projections; it does not establish actual supplier tolerances or solder dimensions.

Remove the PCB before soldering or trimming permissible bare lead tails; do not solder through the closed floor. Do not grind a functional switch/socket body or force an overlong component to fit. If an actual part exceeds the projection limit, stop closure and revise the selected stack/part with measured evidence. Do not use screw preload to compress wires, solder joints or a battery.

The floor is below the existing support-foot ends; it does not move PCB support, receiver entry, pilot end or recessed head bearing. The7.50 mm under-head screw remains the nominal contract:2.20 mm insertion and0.60 mm receiver-tip reserve. Additional outside floor thickness is not permission to lengthen screws. Exact screw length tolerance and printed-thread strength remain unqualified.

## Thermal, battery and RF consequences

A closed floor removes the previous open underside airflow path. The resulting temperature change cannot be calculated from geometry alone: actual charging loss, battery characteristics, material thermal properties, boundary airflow and contact resistances are absent. No CFD result, temperature ceiling or thermal PASS is claimed. A floor is neither a heat sink nor a battery safety enclosure rating.

The [nice!nano manufacturer documentation](https://nicekeyboards.com/docs/nice-nano/) identifies its onboard lithium charger, requires a compatible rechargeable3.7 V pack, and warns that underside pins can puncture a battery. Preserve the existing reviewed unboosted charge configuration and protection/polarity requirements; adding a floor does not qualify the unspecified cell's charge rating. Before normal closed-case charging, inspect lead clearance and pack condition, then check actual cell/controller temperature against the selected cell/controller material limits in the intended assembled configuration. Do not invent limits for an unidentified pack or treat a cool exterior as proof of a cool cell. Charge-boost modification is not authorized by this floor revision.

The polymer floor adds material near the assembly but does not change the modeled antenna/copper geometry. RF performance may still depend on actual material, additives, battery/wire placement and the desk. Repeat the existing post-receipt charging-state RSSI/PER/disconnect acceptance; no new RF pass follows from unchanged PCB nets.

## Silicone feet and mechanical service

Twelve nominal diameter8 mm flat bonding regions (four per printable lower part) are placement geometry, not qualification of a purchased foot. Foot thickness changes desk-relative height without changing the internal screw/PCB stack. Adhesive compatibility, surface preparation, peel/creep, slip resistance, load compression and coplanarity require selected-material evidence. Keep pads off seams and service features as checked by the current floor-layout verifier; do not assume unspecified adhesive tolerates charging heat or repeated cleaning.

The new continuous floor can change stiffness, sound and transmitted vibration, but no FEA, modal, acoustic or printed-strength improvement is claimed. Each lower split part still requires valid connected geometry and a print-compatible joint; a floor crossing the nominal assembled outline is not evidence that both independently printed parts are watertight. Current STEP/STL/native and floor-section evidence must pass separately before the r4 release is built.
