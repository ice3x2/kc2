# MX receptacle contact follow-up — 2026-09-06

Scope: `CON-ARCH-004` AC-3/AC-9 and `OPS-ARCH-007` AC-1/AC-3/AC-4. Read-only supplementary investigation; no PCB, hole, CAD, existing review or release-bound file changed. This is not a new requirement or a physical PASS. Physical acceptance remains post-receipt, without a separate sample-order prerequisite.

## Findings and source separation

The selection remains the [seller's 3.00 mm open-bottom hat socket](https://ko.aliexpress.com/item/1005010364025678.html), barrel OD 1.45 mm, flange OD 2.00 mm and thickness 0.20 mm. The [selected drawing](https://ae-pic-a1.aliexpress-media.com/kf/S4b47dab427cd4b539a50618bf16a62d9J.jpg) was visually inspected from its cached original, `.codex-tmp/hat-seller-3.jpg`; raw SHA-256 `0bdb35b93473ce078fcd53aafcb68abb7cc7c5bdea75106ccb31a1afc4d260fc`. The photo of a socket on an unspecified switch illustrates intended use, not dimensional/contact qualification. Live AliExpress and direct image requests failed in this session.

The user's `C:/Users/ice3x/Downloads/S657430a83660460db43891c66b7614bby.avif` is a DIFFERENT, closed-bottom **4.00 mm** socket drawing. It explicitly labels pin diameter **0.64–0.90 mm**, internal depth 3.60 mm and OD 1.45 mm. Its raw SHA-256 is `0f9f116f40288921a6582c87c4f0c501686a4024276dc2009618655737491ce9`. It was decoded in memory for viewing, without modifying the file. Neither that round-pin range nor a different Mill-Max contact specification applies to the selected open-bottom part.

The selected drawing does **not** dimension mouth ID, blade width/thickness range, spring start/end depth, insertion force, contact resistance, plating or production tolerances. No additional controlled selected-part contact drawing was found by this bounded search. Do not infer dimensions by scaling its illustrative cross-section.

The manufacturer-authored [archived Cherry MX drawing](https://www.farnell.com/datasheets/1792245.pdf), page 2, provides the generic 5.0 mm under-flange body and 3.30 mm exposed contact length; its PCB grid is 1.27 mm. It does not dimension the blade cross-section in the inspected drawing. The [current Cherry MX2A download page](https://www.cherry.de/en-gb/product/mx2a-black/downloads) was reachable, but its English datasheet endpoint returned HTTP 403; the old developer endpoint also failed. No numeric blade size or exact user's-switch identity is invented from these results. Internal switch contact-resistance figures would not qualify the separate receptacle interface.

## Hole, flange and solder land: conditional calculations

The [current JLCPCB capability table](https://jlcpcb.com/capabilities/pcb-capabilities) specifies ordinary through-hole tolerance +0.13/−0.08 mm, hole position ±0.05 mm, and 1.60 mm board thickness ±10%. Thus the selected hole's PCB-only range is 1.52–1.73 mm. It also permits 1:1 pad/mask openings; this is not a promise of zero physical mask misregistration. No numerical registration tolerance was found on the inspected page.

The following are engineering calculations, holding the seller's barrel/flange at nominal. They are **not** complete production tolerance bounds:

| Quantity | Calculation / result (mm) |
|---|---|
| Nominal radial barrel clearance | (1.60−1.45)/2 = 0.075 |
| Radial float at largest hole | (1.73−1.45)/2 = 0.140 |
| Centered flange bearing beyond largest hole | (2.00−1.73)/2 = 0.135 |
| Far-side bearing at maximum socket eccentricity | 0.135−0.140 = −0.005 |
| Centered exposed top land beyond flange, minor/major axes | (2.50−2.00)/2 = 0.250; (3.20−2.00)/2 = 0.600 |
| Conditional minor-axis lip with aligned adverse displacement | 0.250−0.140−0.050 = 0.060 |
| Minor-axis copper ring at largest drilled hole and 0.05 offset | (2.50−1.73)/2−0.05 = 0.335 |

The −0.005 result means a tiny locally uncovered crescent is possible at maximum eccentricity. It does **not** mean complete loss of flange retention: the nominal 2.00 mm flange remains larger than the 1.73 mm hole. It does mean the flange cannot be treated as a reliable complete solder seal.

The KiCad oval is a rounded capsule, not a 2.50 by 3.20 rectangle or an ellipse. In local coordinates it is a vertical segment from Y=−0.35 to +0.35 swept by a radius-1.25 circle. For a nominal radius-1.00 flange displaced by `(dx,dy)`, ideal full-boundary clearance is:

`0.25 − sqrt(dx² + max(abs(dy)−0.35, 0)²)`.

Thus a major-axis 0.60 mm allowance is not available in every direction. The 0.060 mm figure is an ideal single-axis calculation, before flange/OD tolerance, copper etch, mask shift and mask-size error; it is **not a guaranteed minimum exposed solder lip around a manufactured socket**. Treating ±0.05 as independent global-axis errors gives a conservative displacement norm allowance of 0.07071 mm, and the cruder inscribed-circle bound is only 0.03929 mm before those same unknowns. Current axis-aligned oval geometry is less pessimistic than that generic bound, but neither calculation establishes physical wettable land. An inward mask-edge error can consume a small lip despite zero nominal mask expansion. Do not enlarge the hole or mask spec blindly to fix an unmeasured condition.

## Pin pitch and assembly alignment

Read-only parsing of both canonical PCBs found exactly 31 left and 39 right electrical pairs. Every pair has absolute X/Y separation **6.35/2.54 mm**, giving `sqrt(6.35²+2.54²) = 6.839159305 mm`. Rotated key positions preserve this pair geometry. Arithmetic and all-70-pair assertions passed in KiCad Python. No pad or route was saved.

Two independently floating sockets can change their relative axis spacing by up to 0.28 mm from barrel clearance alone at the largest hole. Adding opposite 0.05 mm drill-position errors gives a conservative **0.38 mm per-axis** deviation from nominal for an unfixtured pair; simultaneous X/Y extrema are not independent because each socket's radial float is circular. This is an alignment risk, not a measured pin interference. At the smallest hole, each nominal socket has only 0.035 mm radial self-alignment freedom; actual pin positioning and contact compliance remain unknown.

Minimum practical improvement: use the actual two switch blades together, with the switch seated in the intended plate and its center/locator geometry correctly registered, as the alignment jig during hand soldering. Keep both flanges seated without side load; do not solder all loose sockets first and expect the switch to force them into alignment. Tack, cool, remove/reinsert and check seating before completing joints. Keep solder out of the open spring passage and avoid excessive heat to the inserted switch/printed plate. This is an assembly recommendation, not a new fixture CAD design or a passed heat/force specification. Do not grind the blades or flood the sockets to compensate for wrong parts.

## Axial reach and remaining unknown contact engagement

Using the existing [reviewed nominal stack](kc2-first-order-socket-fit-2026-09-06.md): plate top is 5.20 mm above PCB top, generic body depth is 5.00 mm, hence switch underside and flange top meet at +0.20 mm. Socket bottom is −2.80 mm; a generic 3.30 mm pin reaches −3.10 mm. The tip projects **0.30 mm through the open end**. This does not bottom out, but does not prove spring engagement or continuity.

At board thickness 1.44/1.60/1.76 mm, nominal socket protrusion below PCB is 1.36/1.20/1.04 mm; pin protrusion is 1.66/1.50/1.34 mm. Those numbers exclude seller tolerances and added solder. The flange/body meet with zero additional nominal height reserve; body recesses, flange height and actual printed stack may change seating. This remains a disclosed assumption, not a known collision for the selected nominal geometry.

## Disposition

No new demonstrated nominal incompatibility justifies changing the **1.60 mm PTH**, selected socket or PCB geometry. Newly clarified process risks are socket eccentricity, reduced local solder lip, mask registration and two-contact alignment. Keep them visible in assembly guidance and inspect the received product's insertion/replacement/continuity/wetting/retention under the existing SRS acceptance criteria. Exact blade/contact dimensions and supplier tolerances remain unknown, not failed and not passed. This report does not alter the existing first-order release or certify any physical acceptance criterion.
