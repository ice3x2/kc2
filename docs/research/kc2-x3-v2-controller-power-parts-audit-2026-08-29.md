# KC2 X3 V2 controller-power parts and release-evidence audit

Date: 2026-08-29
Scope requirements: `CON-ARCH-004`, `CON-ARCH-006`, `CON-ARCH-007`, `REL-ARCH-001`
Status: digital implementation evidence only; fabrication and parts ordering are not approved

This note records the five independent component, circuit, structural, fabrication-output, and release-evidence reviews performed after the switched per-half battery service layout was pulled into the X3 V2 branch. It is research evidence, not a second requirements source. The acceptance contract remains in `docs/spec/10.product-architecture.srs.md`.

## Reviewed assembly

The frozen digital board contains, per half, one socketed nice!nano v2 controller, one nominal 301230 battery reference, one two-pad direct-solder battery termination, one three-terminal slide power switch, one two-pad reset tact switch, M1.4 retention holes, 31 or 39 hybrid switch positions, and one ES1B diode per key.

| Item | Controlled digital geometry | Audit conclusion |
| --- | --- | --- |
| `BAT1` | nominal `30 x 12 mm` plan reference; nominal `3 mm` thickness class | A size code is not an orderable identity. Exact protected-pack manufacturer/MPN, maximum swollen envelope, protection declaration, lead exit and lead drawing remain pending. |
| `J_BAT1` | two direct-solder PTH pads, `2.54 mm` pitch; pad 1 `BAT+`, pad 2 `GND` | Board nets and routed continuity pass. Actual insulated-lead diameter, solder fillet and strain relief require a populated first article. |
| `SW_PWR1` | owned three-pad footprint, `0.80 mm` plated drills at `2.54 mm` pitch; nominal `10.00 x 2.50 mm` body, `6.40 mm` installed-height proxy and `1.60 mm` travel | The board model and pad order pass digitally. `IMMS-12V` and `BSI-10` names are not treated as proven equivalents; one purchased MPN/drawing or incoming inspection is required. The STEP is a nominal collision proxy, not maximum-envelope evidence. |
| `SW_RST1` | owned `NW3-A06-B3` footprint; nominal `6.10 x 3.70 mm` body; pad 1 `RST`, pad 2 `GND` | Placement, rotation and pad nets pass. A controlled primary drawing or incoming lot inspection must establish maximum height, travel, force, reflow limits and exact supplied-part equivalence. |
| `U1` | owned 24-pad side-specific nice!nano v2 socket footprint; `RAW=NN_B+`, `GND_C=GND`, `RST=RST` | Pad labels, geometry and power/reset nets pass. Exact socket-receptacle height, pin-tail and populated controller/USB stack remain physical gates. |
| Hybrid switch | Choc V2 hot-swap lands on `B.Cu`; MX electrical PTH pads and copper-free locator holes; no stabilizer | Source and all 70 placed footprints now include complete front/back courtyard contracts. “Deep Sea Whale” or `PG1353-class` is not a unique procurement MPN; exact supported low-profile switch drawing remains pending. |
| ES1B | Jingdao ES1B / LCSC `C437840` / Eleparts `9475342`; SMA lands `1.80 x 1.80 mm`, `2.40 mm` inner gap; pad 1 cathode/row, pad 2 anode/per-key | All 70 placed diode lands, polarity, B.Cu orientation and row/switch nets pass. |
| M1.4 retention | left 8/right 10 unplated `1.60 mm` holes, visible `MH*` references; rounded-head provisional maximum `3.00 x 1.20 mm`; housing land/column `3.00 mm`, pilot `1.10 x 2.80 mm` | The active P1 centers move into switch-corner pockets to retain `0.25 mm` head clearance while preserving the 14/11 primary supports. Exact screw, driver runout, printed pilot, torque, cycles, registration and 2 N deflection remain pending. |

## Circuit review

The independent circuit audit checked the actual PCB pad nets rather than generated net names alone:

