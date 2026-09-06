# Actual Gerber visual review — 2026-09-06

Requirement: `CON-ARCH-004 AC-8`; supporting scope `CON-ARCH-006/007`.

## Outcome

Actual Gerber/Excellon rendering and visual inspection found no additional
missing layer, shifted hole pattern, visible unrelated-copper bridge, interrupted
outline or pad-mask omission. It **did find three same-net via/pad-mask overlaps**
that the earlier coincident-flash-only tenting check did not detect. Therefore
the earlier check must not be described as proving every via is fully tented.
This report is an output inspection record, not an order or physical-fit approval.

## Inputs and method

Inputs are the eleven actual manufacturing layers per half under
`hardware/kicad/fabrication_review/mx-receptacle-20260906/{left,right}`:
two copper, two mask, two silk, two paste, outline, PTH and NPTH files.
Drill-map Gerbers are explicitly excluded from the layer stack.

The KiCad MCP skill was read and its tool inventory checked. Available board
SVG exports would render source boards, not these delivered Gerbers, so a
separate Gerber renderer was used. [Gerbonara documentation](https://gerbolyze.gitlab.io/gerbonara/)
describes its Gerber/Excellon parsing and aperture-macro rendering support.

`tools/render_kc2_gerber_visual.py` uses isolated Gerbonara 1.6.3, resvg-py 0.5.0
and Pillow 12.3.0. Three requirement-linked tests passed after an initial failing
import; the raster test verifies a synthetic Gerber dark disk/clear disk cutout.
No PCB or manufacturing-input file was edited. Input bytes were hashed before
and after rendering and unchanged. The parser warned about KiCad's `G90` after
the Excellon header; actual drill geometry was independently compared with the
boards in the preceding raw-output audit, with no missing/extra holes or slots.

The 62 SVG/PNG views and their hashes are recorded in
`hardware/kicad/fabrication_review/mx-visual-20260906/manifest.json`.
All views use PCB top-coordinate orientation; bottom layers are **not** mirrored
into physical bottom-view orientation. Colored overlays use red for the selected
layer, blue for outline, white for PTH drilling and dark gray for NPTH drilling.
In mask views, red means an **opening**, not solder-mask material.

## Visual coverage and findings

Both halves were examined at full-board scale for front/back copper, front/back
mask with drilled holes and complete outline, both silkscreens and both paste
layers. All 24 non-overlapping copper tiles were viewed, covering both copper
layers on both halves at higher resolution. Service closeups were examined for
U1, POWER, RESET, J_BAT and the lead slot. The repeated key patterns include
the enlarged MX lands, retained Choc SMD pads, diode lands and locator holes.

| Area | Observed output |
|---|---|
| Copper and outline | Complete left/right patterns and stepped outlines; no visible unexpected bridge, displaced layer or edge truncation. Cross-layer connections terminate at the exported via holes. Automated connectivity/DRC remains the stronger net-level evidence. |
| U1 / MX lands | Enlarged oval copper and matching mask openings; component PTH drills centered in the intended lands. Adjacent U1 apertures remain separate. |
| PTH / NPTH | Left 118/195 and right 166/244 records match source positions, sizes and plating in the independent raw audit. Each half has one 3.6 × 2.2 mm lead slot; 8/9 mounting holes remain NPTH. |
| Paste | Front paste only at RESET SMD lands; bottom paste at diode/alternative Choc SMD lands. No U1/MX PTH paste apertures. No stencil or machine-placement instruction is implied. |
| Silkscreen | U1 pin labels and USB-side labels, POWER/RESET and battery polarity legends present; 8/9 MH references present. Bottom diode cathode marks present. The earlier glyph-signature audit also passed. |
| Mask/vias | No separate via-centered mask flashes, but three vias intersect same-net pad apertures as detailed below. |

## Explicit via-tenting exceptions

All three vias have nominal 0.60 mm copper diameter and 0.30 mm drill.
Board pad/net identity was read independently with pcbnew and confirmed by the
parent review. These are **not unrelated-net shorts**.

| Half / via center (PCB mm) | Same-net pad | Exposed side(s) | Nominal geometric observation |
|---|---|---|---|
| Left (136.500, 59.400) | U1 D5, `L_COL1`, center (136.5225, 58.3700) | F/B | Entire drill disk is inside the oval opening; about 0.01965 mm remains between drill edge and nearest opening edge. |
| Right (73.500, 59.500) | U1 D18, `R_COL5`, center (73.5900, 58.3700) | F/B | Drill disk intersects the rounded end of the oval; calculated nominal exposed disk area is about 75.38%. |
| Right (90.754, 127.917) | D27 pad 1, `R_ROW3`, center (90.2125, 127.6750) | B only | Entire drill disk is within the diode land opening, with a minimum nominal 0.0085 mm residual edge distance. |

U1's primary 0.95 mm component holes remain separate from these via holes.
The expanded lands remain exposed; no mask was added over their soldering area
to conceal the exceptions. Nevertheless these unfilled/un-capped holes can wick
solder, especially at D27; hand-solder inspection must check wetting and replenish
solder as needed. This is a known assembly risk, not a claim of tested wetting.

The production profile must accurately distinguish tented isolated vias from
these same-net pad-overlap exceptions and must not request filled/capped vias
without a separately specified process. The SRS's adjacent exposed-pad mask-web
criterion is not evidence that same-net pad-contained vias are fully tented.

Useful views: `left-F_Mask-service.png`, `right-B_Mask-service.png`,
`right-B_Mask-holes.png`, and `right-B_Cu-tile-0-0.png` in the visual directory.

## Evidence limits

Visual inspection is finite-resolution human/model inspection, not an exhaustive
polygon Boolean proof. It supplements, rather than replaces, actual net checks,
source/output geometry comparisons, DRC and manufacturing review. Nominal
Gerber geometry does not measure manufactured mask registration, plating, hole
tolerance, wetting, switch fit, housing fit or reliability. No new physical test
result, requirement verification status or order approval was created here.
