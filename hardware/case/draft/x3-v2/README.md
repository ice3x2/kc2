# KC2 X3 V2 draft lower support plate

Requirement: `CON-ARCH-006`.

These files are generated only from the current 31-key left and 39-key right
draft V2 KiCad boards. They do not reuse the promoted 77-key housing or any
REG/H registration pattern.

## Construction and load path

- The lower housing is a nominal `2.50 mm` constant-Z support plate from
  exterior bottom `Z=0.00 mm` to PCB support plane `Z=2.50 mm`.
- There is no raised key-field bezel. The housing outline is inset `0.10 mm`
  from the PCB outline, preserving the keycap-concealed edge requirement.
- Clearance-cut perimeter regions and distributed `2.00 mm` support datum
  regions terminate at exactly Z `2.50 mm`, so the PCB has zero nominal
  vertical support gap without screw preload.
- The generated support set contains 14 left and 13 right seam/thumb/span
  regions. The measured worst switch-center distance to support is
  `14.9304 mm` left and `18.4727 mm` right; seam distance is `2.85 mm`
  on both halves.
- There are no PCB registration pegs, screw pilots, or fastener bosses. PCB
  retention remains intentionally unresolved; the plate provides the vertical
  typing-load path, but physical retention and deflection still require a
  printed first article.

## Exterior-open underside clearances

The plate is cut completely through from Z `0.00` to `2.50 mm` wherever a
bottom-side assembly envelope is required. The generated STEP volume is
independently compared with the cutout-differenced support plan, and every
required envelope has zero residual intersection volume.

The verified openings cover:

- Choc V2 socket bodies and solder-fillet envelopes;
- all switch center and locator NPTH/mechanical-pin continuations;
- MX electrical pins, pads, solder joints, and lead-trimming access;
- all 70 SOD-123 diode bodies, pads, and solder fillets;
- nice!nano/controller/reset/service geometry; and
- battery-lead access.

Every class has at least `0.30 mm` nominal XY clearance. The measured minimum
is `0.3263 mm` for the diode openings after export simplification. No diode
opening breaks the lateral housing perimeter: the limiting left opening leaves
`0.90 mm` of housing material and the right leaves `3.0888 mm`, against the
`0.85 mm` release gate. The
vertical model uses the official Kailh CPG135001S30 maximum socket depth
`2.30 mm` plus `0.10 mm` assembly allowance, leaving `0.10 mm` to the
exterior bottom. It uses the official Vishay SOD-123 maximum depth `1.35 mm`
plus `0.30 mm` solder allowance, leaving `0.85 mm`.

- Kailh drawing:
  <https://www.kailhswitch.com/uploads/15927/files/CPG135001S30.pdf>
- Vishay 1N4148W datasheet:
  <https://www.vishay.com/docs/86356/1n4148w.pdf>

Bottom copper tracks and tented vias do not protrude below the PCB support
plane. Their electrical/mask state remains covered by the V2 board verifier.

## 150 mm printable right split

The left housing is one printable part. The right housing is exactly two parts
and has no stale monolithic STL:

- left: `134.9125 x 126.5500 x 2.5000 mm`;
- right part A: `86.9938 x 92.0500 x 2.5000 mm`;
- right part B: `81.6438 x 126.5500 x 2.5000 mm`.

Every STL is one watertight shell and fits the `150 mm` cube. The two right
parts use two full-depth neck-and-head puzzle captures. They assemble
vertically, use `0.20 mm` nominal print clearance, provide `1.25 mm`
minimum in-plane capture per side, and require neither screws nor adhesive.
This joint provides in-plane case-part registration; it does not claim to
replace the still-pending PCB retention validation.

The generator strips trailing spaces and tabs from exported STEP/STL lines
while preserving newline bytes. The manifest and verifier hard-check
`step_has_trailing_whitespace=false` for both STEP files.

## Regeneration and verification

```powershell
python -B -m tools.generate_kc2_x3_v2_housings
python -B -m tools.verify_kc2_x3_v2_housing
python -B -m unittest tools.test_verify_kc2_x3_v2_housing -v
```

The manifest binds the current source-board SHA-256, generator SHA-256, STEP
and STL SHA-256, support locations, component openings, printable bounds, and
joint geometry.

## Remaining physical gate

This is digital clearance and geometry evidence only. `CON-ARCH-006` AC-7 is
still pending: the printed, assembled housing must pass the 2.0 N load test at
the worst spans with no more than 0.30 mm downward PCB displacement, while PCB
retention and real component insertion are checked. These draft files are not
fabrication/order-readiness approval.
