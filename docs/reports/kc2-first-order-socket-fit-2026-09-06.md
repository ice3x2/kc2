# KC2 first-product MX socket and stack review — 2026-09-06

Requirements: `CON-ARCH-004`, `CON-ARCH-006`, `OPS-ARCH-007` (in progress / evolving). This is dimensional research, not a second requirements source or complete fabrication approval. The user's first order is the product; no separate pre-order coupon is required. Physical tests remain pending after receipt, not passed or waived. No PCB/CAD geometry was changed for this report.

## Evidence and selected dimensions

The selected [seller product](https://ko.aliexpress.com/item/1005010364025678.html) [hat-style drawing](https://ae-pic-a1.aliexpress-media.com/kf/S4b47dab427cd4b539a50618bf16a62d9J.jpg) specifies total length **3.00 mm**, barrel OD **1.45 mm**, flange OD **2.00 mm**, flange thickness **0.20 mm**, and an open bottom. It does not specify dimensional tolerances, entry ID, accepted flat-blade section, spring position, contact length, force, or resistance. The drawing was visually inspected from the locally cached original image; live AliExpress product access failed. The 3.50 mm hatless and prior 4.00 mm alternatives are not this selection. “Mill-Max compatible” does not transfer another manufacturer's tolerances or contact specification.

The manufacturer-authored [Cherry MX drawing, archived by Farnell](https://www.farnell.com/datasheets/1792245.pdf), visually inspected pages 2 and 5, provides this generic reference:

| Reference feature | Drawing value | Interpretation |
|---|---:|---|
| Under-flange body depth | 5.0 mm | Reference switch underside datum |
| Exposed contact length | 3.30 mm | From body underside to tip |
| Frame top above PCB | 0.197 +0.012 inch | Approximately 5.00 to 5.31 mm; not symmetric ±0.012 |
| Square opening | 0.551 ±0.002 inch | 13.9954 ±0.0508 mm |
| Corner radius maximum | 0.012 inch | 0.3048 mm |
| Frame thickness | 0.060 ±0.004 inch | 1.524 ±0.1016 mm |

The 1.50 mm candidate plate is within that reference thickness interval. This archived generic drawing is not a controlled drawing of the user's exact switch, and does not establish FDM dimensional accuracy or keycap clearance. Its inspected views do not dimension the contact blade width/thickness. No numeric blade cross-section is invented here.

## Finished hole and solder land

[JLCPCB published capabilities](https://jlcpcb.com/capabilities/pcb-capabilities) give ordinary PTH diameter tolerance +0.13/−0.08 mm, hole position ±0.05 mm and 1.60 mm PCB thickness ±10%. These are the known fabrication bounds; seller socket tolerances remain unknown.

| Calculation | Result |
|---|---:|
| Finished 1.60 mm PTH | 1.52–1.73 mm |
| Diametral clearance to nominal 1.45 mm barrel | 0.07–0.28 mm; nominal 0.15 mm |
| Radial clearance | 0.035–0.140 mm; nominal 0.075 mm |
| Conservative minor-axis copper ring, 2.50 mm land | (2.50−1.73)/2−0.05 = 0.335 mm |
| Centered flange overlap at largest hole | (2.00−1.73)/2 = 0.135 mm |

These are **PCB-only bounds with the socket held nominal**, not full worst-case production fit. Guaranteed non-interference requires actual maximum barrel OD below 1.52 mm, with additional assembly clearance desired. Increasing the drill without a demonstrated need reduces flange bearing and annular ring. At maximum hole/barrel eccentricity (0.140 mm), the nominal flange need not cover the entire hole circumference; this is not complete loss of retention, but supports centering the receptacles with the correctly seated switch/plate during soldering. Prevent solder entering the spring.

No known barrel/hole interference follows from the supplied nominal values. An unknown seller OD tolerance is a disclosed procurement risk, not evidence that interference already exists.

## Vertical stack, open bottom and contact engagement

Engineering assumptions: generic 5.0 mm under-flange body; 3.30 mm exposed pin; socket flange sits on PCB top; no beneficial recess in the switch underside; current plate top is 5.20 mm above PCB top, with a 1.50 mm plate and 3.70 mm hard stop. Dimensions below are calculations, not measured assemblies.

Taking PCB top as zero:

| Feature | Nominal Z (mm) |
|---|---:|
| Plate top / bottom | +5.20 / +3.70 |
| Switch underside and nominal flange top | +0.20 |
| Socket bottom | −2.80 |
| Switch contact tip | −3.10 |

The nominal switch underside meets the flange top with **zero additional local height reserve**. Unknown body/flange/print tolerances can affect seating; the archived frame-spacing interval is not proof of a clearance allowance inside every MX clone. The pin extends 0.30 mm through the open socket bottom, which is not a bottoming collision. Axial reach alone cannot prove spring engagement: the seller gives neither spring start/end positions nor usable contact travel.

For PCB thickness 1.44–1.76 mm, socket protrusion below PCB is 1.04–1.36 mm (nominal 1.20); pin protrusion is 1.34–1.66 mm (nominal 1.50). The lower support plane at Z=2.50 and desk at Z=−1.00 provide 3.50 mm below-PCB space. Thus nominal socket/pin desk clearances are 2.30/2.00 mm; PCB-only minima are 2.14/1.84 mm. Subtracting a separate 0.30 mm print allowance leaves 1.84/1.54 mm, **before unknown socket/pin tolerances and solder protrusion**. Do not label 1.20 mm socket protrusion a maximum envelope.

For blade width `w`, thickness `t`, and a rigid circular mouth ID `d`, `sqrt(w*w+t*t) <= d` is a useful geometric entry check, but not a contact-force/elastic-spring qualification. None of these three selected-part dimensions is available here. A different branded receptacle's round-pin range cannot resolve this flat-blade question.

## Long-screw length candidate, not an exact part approval

Current stack places the under-head bearing face 6.80 mm above receiver entry; receiver pilot depth is 2.80 mm. For an under-head screw length `L`, nominal insertion is `L−6.80`, and bottom reserve is `9.60−L`.

| Under-head length | Nominal insertion | Nominal bottom reserve | PCB-only insertion range |
|---|---:|---:|---:|
| 8.00 mm | 1.20 mm | 1.60 mm | 1.04–1.36 mm |
| **9.00 mm candidate** | **2.20 mm** | **0.60 mm** | **2.04–2.36 mm** |
| 10.00 mm | 3.20 mm | −0.40 mm | 3.04–3.36 mm |

A 10 mm under-head screw is a **known geometric bottoming conflict** with this unmodified stack. A 9 mm candidate balances insertion and reserve better than 8 mm, without changing geometry. Its PCB-only bottom reserve is 0.44–0.76 mm. Full thread engagement is less than insertion when the point or incomplete threads occupy the tip. Screw length tolerance, pilot depth/print error, head seating error and point length are not yet supplied; combined adverse length/depth errors must remain below 0.44 mm to avoid bottoming at the known PCB-thickness bound. This is not a thread-strength or torque qualification. Retain the required non-countersunk head envelope ≤3.00 mm diameter ×1.20 mm height and verify actual thread form against the printed pilot before selecting a purchasable screw.

## Decision and post-receipt checks

The selected hat socket has **no demonstrated nominal hole or open-bottom vertical incompatibility**. Remaining unknowns are actual barrel/flange tolerances, exact MX blade and underside geometry, spring contact/force/resistance, printed aperture/clip fit, solder envelope, and exact fastener tolerances. These are explicit first-product residual risks under `OPS-ARCH-007`; they are not fabricated PASS evidence and do not independently require a separate pre-order sample.

After receipt, inspect the actual product parts: finished hole/OD and flange seating; both switch contacts' insertion, continuity and retention; final plate opening and clip seating; solder intrusion/bridges and underside clearance; actual screw tip reserve and progressive tightening; keycap full travel and service-driver access. Use the physical acceptance definitions in the SRS. A known incorrect part, interference, electrical error or stale output still blocks first-order approval. Full-board electrical, component, Gerber/drill, 1:1 and upper-head/keycap checks remain separate mandatory digital review work.

## Inspectable 1:1 and native geometry evidence

New [left 1:1 overlay](../../hardware/case/kc2_left_first_order_1to1.svg) and [right 1:1 overlay](../../hardware/case/kc2_right_first_order_1to1.svg) use actual current PCB Edge.Cuts and drilled switch, U1 and MH centers read by KiCad from byte-identical temporary snapshots. Black is PCB outline; blue is the nominal 14 mm plate aperture at each actual switch center; red is U1 drill geometry; green is MH; orange is switch electrical/mechanical drill geometry. SVG physical width/height are in millimetres with one viewBox unit per millimetre. Print at actual size, never fit-to-page. These drawings show geometric alignment, not exact switch-body/keycap silhouettes or full-travel qualification. The [overlay manifest](../../hardware/case/kc2_first_order_1to1_manifest.json) binds both source and SVG hashes and records all extracted coordinates.

The new helper `tools/generate_kc2_first_order_overlay.py` is read-only for boards and fails closed on unsupported non-segment outlines, slots, unexpected key/U1 counts or concurrent source changes. Requirement-linked automated tests were first run RED (missing implementation), then GREEN (2 tests), checking physical units, exact aperture/pad centers and absent-outline rejection. Regenerate with KiCad Python after any PCB change; a report link alone does not prove freshness.

Both overlays now include a visible legend, 50 mm calibration bar and 100% print instruction. The footer requirement was tested RED before implementation and the 2 tests passed again afterward. An independent reviewer inspected the original registration drawings and found no clipped outlines or misplaced visible aperture/drill patterns; that inspection does not establish controller-body, keycap or full-travel fit.

Existing [left upper plan](../../hardware/case/kc2_left_mx_upper_plan.svg), [right upper plan](../../hardware/case/kc2_right_mx_upper_plan.svg) and [dimensioned mounting Z section](../../hardware/case/kc2_mx_mounting_section.svg) show the candidate split/lid and stack. The Z section is explicitly an enlarged diagram, not the 1:1 board print template.

Native upper geometry: [left STEP](../../hardware/case/kc2_left_mx_upper_housing.step), [right STEP](../../hardware/case/kc2_right_mx_upper_housing.step), [left F3D](../../hardware/case/kc2_left_mx_upper_housing.f3d), [right F3D](../../hardware/case/kc2_right_mx_upper_housing.f3d). Native lower geometry: [left STEP](../../hardware/case/kc2_left_lower_housing.step), [right STEP](../../hardware/case/kc2_right_lower_housing.step), [left F3D](../../hardware/case/kc2_left_lower_housing.f3d), [right F3D](../../hardware/case/kc2_right_lower_housing.f3d). All four native round trips are indexed by the [Fusion result](../../hardware/case/kc2_fusion_export_result.json). Native round-trip dimensional equality is not physical fit evidence. The overlay manifest explicitly uses raw-byte SHA256, whereas the main CAD evidence uses `tools.canonical_hash` newline-normalized hashes; compare like policies rather than interpreting CRLF differences as geometric changes. Actual PCB geometry changes require existing CAD manifests to undergo exact-geometry rebinding or regeneration checks; the new current-coordinate SVG does not silently requalify old CAD.

## All-17 head / keycap travel projection review

Read-only calculation uses current overlay coordinates, `make_left_keys_x3_v2` / `make_right_keys_x3_v2` key widths and the same keycap rectangle formula as `tools.verify_kc2_x3_v2_outline.keycap_bounds`: half-size = key unit dimension ×19.05/2−0.50 mm. Heads are radius 1.50 mm discs. Exact circle-to-rectangle distance is `hypot(max(abs(dx)−half_width,0), max(abs(dy)−half_height,0))−1.50`; negative means overlap, not a measured collision depth. The plate check uses 7 mm half-width apertures. Current switch rotations are multiples of 90 degrees, so those square apertures are unchanged by rotation.

| Side / mount | Nominal keycap projection | Nearest cap | Head-to-aperture gap (mm) | Existing head-to-installed-component XY gap (mm) |
|---|---|---|---:|---:|
| Left MH1 | clear 24.000 mm | SW5 | 26.0250 | 2.7292 |
| Left MH2 | clear 0.750 mm | SW6 | 2.7750 | 1.9750 |
| Left MH3 | overlaps | SW14 | 2.3062 | 1.5062 |
| Left MH4 | overlaps | SW14 | 3.1750 | 1.7705 |
| Left MH5 | overlaps | SW28 | 3.3937 | 2.5937 |
| Left MH6 | overlaps | SW30 | 7.2562 | 6.2565 |
| Left MH7 | overlaps | SW31 | 2.4187 | 1.6187 |
| Left MH8 | overlaps | SW21 | 2.1375 | 1.3375 |
| Right MH1 | clear 23.750 mm | SW3 | 25.7750 | 2.5738 |
| Right MH2 | tangent; zero reserve | SW2 | 2.0250 | 1.2250 |
| Right MH3 | overlaps | SW16 | 4.5813 | 3.1136 |
| Right MH4 | overlaps | SW16 | 2.4187 | 1.6187 |
| Right MH5 | overlaps | SW23 | 2.4125 | 1.6069 |
| Right MH6 | overlaps | SW34 | 3.5750 | 1.6379 |
| Right MH7 | overlaps | SW34 | 5.6812 | 4.2957 |
| Right MH8 | overlaps | SW35 | 2.1062 | 1.3062 |
| Right MH9 | overlaps | SW23 | 2.4000 | 1.2429 |

Thus **13 heads overlap nominal cap projections and one is tangent**. These positions cannot be cleared for full travel merely from plan views. No head intersects the nominal plate aperture; the minimum aperture gap is 2.025 mm. The last column is read from the current lower housing manifest's per-hole `head_to_installed_component_mm`. Its implementation computes 2D separation from the union of 15.60 mm switch-service rectangles, component features including controller/socket/reset geometry, and battery/POWER body/sweep geometry. Positive plan gaps exclude intersection with those modeled envelopes irrespective of Z, but do not qualify missing or larger actual part shapes. Keycaps are explicitly excluded by its keycaps-off service assumption.

The actual upper head envelope is **Z=9.30–10.50 mm**, not the old head-on-PCB 4.10–5.30 mm envelope. At every overlapped head location, the selected keycap's underside throughout the full keystroke must remain above the head. A proposed **0.30 mm engineering assembly reserve** makes the interface requirement underside ≥10.80 mm at the nominal stack, equivalently ≥1.50 mm above plate top. This reserve is an assumption for this review, not a supplied keycap tolerance. An exact cap underside/travel model is unavailable, so that condition is **unproven**, not PASS and not a demonstrated 3D collision. PCB-thickness movement shifts head and plate together; it does not supply missing local cap-to-head clearance.

This is a high-risk conditional mechanical interface for the first **PCB-fabrication-only** release, not approval to buy unspecified keycaps/fasteners or a claim that the printed full assembly is qualified. A compatible cap may satisfy it; otherwise a separately reviewed cap/fastener/housing change may be needed. Do not assume relief is possible or silently modify the current geometry. The candidate 9 mm screw remains conditional on both the axial pilot calculation and this actual head/cap interface. A later proven underside collision remains a real fit error regardless of verification phase.
