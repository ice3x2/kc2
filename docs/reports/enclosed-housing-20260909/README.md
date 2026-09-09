# Continuous enclosure revision — digital geometry verified

Requirements: CON-ARCH-006, OPS-ARCH-006. User approved upper/lower exterior walls, minimum necessary enclosure expansion, and preservation of ordered PCB/Gerber and magnetic/non-magnetic options.

Before starting, the worktree was clean at `cc854a3`; `git push origin main` returned `Everything up-to-date`. No artificial empty commit was created.

**Canonical CAD is published at `hardware/MODELS`.** The user approved increased center spacing. The current enclosed design uses a nominal6.40 mm cross-half cap gap (right transform X129.225 mm), locally0.40 mm / normally0.80 mm walls, and0.300913 mm minimum complete-shell separation. PCB and Gerbers are unchanged. The preliminary source-bound calculation [plan-feasibility.json](plan-feasibility.json) is historical, not the current implementation verification.

Staged STL/STEP files are generated under `.codex-tmp/enclosure-build`; they are review intermediates, not an alternate active hardware target. Lower floor remains1.20 mm; the lower wall reachesZ4.10 and directly seats the upper wall. MX plate remainsZ7.80..9.30. Normal and magnetic lower options have the same exterior.

Both magnet pairs retain aligned Y103/111 and Z0.75, with opposed axes. Wider joined spacing moves the pocket walls to a6.195819 mm gap; bottom-seated1 mm magnets in1.2 mm deep pockets have a6.595819 mm face gap before adhesive. This is larger than the historical4.4 mm gap and may give weak attraction withØ2 mm magnets. No snap/holding-force claim is made; print and pull testing remain mandatory. The revised wall does not silently inherit the earlier magnet gap.

Independent initial review found a blocked USB approach in the first staged upper wall; see [initial findings](independent-review-initial.json). A12.60 mm trial corridor was rejected because it intersected the MH1 receiver. The revised fix adds an upper-only top-open10.20 mm corridor (9.60 mm design cable allowance plus0.30 mm each side) along the actual controller axis, retaining all receivers. The lower socket-concealing wall is retained. This allowance is not a measurement of an unspecified cable/header; a wider cable body belowZ9.30 requires a measured fit check.

CON-ARCH-007 AC-8 access review also found the previous narrow RESET opening obstructed a3 mm probe. The revised upper has a3.60 mm RESET opening, and a4 mm outward POWER fingernail corridor. Combined USB/POWER/RESET plan checks show zero receiver collision and one connected plate polygon per half before intended splitting. All9STL and6STEP files have been regenerated.

[Final independent review](independent-review-final.json) passes:25 actual STEP service/driver intersections are0 mm3, all9STLs are watertight/single-body/within150 mm, and14 source bindings match. It explicitly does not qualify native archives, exact cable/header or physical printing.

Both actual-STEP main audits pass with errors=[]: [left](left-audit.json), [right](right-audit.json). They check sampled floor/wall coverage, PCB and component clearance slices, exterior containment, full USB/POWER/RESET corridor volumes, full0.60 mm magnet backing disks, complete bore access/removal, and actual lower/upper wall contact atZ4.10. Generation records: [left](left-generation.json), [right](right-generation.json); [joined plan](joined-plan.json). Immutable reports retain the paths observed during checks; the [publication manifest](../../../hardware/MODELS/kc2_enclosure_manifest.json) maps them to identical canonical bytes. Verification resolves PCB aliases to physical `hardware/PCB` paths and needs no temporary tree or junctions.

After the user resolved the Fusion update, Fusion2705.1.11 exported and reopened all6native archives successfully: [native-all.json](native-all.json). Publication cross-checks both Fusion source/reopened body bounds and volumes against the independently exported CadQuery models. All21CAD files (9STL/6STEP/6F3D) were copied byte-for-byte only after geometry, independent-review and native gates passed. No new PCB fabrication package or physical qualification is implied.

## Bottleneck independent of component-envelope assumptions

The exact existing PCB polygons are only1.10 mm apart at global XY(161.625,86.500) and(161.625,87.600). At the PCB-height slice, allowing0.30 mm nominal printed-case/PCB clearance on each side and0.30 mm between cases leaves only0.20 mm total plastic: **0.10 mm per opposing wall**. This is not a qualified FDM wall. Merely making an0.40 mm wall cannot satisfy these retained clearance assumptions at the old joined position.

The walls are parallel to a horizontal step here. Moving the right half a few tenths along X does not separate these overlapping horizontal segments; this is why the required X change can be much larger than the wall thickness.

## Uniform-envelope feasibility scan

