# Local socket screens on the original r5 assembly

Requirements: `CON-ARCH-006`, `CON-ARCH-007`, `OPS-ARCH-006`. User correction: 2026-09-10.

The user rejected the full enclosure in `2268492`. The clean worktree was reset to `cc854a3`; rejected work remains recoverable on `backup/enclosure-2268492`. The restored PCB-on-lower-support assembly is the baseline. This revision must not silently restore the rejected enclosure or its enlarged joined spacing.

## Scope and geometry

The lower housing has five left and seven right exterior socket windows. All are intersections of the Choc socket body/fillet reliefs with the old outer boundary. Local nominal0.40 mm screens wrap these reliefs while keeping the internal clearance cavities open from above. Local floor extensions support the additions continuously from Z−2.20; wall tops stop at the original PCB underside Z2.50. Nothing wraps the PCB thickness or changes the original PCB support/load path. One right local cover crosses the retained print split; its additions preserve the original0.20 mm split gap.

The MX lid uses segmented screens beside peripheral switches, not a housing enclosing the controller or PCB. Screen bottoms are Z4.40, leaving0.30 mm above PCB top Z4.10; the original standoffs still determine seating. Screens join the original plate at Z7.80. Only clearance-driven local roof additions at Z7.80..9.30 support outward screen portions. The existing plate, apertures, collars, hard stops and split parts are preserved. The screens retain the conservative15.6 mm switch body envelope; a14 mm clip opening is not substituted for the body. Controller-facing regions and existing service access are explicit openings.

The original right-half transform is X124.625/Y0, corresponding to nominal1.80 mm cross-half cap gap. No6.40 mm spacing from the rejected revision is used. Normal/magnetic lower variants both receive the same additions; original magnet geometry, receiver bores,70 switch supports,17 mounting positions and nominal7.50 mm screw stack remain unchanged.

## Evidence gates

Generation is staged at `.codex-tmp/local-cover-build`. Canonical publication is permitted only after all generation reports, separate actual STEP/mesh reviews, native Fusion export/reopen reports, regression tests and combined joined/intent review pass and bind the current bytes. The [publication manifest](../../../hardware/MODELS/kc2_local_cover_manifest.json) is the current-file authority after successful publication; its absence or failed verification means this is not a completed digital publication.

Lower reviews independently import the normal/magnetic baseline directly from Git and compare actual STEP material differences, required local cover inclusion, protected component/pilot/magnet voids and printable STL topology. Upper reviews independently check added material, original structure preservation, actual switch/service clearance and own-part roof support. Synthetic mutation tests must reject removed supports, global walls, missing covers and unauthorized PCB-height walls.

Both final lower reviews passed: added material177.589077 mm³ left and241.191379 mm³ right per normal/magnetic variant; removed material, off-allowance additions, missing requested covers, component/pilot obstruction and magnet-void changes are all0 mm³. All six lower STLs pass topology, STEP equivalence and150 mm part-envelope checks. The retained right split omits only0.1252 mm² of the local patch at the original0.20 mm seam. Start/end source hashes match.

Both final upper reviews also passed. All three actual STEP parts retain original material and have zero missing requested cover, off-allowance addition, component/service collision or new service/driver approach obstruction. Their three STLs pass topology and STEP equivalence. The right original/revised/full-added-part distance checks all equal0.19975909123481658 mm. The combined assembly review passes at the original joined transform: minimum complete-footprint gap1.30 mm, overlap0 mm², and all six bare lower-housing centroids within the original four-foot support hulls. All four independent audit reports retain their observed source bindings.

The combined `independent-review-final.json` checks complete joined polygons at the original transform and bare-housing STL centroids against retained silicone-foot support hulls. It aggregates separate independent CAD reviews; a plan-only gap or green mesh check is not treated as full mechanical proof. `regressions.json` records exact commands, sources, output and scope. Historical r5 fixtures are not evidence for newly added material.

The final source-frozen regression run passed105 tests in165.966 seconds. These include missing-corner and original split-clearance regressions, rejected removed/global/unsupported cover mutations, native integration/identity checks, fail-closed publication checks, and historical support/service contract tests. Actual new STEP/STL and native archive reviews remain separate gates; unit-test success does not substitute for them.

