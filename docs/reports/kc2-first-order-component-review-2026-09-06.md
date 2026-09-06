# KC2 first-product component and circuit review

Requirements: CON-ARCH-004, CON-ARCH-006, CON-ARCH-007, REL-ARCH-001,
OPS-ARCH-007. This records pre-order design inspection, not measured hardware
qualification. The first manufactured lot is the product, not a sample prerequisite.

## Source identity and coverage

Canonical LF-normalized PCB SHA-256:

- Left: `e1a50fa657a2cc8ad10a60eed9e0fd5d326c6a138315f429414b9fc18d3b5583`
- Right: `30029aac80a7d1ce0cdf15ead621dcc9906e51775e031c4dffe4841aff8f618c`

The current exact V2 verifier was rerun and returned `errors=[]` and
`connectivity_errors=[]`. Its nine legacy order-blocker messages describe
qualification activities; their timing is governed by OPS-ARCH-007. They are
not converted into physical PASS results. The new first-order package gate also
requires independent actual-output and mechanical reviews.

The KiCad skill was used. No installed `kc2-pcb-preflight` skill was available;
the repository component/circuit checks and independent review cover its stated
gate categories. There is no canonical schematic: this is actual-pad/net versus
SRS/firmware intent review, not an ERC or independently authored schematic-parity claim.

| Item | Actual design review |
|---|---|
| Both nice!nano v2 controllers | All 24 physical pad identities and ordered positions checked; 2.54 mm pitch, 15.24 mm row spacing. Component side up, USB outwards: left USB left, right USB right. Right footprint is the corresponding 180-degree physical orientation, not a backside assembly. |
| Controller battery/reset | RAW is the ordinary side-row battery-positive connection, not 3.3 V/VCC. GND_C is ground. Top-edge extra battery pads are not assumed to be socket contacts. RESET goes only to RST and local GND. Unused controller contacts remain intentionally unconnected. |
| Battery pads, two halves | J_BAT1 pad1 BAT+, pad2 GND, 0.90 mm PTH; no connector polarity is implied by a wire color. Left pad1/2 X=115.8125/113.2725, right=94.3000/96.8400; Y=59.4000 mm. Protected single-cell 301230 nominal 30x12x3 mm envelope is a dimensional interface, not approval of an unspecified pack's charge rating. |
| POWER, two halves | Common pad1 BAT+ at center; pad2 NN_B+; pad3 NC. Left 0 degrees, right 180 degrees. Physical straight-lead order 2,1,3 and 2.54 mm pitch agree with the BSI-10 drawing. Switching the negative lead is not substituted. |
| RESET, two halves | NW3-A06-B3 two-terminal normally-open SMD interface, body 6.1x3.7 mm, nominal height2.55 mm; mirrored placement retains pad1 RST/pad2 GND. No four-terminal switch substitution. |
| 70 switches / 140 MX sockets | Two plated MX contacts per key; both Choc alternate lands tied to the intended corresponding contact nets. 31 left and39 right keys, maximum1.75U, no stabilizers. Selected population is MX hat sockets plus plate-lid; Choc pads stay empty. All locator/center holes remain NPTH. |
| 70 matrix diodes | Exact Diodes Incorporated1N4148W-13-F SOD-123, bottom side. Cathode band to pad1/row, anode pad2/per-key; bottom assembly must follow the mirrored pad1 marking, not a top-view guess. Actual diode nets/geometry and all per-key clearances passed. |
| Mounting and other NPTH | 8 left/9 right M1.4 mounting holes are1.60 mm unnetted NPTH with copper keepout. 195/244 total NPTH holes/slots, including one3.60x2.20 mm battery-lead slot per half; drill inspection matches every center/size. |
| Solder access | U1 oval1.80x2.40 mm /0.95 PTH and MX oval2.50x3.20 mm /1.60 PTH expose their full lands on both faces, without paste. Diode tool-approach, fillet, unrelated-pad/trace, NPTH and edge clearance checks passed. |
| Power/RF geometry | BAT+ switched to RAW/NN_B+, unswitched local GND, no inter-half battery link. Current controller/battery/service and antenna keepouts pass the source-bound geometric checks. Radio and charge performance are not inferred from clearance. |

## Primary-source orientation review

