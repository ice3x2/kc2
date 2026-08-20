# KC2 X3 V2 draft lower housing

Requirement: `CON-ARCH-006`.

These files are generated only from the current 32-key left and 39-key right
draft V2 boards. They do not reuse the promoted 77-key housing or its REG/H
registration pattern.

## Load path

- The PCB bottom is at Z `3.90 mm` over a `1.20 mm` floor and `2.70 mm`
  component cavity.
- Clearance-cut perimeter rails terminate at exactly Z `3.90 mm`, so the PCB
  has zero nominal vertical support gap without screw preload.
- Copper-aware `3.20 mm` posts are distributed in `seam`, `thumb`, and `span`
  categories. The measured worst switch-center distance to a rail/post contact
  is `15.552 mm` left and `16.971 mm` right.
- There are no PCB registration pegs, PCB screw pilots, or PCB fastener
  bosses. Glue is not assumed; case-part joining remains separate from the
  typing-load path.

## 150 mm printable right split

The left housing is one printable part. The right housing is exactly two parts
and has no stale monolithic STL:

- left: `134.9125 x 126.5500 x 3.9000 mm`;
- right part A: `91.7438 x 92.0500 x 3.9000 mm`;
- right part B: `81.6438 x 126.5500 x 3.9000 mm`.

Every STL is one watertight shell and fits the `150 mm` cube. The right parts
use a `10.0 mm` overlap lap and exactly two
[`SUNCO CSPSL-ST3W-M2-3`](https://jp.misumi-ec.com/vona2/detail/221005676627/?HissuCode=CSPSL-ST3W-M2-3)
M2x0.4 x 3.0 mm trivalent-white Phillips #0 slim-head screws. This exact M2X3 SKU is present in
the official catalog. The official head range is 3.5--4.0 mm diameter and
0.4--0.6 mm high; JIS B 1111 gives the length a `0/-0.3 mm` tolerance. Do not
substitute another screw length. Adhesive is neither required nor assumed.

The generator strips only trailing spaces and tabs from exported STEP/STL
lines while preserving their original newline bytes. The manifest and verifier
hard-check `step_has_trailing_whitespace=false` for both STEP files.

Install both screws upward from the exterior bottom. Part A contains the head
recess and bearing collar: the head seats at Z `0.70 mm`, a 2.40 mm shank hole
continues upward, the 4.40 mm recess provides 0.20 mm radial print clearance,
and the 5.40 mm collar retains a 0.50 mm radial wall and 0.55 mm minimum-head
bearing annulus. Part B starts its 1.60 mm blind receiving pilot at Z `0.85 mm`,
ends it at Z `3.60 mm`, and closes the 3.20 mm receiving boss at Z `3.85 mm`.

Worst-case calculations apply `+/-0.05 mm` independently to the part-A head
seat and part-B pilot/boss surfaces. The result is a `0.05--0.25 mm` clamp
stack, `2.65 mm` usable pilot depth for `2.60 mm` maximum threaded penetration,
`2.10 mm` effective thread engagement against the `1.50 mm` minimum, a
`0.15 mm` blind cap, and no exterior head protrusion. The maximum head remains
`0.05 mm` above the exterior bottom and the maximum-length screw tip stops at
Z `3.75 mm`. Applying the part-B boss tolerance independently leaves `0.05 mm`
to the boss top; independently lowering the PCB support plane leaves `0.10 mm`
to the PCB bottom at nominal Z `3.90 mm`. Both unrounded formulas have a
`0.05 mm` hard minimum.

Driver verification uses a separate Phillips #0 shaft envelope of 3.0 mm
diameter by 20.0 mm extending downward from the exterior head; it does not reuse the head and
collar envelope. Actual STEP intersection volume is zero for both head and
driver cylinders. Board-feature, rail, and support collision counts are also
zero.

## Digital clearance evidence

`kc2_x3_v2_housing_clearance.json` regenerates its checks from the current
KiCad boards and verifies zero intersections for:

- Choc V2 socket bodies and 0.30 mm solder-fillet envelopes;
- MX pins, pads, and 0.30 mm solder-fillet envelopes;
- diode bodies, pads, and 0.30 mm solder-fillet envelopes;
- routed copper tracks and vias;
- nice!nano/controller/reset geometry;
- battery-lead access; and
- switch/key travel, by the disjoint support/contact Z envelope.

The manifest records every support category, coordinate, diameter, top Z,
nominal gap, split-joint dimension, fastener envelope, printable-part bound,
current source-board SHA-256, and generated STEP/STL SHA-256.

Regenerate and verify with:

```powershell
python -m tools.generate_kc2_x3_v2_housings
python -m tools.verify_kc2_x3_v2_housing
python -m unittest tools.test_verify_kc2_x3_v2_housing -v
```

## Remaining physical gate

This is digital clearance and geometry evidence only. `CON-ARCH-006` AC-7 is
still pending: the printed, assembled housing must pass the 2.0 N load test at
the worst spans with no more than 0.30 mm downward PCB displacement. These
draft files are therefore not fabrication/order-readiness approval.