- `J_BAT1 pad 1 (BAT+) -> SW_PWR1 pad 1 (common)`;
- `SW_PWR1 pad 2 (ON) -> NN_B+ -> U1 RAW`;
- `J_BAT1 pad 2 -> GND -> U1 GND_C`;
- `SW_RST1 pad 1 -> U1 RST`, and `SW_RST1 pad 2 -> GND`;
- every switch/ES1B path keeps column -> switch -> diode anode, diode cathode -> row polarity;
- M1.4 holes remain unnetted, unplated and copper-free.

KiCad 10 DRC is clean on both frozen halves with zero violations and zero unconnected items. The release verifier was strengthened to reject wrong or netless `U1 RAW`, `GND_C`, and `RST` pads, so a self-consistent net-name mutation cannot silently pass.

## Structural and service review

The existing perimeter rail plus 14 left and 11 right distributed supports remains the primary key-load path. M1.4 screws clamp and register the PCB; they do not replace those supports. The verified maximum key-to-support spans remain `15.4640 mm` left and `18.9619 mm` right.

The final PH0 driver envelope is deliberately tight. Keycaps must be removed while switches remain installed. Physical driver shaft/runout and printed-hole tests are therefore mandatory. After the user selected a rounded head, the active P1 coordinates use a conservative `3.00 x 1.20 mm` head envelope and move the limiting holes into corner pockets rather than depend on the obsolete right-MH9-only rail relief or waive the `0.25 mm` reserve.

The mounting clearance analysis now includes the full nominal `BAT1 30 x 12 mm` plan, the complete `SW_PWR1 10 x 2.5 mm` body and its actuator sweep, the installed switch bodies, routed copper and vias. Reset support metadata follows the actual left `0 deg` / right `180 deg` rotation and derives bottom-mask protection from the real pad stack rather than a constant.

## Fabrication and evidence findings

A package hash alone did not prove that Gerber, Excellon or a 1:1 drawing matched the source board. The revised verification contract therefore compares source-derived service PTH/NPTH coordinates and sizes with the extracted drill/Gerber semantics and parses the mechanical PDF/SVG page geometry, scale, mirror and feature positions. Per-half BOM outputs are source-derived.

Order readiness is fail-closed through a separate physical-evidence record. Generated design manifests remain `order_ready=false`. A future pass must bind repository paths and SHA-256 digests for the exact purchased-part documents and raw measurements, including equipment/calibration, sample counts, limits and computed results. Merely changing a scalar to `passed`, `confirmed`, or `order_ready=true` is rejected.

Required physical bundles are:

1. exact pack/switch/controller/socket identity, caliper stack, lead pull and POWER/RESET service evidence;
2. populated 3.0/3.3 V maximum-row and maximum-column scan evidence;
3. screw/pilot torque, stripping ratio, ten service cycles, no-force registration and 2 N deflection evidence;
4. power-transition oscilloscope captures and final assembled BLE/RF reliability evidence.

## Decision

The digital design may continue through reproducible verification and deliberately limited prototype evidence generation. It is not approved for production fabrication or general parts ordering. The blockers above are intentional SRS gates, not optional recommendations.

## Source references

- Jingdao ES1B/LCSC C437840: <https://www.lcsc.com/product-detail/C437840.html>
- Eleparts ES1B listing: <https://www.eleparts.co.kr/goods/view?no=9475342>
- Kailh low-profile switch family: <https://www.kailhswitch.com/uploads/15927/files/CPG1353S01D01-01-data-sheet.pdf?rnd=494>
- Kailh Choc socket CPG135001S30: <https://www.kailhswitch.com/Content/upload/pdf/202115927/CPG135001S30-data-sheet.pdf>
- nice!nano documentation: <https://nicekeyboards.com/docs/nice-nano/>
- PCBWay capabilities and tolerances: <https://www.pcbway.com/capabilities.html>
- M1.4 mounting-hole research and fastener sources: `docs/research/kc2-x3-v2-micro-mounting-hole-review-2026-08-25.md`