The manufacturer's [nice!nano v2 pinout and schematic](https://nicekeyboards.com/docs/nice-nano/pinout-schematic/)
were opened and the actual pinout image visually compared with both PCB pad rows.
The USB-adjacent ordinary RAW contact is battery positive; the extra top-edge
contacts are separate. Leave the charge-boost jumper open for the nominal100 mAh
pack. The manufacturer warns that bridging it increases charge current; an
unspecified cell must not be assumed to accept that current.

The manufacturer-authored [Diodes DS30086 Rev31-2 drawing](https://www.mouser.com/datasheet/2/115/ds30086-3214660.pdf)
confirms SOD-123, cathode band and exact -13-F ordering identity. Body maximum
2.85x1.70 mm, terminal span3.85 mm, height1.35 mm were compared with the owned
land and underside envelope. The enlarged1.40x1.55 mm pads at3.60 mm center
spacing are KC2 hand-solder lands, not mislabeled manufacturer recommendations.

The manufacturer-authored [BSI-10 drawing](https://amec-gmbh.de/wp-content/uploads/2022/11/BSI-10.pdf)
was downloaded and visually inspected. It shows central common1, throws2/3,
2.54 mm pitch,0.80 mm PCB holes,0.60 mm terminals,10x2.50 mm body and1.60 mm travel.
This verifies the intended physical interface. The historic `IMMS-12V_BSI-10`
value is not proof that every seller's similarly named switch is identical;
received parts must match that interface. Terminal2 versus3 changes actuator
direction, not the battery/ground topology.

The product's attached [NW3-A06-B3 drawing](https://www.devicemart.co.kr/goods/download?id=1322056&rank=1)
was also downloaded and visually inspected after the browsing interface timed
out. It shows the two-terminal normally-open circuit,6.1x3.7 mm body,2.55 mm
height and8 mm terminal span. Suggested lands have6 mm inner gap and9.5 mm
outer span, giving1.75 mm land length and7.75 mm center spacing, matching the
owned footprint. Left/right mirroring therefore does not interchange a
power-sensitive terminal or accidentally short a duplicated four-leg pair.

## DRC and fabrication exceptions

Both current source-bound DRC reports have zero hard errors, warnings and
unconnected items. The inherited exclusions are footprint_filters_mismatch,
footprint_type_mismatch, missing_courtyard, track_not_centered_on_via and
tuning_profile_track_geometries. These do not waive electrical clearance;
library identity, courtyard/body and via geometry are separately inspected.
Ordinary unrelated copper clearance remains0.30 mm. Owned footprint and current
route replay checks bind regenerated pads, masks and routing; 26 focused tests
including fresh generation/replay, fresh-process pad checks, route binding and
Fusion/housing integration passed in7.581 seconds.

Actual mask rendering, beyond a centered-flash check, found three SAME-NET
pad-opening/via overlaps:

| Side/coordinate(mm) | Pad / net | Open faces |
|---|---|---|
| Left136.500,59.400 | U1 D5 / L_COL1 | Front and back |
| Right73.500,59.500 | U1 D18 / R_COL5 | Front and back |
| Right90.754,127.917 | D27 pad1 / R_ROW3 | Back |

Each is a0.30 mm via drill. These are not unrelated-net shorts or extra mask
apertures. They can draw solder from the adjacent land during hand assembly;
inspect and replenish the joint without flooding the socket. Isolated vias
retain tenting, but **all vias fully tented is false**. No filled/capped-via
service is requested, and the remaining solder land is not masked off merely
to hide these holes. This explicit fabrication exception supersedes historical
blanket-tenting descriptions for this output set.

## Analytical limits and assembly acceptance

Read the separate socket-fit and actual-output visual reviews. The1.60 mm MX
hole has a known PCB-only1.52..1.73 mm finished range, not a guaranteed full
socket tolerance fit. Exact blade/contact-spring tolerances remain unknown.
Current5.20 mm plate stack meets the generic reference nominal geometry but
provides no additional local flange-height reserve. A9 mm under-head screw is
the calculated candidate;10 mm is a known bottoming conflict and is prohibited
for this stack. No10 mm screw is selected by this release.

After receipt and before energizing, check polarity and shorts without a battery,
then verify actual pack protection/rating, wiring and switch operation. Inspect
socket seating, continuity, solder intrusion and retention before assembling the
complete product. Preserve the SRS post-receipt contact-cycle, scanning, housing,
power and RF acceptance activities as pending. This review identifies no known
electrical/net incompatibility in the frozen PCB; it does not guarantee unknown
purchased-part tolerances or replace received-part inspection.
