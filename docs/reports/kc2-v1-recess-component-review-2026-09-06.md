# V1 / recessed-lid revision: independent component and circuit review

Requirements: `CON-ARCH-004`, `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-007` (current evolving requirements queried through SpecKiwi). This is a fresh read-only review of the promoted canonical PCBs, not a reuse of the r2 board verdict and not final fabrication approval. KiCad skill instructions were followed; no installed `kc2-pcb-preflight` skill was available. No canonical PCB, CAD, or sealed package was changed by this review.

## Bound evidence

The [actual-pad inventory and analyses](kc2-v1-recess-component-data-2026-09-06.json) include every footprint and pad: reference, value, library identity, assembly side, orientation, coordinate, net, pad/drill size, and declared layer set. Twenty-two raw-SHA source bindings cover both PCBs, DRC reports, checker sources, firmware configuration/build evidence, generation manifest, and both UF2 files. All source hashes were identical before and after collection.

- Left PCB raw SHA-256: `568e1427e4cfb9d667b6d5b3754da3a4e24c924abfa85a8dfe394dd050b5fe67`.
- Right PCB raw SHA-256: `88290c3b0cf3951d56221d216549665c0576a816a6315012f7f12b027f402577`.
- Supporting JSON raw SHA-256: `0557efc484c4c52cb565a751d1203fdbbef7d698bcac13863cbca1728510b8ed`.

Fresh `analyze_v2_board`, actual-route connectivity, and compact-controller checks return no errors on either half. Firmware verification also returns no errors, verifies both local UF2 artifacts and build provenance, and matches all70 matrix positions. The standalone firmware CLI exited0. KiCad's duplicate-image-handler stderr makes the PowerShell redirection wrapper report1 despite successful JSON collection; that wrapper is not represented as an exit0 test.

## Component-by-component findings

| Component / feature | Fresh actual-board finding |
|---|---|
| Controllers,2 ×24 pins | All48 pad identities/ordered coordinates match the intended nice!nano v2 physical rows; pitch2.54 mm, row spacing15.24 mm. Both modules mount component-side up, USB outward: left USB left, right USB right. Side-specific owned footprints encode the rotation; a raw footprint angle alone is not the assembly orientation. |
| Controller solder lands | All48 remain oval1.80 ×2.40 mm, drill0.95 mm, front/back mask open and no paste. Unused module contacts remain intentionally unnetted. |
| Battery/service circuits | Both J_BAT1 pad1=BAT+, pad2=GND;0.90 mm PTH. Both POWER central pad1=BAT+, throw2=NN_B+, throw3 unnetted; RESET pad1=RST and pad2=GND. No BAT−/NN_B− carrier net or negative-lead switching was introduced. |
| MX and Choc contacts | All70 switches have two MX PTHs and two bottom Choc SMD alternates. Each duplicate number has one intended net and the actual copper routes tie the alternates, not merely identical labels. Pad1 goes to column; pad2 goes to its individual diode anode net. MX contacts retain2.50 ×3.20 mm area /1.60 mm drill; pad2's45-degree local rotation provides clearance for the revised locator hole without moving the electrical hole. |
| Switch alternatives | Selected MX is seller-listed TTC Bluish White / Tactile Silent42gf3-pin. Selected Choc V2 is Kailh Deep Sea brown. The revised shared locator holes accommodate the approved V1/MX mechanical interface; do not populate Choc sockets and MX receptacles simultaneously on one key. The MX plate is not a Choc retention plate. |
| Diodes,70 | Every diode is owned `D_1N4148W_SOD123_HandSolder_DiodesInc`, value1N4148W-13-F, B.Cu assembly. Every pad1 cathode is on its row; pad2 anode is on the corresponding switch's per-key net. Footprint geometry and all70 polarity/net checks pass. |
| Mechanical holes | Every NPTH is unnetted and has no copper-layer membership. Counts remain195 left /244 right because the two prior locator holes per key are replaced, not added. Shared holes are round2.60 mm at local X±5.45 mm. Exact8/9 MH centers remain1.60 mm NPTH. Battery lead slot remains3.60 ×2.20 mm. |
| No stabilizers |31 left /39 right switches and matching diodes; no STAB reference or legacy registration-hole substitute. Actual switch-layout comparison passes. |
| Battery/body/RF envelopes | Both nominal battery-to-antenna gaps3.97 mm and battery-to-socket-copper gaps0.42 mm pass the modeled contract. Service geometry and all controller/body clearance checks pass. These are not RF, cell-swelling, or charge-temperature measurements. |

