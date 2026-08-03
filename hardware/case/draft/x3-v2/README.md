# KC2 X3 V2 housing clearance

Requirement: `CON-ARCH-004`, reusing the flat split housing from
`CON-ARCH-003`.

The V2 board keeps the X3 switch centers, registration holes, PCB outline, and
lower-housing strategy. `kc2_x3_v2_housing_clearance.json` records the renewed
clearance analysis for the V2 footprint:

- 0 socket/wall collisions; minimum lateral clearance 0.309 mm.
- 0 MX solder/wall collisions; minimum lateral clearance 1.031 mm.
- 0 MX solder/post collisions; minimum lateral clearance 1.439 mm.
- 0 socket/diode collisions; minimum clearance 8.050 mm.
- With a 0.30 mm Choc socket SMD solder-fillet allowance, there are 0
  fillet/wall and 0 fillet/diode collisions. Minimum residual wall clearance
  is 0.010 mm and minimum diode clearance is 10.234 mm.
- With a 0.30 mm MX solder-fillet allowance, minimum clearance is 0.362 mm
  to the diode body and 0.197 mm to the diode SMD pad; neither intersects.
- 2.60 mm component cavity over a flat 1.20 mm floor, with no rear rise.
- MX electrical terminals must be trimmed to at most 2.20 mm below the PCB,
  leaving at least 0.40 mm vertical clearance.
- The right housing remains two printable parts, maximum dimension 145.513 mm,
  with a 1.601x zigzag bond-length ratio and 0.40 mm assembled glue gap.

This is digital clearance evidence only. The physical coupon and one housing
fit check remain required before the V2 board can be treated as orderable.
