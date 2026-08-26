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
- The generated support set contains 14 left and 11 right seam/thumb/span
  regions. The measured worst switch-center distance to support is
  `15.4640 mm` left and `18.9619 mm` right; seam distance is `2.85 mm`
  on both halves.
- A `2.00 mm` diameter foot continues downward from every distributed support
  datum to desk datum Z `-1.00 mm`. The eight left and ten right mounting
  points add coaxial `3.00 mm` desk-contact columns. A separate `3.00 mm`
  column also backs the exact top-side `SW_RST1` actuator at zero gap. The
  left part therefore has 23 coplanar desk contacts; right parts A/B have
  10/12. Each set is
  non-collinear and its contact hull contains
  the projected plate centroid, so every printable part has an independent
  no-rocking digital support proof. Feet remain inside the housing silhouette
  and have zero intersections with exterior-open component cutouts.
- There are no legacy REG/H pegs or separate fastener bosses. The exact
  `MH1..MH8` left and `MH1..MH10` right M1.4 pattern adds `3.00 mm` zero-gap
  annular support lands at Z `2.50 mm`, aligned `3.00 mm` columns to Z
  `-1.00 mm`, and provisional `1.10 mm x 2.80 mm` blind pilots. Each pilot
  ends at Z `-0.30 mm`, leaving a nominal `0.70 mm` closed column bottom.
  The provisional 4.00 mm under-head screw length yields `2.24..2.56 mm`
  penetration across the PCB thickness tolerance and at least `0.24 mm`
  nominal tip clearance. The exact screw MPN, printed pilot, torque, repeated
  service, and full-pattern registration remain physical gates.
- The mounting service model removes keycaps but leaves switches installed.
  All selected points pass the final `3.00 mm` PH0 driver cylinder and
  `2.00 x 0.50 mm` head envelope without adding a second clearance buffer.
  The screw pattern clamps and registers the PCB; it does not replace the
  perimeter rail or the retained 14/11 distributed supports.

## Exterior-open underside clearances

The plate is cut completely through from Z `0.00` to `2.50 mm` wherever a
bottom-side assembly envelope is required. The generated STEP volume is
independently compared with the cutout-differenced support plan, and every
required envelope has zero residual intersection volume.

The verified openings cover:

- Choc V2 socket bodies and solder-fillet envelopes;
- all switch center and locator NPTH/mechanical-pin continuations;
- MX electrical pins, pads, solder joints, and lead-trimming access;
- all 70 Jingdao ES1B SMA maximum lead/body, pad, and solder-fillet envelopes;
- nice!nano/controller socket/service geometry;
- the exact B.Fab `TW301525 80mAh` `15.00 x 25.00 mm` battery body with
  `0.35 mm` XY allowance; and
- battery-lead access.

`SW_RST1` is intentionally absent from this underside-cutout list. Its pads
are F.Cu-only, and the exact actuator projection is backed by the local
zero-gap support/desk column. The support intersects no via, bottom-exposed
pad, or exterior-open cutout. The right support lies over two B.Cu routes that
remain inside the PCB stack under solder mask; the left overlaps none.

Every class has at least `0.30 mm` nominal XY clearance. The measured overall
minimum is `0.3279 mm`; the ES1B openings retain at least `0.3282 mm`. No diode
opening breaks the lateral housing perimeter: the limiting opening leaves
`1.0250 mm` of housing material on both sides, against the `0.85 mm` release
gate. The
vertical model uses the official Kailh CPG135001S30 maximum socket depth
`2.30 mm` plus `0.10 mm` assembly allowance, leaving `0.10 mm` to the
plate bottom. It uses Jingdao's ES1B maximum `5.20 x 2.70 x 2.20 mm`
lead/body envelope plus `0.30 mm` solder allowance. This consumes the full
`2.50 mm` plate depth, but the feet provide `1.00 mm` nominal diode-to-desk
clearance and `0.70 mm` after the documented `0.30 mm` print allowance. The
modeled `3.00 mm` battery retains `0.50 mm` nominal desk clearance and exactly
`0.85 mm` top-edge housing land. Maximum battery thickness/swelling, adhesive
retention, lead bend, strain relief, abrasion protection, placement tolerance,
and post-print desk clearance remain physical gates.

- Kailh drawing:
  <https://www.kailhswitch.com/uploads/15927/files/CPG135001S30.pdf>
- Jingdao ES1B / LCSC C437840 datasheet:
  <https://datasheet.lcsc.com/datasheet/pdf/2343098076327222563a84c9a80dbd7d.pdf?productCode=C437840>

Bottom copper tracks and tented vias do not protrude below the PCB support
plane. Their electrical/mask state remains covered by the V2 board verifier.

## 150 mm printable right split

The left housing is one printable part. The right housing is exactly two parts
and has no stale monolithic STL:

- left: `134.9125 x 122.3000 x 3.5000 mm`;
- right part A: `86.9938 x 92.0500 x 3.5000 mm`;
- right part B: `81.6438 x 122.3000 x 3.5000 mm`.

Every STL is one watertight shell and fits the `150 mm` cube. The two right
parts use two full-depth neck-and-head puzzle captures. They assemble
vertically, use `0.20 mm` nominal print clearance, provide `1.25 mm`
minimum in-plane capture per side, and require neither screws nor adhesive.
This joint provides in-plane case-part registration; it does not claim to
replace the still-pending physical PCB-registration validation.

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
and STL SHA-256, support/desk-contact locations, component openings, printable
bounds, M1.4 land/pilot/column/head/driver contract, and joint geometry. The
verifier independently extracts each STL's
bottom contact components and compares their count, centers, Z datum, and
stability hull with the generated plan.

## Remaining physical gate

This is digital clearance and geometry evidence only. `CON-ARCH-006` AC-7 is
still pending: the printed, assembled housing must pass the 2.0 N load test at
the worst spans with no more than 0.30 mm downward PCB displacement, while PCB
registration, pilot/torque/ten-cycle behavior, switch/keycap clearance, and
real component insertion are checked. AC-11 additionally requires the exact
reset supplier Z/travel/force/reflow limits, socketed-controller and
nonconductive-probe service, USB shell/cable clearance, ten double-reset and
bootloader-enumeration cycles, plus the battery physical gates above.
`order_ready` remains false. These draft files are not fabrication/order-readiness
approval.