## Physical pin orientation and circuit intent

The [official nice!nano pinout](https://nicekeyboards.com/docs/nice-nano/pinout-schematic/) was reopened and its v2 diagram visually compared with fresh actual-pad coordinates. RAW is the ordinary battery-positive row contact; VCC is not battery input. GND_C is local ground. The extra top-edge battery pads are not assumed to be ordinary socket pins. Do not bridge BOOST for an unspecified cell; the nominal pack's protection and charge rating still require confirmation.

Actual left RAW/GND_C coordinates are(118.7425,43.13)/(121.2825,43.13); right(91.37,58.37)/(88.83,58.37). Actual RESET pad pairs are left(122.1875,63.45) RST/(129.9375,63.45) GND and right(87.925,63.45) RST/(80.175,63.45) GND. These preserve the circuit through the opposed assembly orientations.

The manufacturer-authored [BSI-10 drawing](https://amec-gmbh.de/wp-content/uploads/2022/11/BSI-10.pdf), inspected from its previously downloaded page image after the live endpoint timed out, confirms physical order2–1–3 with central common1 and2.54 mm pitch. The [NW3-A06-B3 supplied drawing](https://www.devicemart.co.kr/goods/download?id=1322056&rank=1), also visually inspected from the downloaded image, specifies a two-terminal normally-open circuit and7.75 mm land-center spacing. Neither interface authorizes substituting an arbitrary similarly named switch.

The manufacturer-authored [Diodes DS30086 Rev31-2](https://www.mouser.com/datasheet/2/115/ds30086-3214660.pdf) was reopened: cathode-band polarity, SOD123 outline, and exact1N4148W-13-F ordering identity agree. Bottom-side assembly must use the mirrored bottom view and pad1 marking. There is no canonical schematic; this is SRS/firmware intent versus actual-pad/route review, not an ERC or independent schematic-parity claim.

## Firmware and routing

The left matrix columns use D3,D5,D4,D6,D7,D8,D9; rows D10,D16,D14,D15,D18. Right columns0–8 use D9,D10,D16,D14,D15,D18,D19,D21,D20; rows D3,D4,D5,D2,D7. Fresh firmware comparison verifies this assignment and physical SW-reference transform, including the right global column offset7 and left central role. Diode direction remains col2row. Existing verified UF2 bytes are still compatible; no firmware rebuild is implied by this mechanical revision.

Current routes are876 left /1089 right track-via items, not r2's738/949. Current DRC files contain0 violations and0 unconnected items. All per-component geometry/clearance error lists are empty. Minimum modeled diode-fillet-to-unrelated-route gap is0.737 mm left /0.175 mm right, above the dedicated0.10 mm fillet rule; this does not lower the separate0.30 mm unrelated-copper rule. Minimum diode-to-unused-NPTH clearance is1.201 mm on both halves.

Ignored DRC classes remain footprint_filters_mismatch, footprint_type_mismatch, missing_courtyard, track_not_centered_on_via, and tuning_profile_track_geometries. Embedded footprint fallback is explicit: most owned board footprints have an empty library nickname; U1 uses KC2 side-specific library identities. Owned-geometry checks are the relevant traceability evidence, not an assumption that every embedded footprint has an externally resolvable library. Route replay/regeneration and final rendered-output inspection remain separate release gates.

## Release-pipeline status and remaining limits

The current package code checks typed/source-bound board and housing reports, nested board errors, connectivity, DRC counts, actual archive/output hashes, and native Fusion blockers. Its manual BOM now names the selected TTC switch, mutually exclusive Choc alternatives, and7.50 mm recessed-lid fastener candidate. It does not silently keep the obsolete9 mm screw.

At review time the19 package/semantics tests could not run: their setup referenced the new r3 Gerber directory before those outputs existed. These were19 setup errors, not19 passes and not evidence of a PCB circuit defect. Rerun after export; bind fresh visual,1:1, mechanical, native CAD, and package verification before release. Old r2 files are not current-board fabrication evidence.

No known electrical/pin-net incompatibility was found in these bound boards. Exact hat-socket contact range, switch-blade tolerance, actual battery qualification, solder intrusion, printed-thread torque/retention, and contact-cycle reliability remain unmeasured. The recessed-head CAD verdict is owned by the separate current housing analysis; this component report does not certify unprovided keycap underside geometry. Neither unknown tolerances nor pending physical acceptance are converted to a measured pass. No order/payment approval is given by this report alone.
