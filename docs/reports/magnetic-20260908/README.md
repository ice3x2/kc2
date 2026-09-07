# Optional magnetic lower housings — 2026-09-08

Requirements: **CON-ARCH-006**, **OPS-ARCH-006**. Existing r5 non-magnetic housing remains available and unchanged. This is an optional mechanical assembly, not a new PCB revision or fabrication release.

## Design

- Ø2.00 ×1.00 mm axial disc magnets, two per half / four total.
- Horizontal blind pockets Ø2.40 ×1.20 mm; no added material, thickened walls, enlarged exterior or inter-half mechanical lock.
- Reflected local housing coordinates: left X0.10, inward +X; right X149.30, inward −X. Both Y103.00 /111.00 and Z0.75 mm; 8 mm center spacing. Right pockets are in part B, not the A/B joint.
- Existing web top/bottom Z2.50 /−1.00 leaves0.55 mm plastic above/below the bores, with at least0.60 mm back wall. The1.20 mm closed floor atZ−2.20..−1.00 remains intact.
- All70 primary support positions and17 mounting lands/pilots, PCB2.50/4.10, MX upper housings and right A/B joint are unchanged. Material may disappear only within the four approved pocket cylinders.
- At the retained joined transform (right offsetX124.625, Y0 mm), the walls at these pockets are4.00 mm apart. Bottom-seated1 mm magnets are recessed0.20 mm each, giving4.40 mm magnet-face air gap before adhesive thickness. No holding-force or snap claim is made.

## Evidence

Final digital result: **PASS**, zero errors. Original94 files preserved; four watertight single-shell STL files (three housing parts and one coupon), two STEP and two actual reopened F3D archives. Regression total: **76 passed** (63 baseline +13 magnetic/evidence tests). The authoritative source-bound outcome is [verification.json](verification.json); a report heading alone is not a pass.

| Evidence | Scope |
|---|---|
| [cad-delta.json](cad-delta.json) | Reimport actual exported STEP; boolean added volume, off-pocket removal and residual bore material; removed volume; unchanged bounds and solid counts; actual STL topology/volume/bounds |
| [Original inventory](originals-before.json), [preservation result](originals-preserved.json) | Raw SHA-256 of original models/adapters, PCB files, ordered Gerber package and original generating/export scripts |
| [Fusion result](../../../hardware/MODELS/kc2_fusion_export_result_magnetic.json) | Actual Fusion STEP import, native archive export and reopen, per-body bounds/volumes and hashes |
| [tests.json](tests.json) | Requirement-linked automated checks, including wrong-bore, added-material, incomplete-evidence and Git-byte-preservation rejection |
| [baseline-regressions.json](baseline-regressions.json) | Fresh44 general,18 report/mutation and1 timeout-contract regression tests; all pass |
| [git-index-check.json](git-index-check.json) |75 staged source/output bindings match reviewed raw bytes;44 ignored local PCB editor/cache files remain local, not release inputs |
| [Original r5 populated CAD](../continuous-web-20260908-r5/populated-cad.json) | Prior complete component envelope checks, reused only after every source binding is checked unchanged |

The new difference-only proof does **not** rerun or relabel the whole r5 populated audit as a magnetic strength test. New plastic/component interference cannot be introduced by a strictly subtractive revision. Placement is separately checked against cutout-differenced support material and protected support/mount/reset regions. The retained magnet fits inside the bore and remains below the PCB support plane; loose magnets and adhesive overflow are assembly hazards, not modeled retained states.

Local horizontal bores are the explicitly approved exception to the r5 complete-web-volume rule. A circular hole roof has a short overhang/bridge (up to2.4 mm), so the original no-air-gap proof does not establish its print quality. Actual FDM dimensions, strength, adhesive retention, polarity, magnetic attraction and RF behavior remain **unverified**.

The initial failing tests were executed before the generator, the restricted Fusion exporter and the evidence verifier were implemented. Further failing tests detected missing canonical-path raw-byte protection and required complete baseline-suite evidence; both were implemented and passed. The original44-test continuous-web/closed-floor/MX/recessed-lid/layout suite was rerun, and the final recorded run passed in107.063 seconds. The18 report/mutation tests and1 timeout-contract test also passed.

## Reproduce

Use Python3.12 with CadQuery, Shapely, trimesh and its numerical dependencies; the existing KiCad10 Python provides read-only PCB extraction. KiCad MCP board statistics were also read without modifying boards. Its generic net counter returned0 and is not used as electrical connectivity evidence; this task does not approve electrical fabrication.

```powershell
python -B -m tools.kc2_current_layout --apply
C:/Python312/python.exe -B -m unittest tools.test_kc2_magnetic_housing tools.test_verify_kc2_magnetic -v
C:/Python312/python.exe -B -m tools.generate_kc2_magnetic_housings
```

Then run `tools/fusion/KC2MagneticToF3D/KC2MagneticToF3D.py` in the live Fusion Python environment. It writes only magnetic native archives and its separate result file, not the original F3D files. Finally:

```powershell
C:/Python312/python.exe -B -m tools.verify_kc2_magnetic
```

The generator may replace its own `_magnetic` outputs on a deliberate rerun. It must never export to original names. STEP/F3D exporter metadata can vary; regenerate verification after exports, not by rebinding old results to changed geometry. Output locations and printing/polarity/coupon instructions are in [PRINT_magnetic.md](../../../hardware/MODELS/PRINT_magnetic.md).

## Remaining physical acceptance

Print the4 ×24 ×4.7 mm horizontal-bore coupon first (diameters2.2/2.3/2.4/2.5, depth1.2 mm). Use the same print orientation/settings; do not force a tight magnet or globally scale the keyboard. Validate bore roof quality and actual pocket fit, adhesive compatibility and retention, opposed polarity, pull force and repeat placement. Existing socket/pin/solder, battery/header/wire/keycap, torque/deflection, thermal and RF qualification remains post-receipt work. No new order/payment was executed.