Native verification additionally reopens each F3D and exports a diagnostic STEP. Both original and native-derived STEP solids are measured in the same OpenCascade process with adaptive volume integration at relative epsilon1e-9; the comparison limits remain0.001 mm for bounds and max(0.002 mm³, volume×1e-6). Default mass integration produced a spurious0.013868 mm³ difference on the diagnostic left lid; controlled integration reduced that comparison to approximately1e-10 mm³ without changing either shape. The [OpenCascade integration contract](https://occt3d.com/dev/doc/refman/html/class_b_rep_g_prop.html) distinguishes adaptive and non-adaptive evaluation. Diagnostic STEP files in this report directory are verification evidence, not alternate editable or printable models. The final six-model native review and exact STEP/F3D/diagnostic identity-chain gates subsequently passed with no errors; its source-bound report, not the preliminary diagnostic alone, supplies the native evidence.

## Review-driven corrections

Independent review rejected the initial upper partition because it clipped two rounded left corners and parts of the right split ends. Regression tests were made failing first. The final producer keeps the complete unsplit left cover and reconstructs original right split ownership, including the actual captive-key owners. Only the exact retained old split void and narrow outside seam interrupt coverage. Plan tests preserve the measured original0.199759091 mm gap (nominal0.20 mm polygonized geometry), rather than redesigning the original joint.

Separate regression failures also drove the explicit-solid Boolean operands for adjacent cover/floor or skirt/roof solids, controlled native mass integration, and mandatory six-model F3D-to-diagnostic-STEP hash chains. These were verification corrections, not permission to dismiss missing material or raise acceptance tolerances.

## Reproduction commands

Use the configured CadQuery Python and read-only KiCad10 extractor. Generate each side with `tools.generate_kc2_local_covers` (lower) and `tools.kc2_local_upper_covers` (upper), passing `--side left` or `--side right`. Do not edit sources while a generation or review is running.

Run each independent local-cover review, then `tools.review_kc2_local_assembly`. Export and reopen all six native archives using `tools/fusion/KC2LocalCoversToF3D/KC2LocalCoversToF3D.py` inside Fusion. Run `tools/fusion/KC2LocalNativeReview/KC2LocalNativeReview.py` with context `all` inside Fusion, then `python -B -m tools.review_kc2_local_native --label all`. Run the source-bound regressions. Finally use `python -B -m tools.publish_kc2_local_covers --apply` for fail-closed publication.

`python -B -m tools.publish_kc2_local_covers --verify` uses the standard library only and resolves immutable observed report paths to identical canonical bytes. It must also pass against raw Git-exported files without staging directories or compatibility junctions. Replaced r5 JSONs point to the current manifest; their detailed historical contents remain in Git. PCB and ordered Gerber bytes must remain identical to `cc854a3`.

## Physical limits

Digital review does not qualify a particular printer/nozzle, thin-wall strength, received socket/pin/solder depth, exact cable/header/battery/wire placement, keycap inner-skirt/full-travel clearance, screw torque, adhesion, magnet pull force or RF. The original Ø2×1 mm magnets and nominal4.4 mm face gap remain unqualified for holding force. Keycap outer silhouettes do not prove inner clearance. No new PCB fabrication or order approval is issued.

Service approach checks distinguish newly obstructed space from original material. The restored baseline itself overlaps parts of the conservative USB cable, outward power-operation and reset-probe approach prisms (left baseline108.63/8.775/2.66264 mm³ respectively); the corrected left cover adds zero obstruction to these prisms. These broad approach envelopes are not controlled drawings of the user's cable, finger or tool. Retaining baseline geometry therefore does not establish unrestricted service access; inspect actual hardware and tools. Per-part baseline and newly added volumes are reported separately in the upper reviews.

Use the [current print guide](../../../hardware/MODELS/PRINT-local-covers.md). Existing1:1 order-time PCB drawings and older r5 output reports remain historical, not current cover approval.