The preliminary common inner cavity envelopes PCB, underside classes (including alternate Choc sockets), switch bodies, controller/socket, battery, POWER sweep and RESET with at least0.30 mm nominal allowance. A small numerical reserve prevents polygonal arc approximation from reducing that allowance. Each constant-width outer shell is compared as a complete closed polygon, not a sampled Y scan.

| Uniform wall | Extra right-half X on0.05 mm grid | Resulting nominal cross-half keycap gap |
|---|---:|---:|
|0.80 mm|6.10 mm|7.90 mm|
|0.60 mm|5.50 mm|7.30 mm|
|0.40 mm|4.55 mm|6.35 mm|

These are **preliminary projected-envelope results**, not a globally optimized three-dimensional enclosure or a print-ready design. The PCB-only bottleneck remains even if conservative component projections are refined. Normal outer walls with localized thin center walls should be explored after the joined-position decision. A larger center gap also changes magnet-face separation/attraction; magnet relocation and actual pull force must be reviewed, not inherited from the4.4 mm old pocket gap.

The user subsequently approved the wider joined position; the SRS enclosure-specific statement supersedes the old1.80±0.20 mm cap gap for this revision only. The uniform scan is retained for provenance, not as the final variable-wall design.

## Automated checks

`C:/Python312/python.exe -B -m unittest tools.test_kc2_enclosed_housing tools.test_kc2_enclosure_cad tools.test_audit_kc2_enclosure`:13 tests pass after failing tests before implementation. Tests cover closed component-clear walls, thickness and joined-gap rejection, variable walls, actual seated CAD, continuous floor, six native export targets, USB clearance without lower-wall or MH1 receiver removal, RESET/POWER access, source-byte preservation, section mutation rejection, and off-axis void rejection in full-disk magnet backing. The0.40 mm minimum is a design rule, not qualification of the user's unspecified printer/nozzle/material.

The existing44-test continuous-web/closed-floor/MX/recessed-lid/layout/section/service suite is included in the combined source-bound run, alongside current enclosure, publication and retained-foot checks; see [regressions.json](regressions.json) for the exact test list, count, duration and bound sources. Historical r5 unit/mutation tests now read their historical JSON/CAD fixtures from Git `cc854a3` into temporary directories; they do not mistake superseded metadata for current approval. The old `V2LoadBearingHousingTests` class is not part of the claimed current enclosure suite. Actual current STEP audits and independent exported-mesh review provide the new-geometry evidence.

[Retained feet and drawings](retained-feet-and-drawings.json) confirms all six normal/magnetic lower-part mesh centroids lie inside their retained four-foot support hulls, and all nominal diameter8 mm contact disks remain inside the floor masks. This is bare-housing static geometry, not populated stability or adhesive qualification. Current upper-plan and foot-layout SVGs follow the enlarged outline; the mounting-section SVG is explicitly historical local-receiver geometry.

Publication mutation tests reject missing/duplicated output inventories, missing report/input bindings and invalid native records. Final portability is checked by exporting the staged Git blobs into an isolated temporary directory and running the standard-library-only `--verify`, with no `.codex-tmp` generation inputs, compatibility junctions, Fusion or CadQuery. This validates the bytes that will be committed, not only the live working tree.

`C:/Python312/python.exe -B -m tools.kc2_enclosure_plan` regenerates the source-bound plan comparison without exporting CAD or editing PCB. KiCad MCP statistics were read only; its generic net counter is not treated as connectivity evidence.

## Reproduce the staged digital checks

Run with the configured CadQuery Python3.12 and read-only KiCad10 extractor:

```powershell
C:/Python312/python.exe -B -m tools.generate_kc2_enclosed_housings --side left
C:/Python312/python.exe -B -m tools.generate_kc2_enclosed_housings --side right
C:/Python312/python.exe -B -m tools.audit_kc2_enclosure --side left
C:/Python312/python.exe -B -m tools.audit_kc2_enclosure --side right
C:/Python312/python.exe -B tools/review_kc2_enclosure_independent.py
```

Do not change generation sources during a running export; re-run source-bound checks after every geometry change. The actual native export/reopen script is `tools/fusion/KC2EnclosedToF3D/KC2EnclosedToF3D.py` and must run inside Fusion. It targets all6staged STEP files. Then run `python -B -m tools.publish_kc2_enclosure --apply` to repeat the fail-closed promotion.

For the published files, run `python -B -m tools.publish_kc2_enclosure --verify` using standard Python without Fusion/CadQuery. Previous active-looking r5 JSONs are explicit superseded pointers; their original contents remain in Git cc854a3. Exact keycap/full travel, received component/header/cable envelopes, printed fit/strength and magnetic/RF qualification remain physical checks, not software passes. Ordered PCB/Gerber bytes are unchanged. Follow the [current print guide](../../../hardware/MODELS/PRINT-enclosed.md), not historical r5 outlines or order-time assembly drawings.
