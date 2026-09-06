# V1-inclusive r3 actual Gerber visual review

Date: 2026-09-06. Requirements: `CON-ARCH-004` AC-8, `OPS-ARCH-007`.
Independent read-only visual review; not complete order approval or physical qualification.

## Bound inputs and coverage

Inspected all **62 actual rendered PNGs** in
`hardware/kicad/fabrication_review/v1-recess-visual-20260906-r3/`:

- Both halves: nine individual Gerber layer fullboards and separate PTH/NPTH fullboards (22 images).
- Both halves: F.Cu/B.Cu and F.Mask/B.Mask hole overlays and controller/service zooms (16 images).
- Both halves: all six F.Cu and all six B.Cu spatial tiles, indices `0-0`, `0-1`, `1-0`, `1-1`,
  `2-0`, `2-1` (24 images), showing copper, drill holes and edge overlay together.

These are top-coordinate views. The bottom layers are **not physically mirrored**; do not use the
displayed left/right orientation as a bottom-assembly instruction.

The render manifest raw SHA-256 is
`f65ea94d7bc55a264c0391897c760f302b83708e832d7b47e1e0de98ed1a5770`.
All 124 PNG/SVG hashes were independently recomputed and matched the manifest. All 22 rendered input
hashes were independently compared with the current Protel-extension Gerbers and separate PTH/NPTH
drills under `hardware/kicad/fabrication_review/v1-recess-20260906-r3/{left,right}/`; all matched.

Canonical PCB raw SHA-256 at inspection:

- Left: `568e1427e4cfb9d667b6d5b3754da3a4e24c924abfa85a8dfe394dd050b5fe67`.
- Right: `88290c3b0cf3951d56221d216549665c0576a816a6315012f7f12b027f402577`.

## Observations

No new visual fabrication blocker was found in the inspected images.

1. All copper tiles show the added lateral locator holes clear of copper. The rotated MX land is
   visibly separated from its adjacent locator opening; curved/dogleg routes go around those holes.
   No visibly clipped annulus, copper-through-NPTH path or unexplained continuous copper bridge was
   found. Exact numeric clearances remain the responsibility of current DRC/geometry reports, not pixels.
2. Both enlarged controller pad rows have separate oval copper lands with centered PTHs and full
   nominal mask exposure. Front/back MX electrical lands likewise retain exposed annuli. The masks
   expose mechanical openings, not copper rings around NPTHs.
3. Front paste has only the two reset SMD apertures per half; no controller or MX PTH paste was seen.
   Bottom paste shows the diode/socket SMD pattern, not MX receptacle apertures. This is not permission
   to populate mutually exclusive Choc and MX assemblies together.
4. Service zooms show separated power/reset/battery pad geometry and an unobstructed battery lead
   slot. Front silk contains controller pin labels, USB_OUT_LEFT/RIGHT, B+/B-/GND, PWR direction and
   RST labels. Visual review alone does not prove those nets or manufacturer's pin identities.
5. Edge fullboards show the intended continuous split-keyboard perimeter and controller tab, with no
   apparent duplicate board or stray internal outline. PTH and NPTH fullboards are separate; locator,
   center, mounting and lead-slot geometry appears in the NPTH rendering.
6. Bottom silk retains sparse diode cathode-side marks. Mounting-hole identifiers are present on front
   silk. Neither fullboard silk view is an exact silk-to-mask clearance measurement.

## Retained visible solder-wicking exceptions and limits

The controller service views still show the known same-net pad/via overlap at left U1 D5 and right
U1 D18; the right bottom mask also exposes a small via within the D27 pad region. These are not all-vias-
tented designs. Same-net identity is established by separate PCB/net review, not inferred from these
single-color images. Preserve the disclosed solder-wicking caution; these pictures do not qualify
hand-solder technique or eliminate the need to keep solder out of receptacle contacts.

Raster review cannot prove micron-scale clearance, plated-hole tolerances, spring contact force,
exact switch insertion depth, keycap travel, or mechanical strength. Current source-bound DRC,
component/pin/net checks, CAD/native/1:1 evidence and final package checks remain separate gates.
This review neither reuses old r2 artwork as current nor claims that unresolved selected-part
dimensions or post-receipt tests have passed.
