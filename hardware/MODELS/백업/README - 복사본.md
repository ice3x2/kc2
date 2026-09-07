# KC2 lower housing draft

This directory contains first-pass STL drafts generated from the current KC2 X3
KiCad PCB Edge.Cuts.

Generated files:

- `kc2_left_lower_housing.stl`
- `kc2_right_lower_housing.stl`
- `kc2_housing_manifest.json`

Regenerate:

```powershell
python tools\generate_kc2_housings.py
```

Design assumptions:

- FDM PLA+ print.
- No top housing.
- The housing perimeter stays slightly inside the PCB outline so joined left/right
  edges are not blocked by printed plastic.
- A hollow one-piece tray shell is generated per half. The outside wall is
  continuous from the bottom face to the PCB support height, without an
  external stacked ledge.
- A 1.2 mm front floor, 3.2 mm bottom component cavity, 2.4 mm continuous outer
  wall ledge, and nine registration support posts are generated per half.
- Registration pegs are 2.7 mm diameter for the PCB's 3.0 mm NPTH REG holes.
- The PCB battery-lead pass-through slot remains inside the tray, but the lower
  housing floor below the controller is closed.
- The controller/USB side height is 1.7x the front edge height.
- The bottom outline uses a 0.8 mm rounded-corner smoothing pass.
- The lower outside edge uses a 0.8 mm rounded bevel from the bottom face to
  the side wall.

This is a fit-check draft. Print one half first before committing to the full
pair, then tune peg diameter and floor clearance for the actual printer and
material.
