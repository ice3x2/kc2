# Upper inner-void and coplanar print-face correction

Requirements: CON-ARCH-006, OPS-ARCH-006. The immutable input revision is
identified by `hardware/MODELS/kc2_wall_gap_fix_manifest.json`.

The user reported two physical-print concerns in all upper families: awkward
nonfunctional space inside the outer wall and localized screw lands projecting
0.30 mm below the surrounding upper structure. The source minimum is Z4.10,
while the broad surrounding structure starts at Z4.40.

The correction fills only closed nonfunctional silhouette holes outside the
protected switch, socket, screw, service and registration spaces. It removes
all source material below Z4.40, producing one common minimum print datum on
all nine upper STL parts. No downward foot is added. The screw bores and the
larger boss geometry at and above the datum are compared against the source.

Publication is complete only when `hardware/MODELS/kc2_upper_finish_manifest.json`
exists and `python -B -m tools.publish_kc2_upper_finish` passes. Evidence then
contains six CAD generation records, six actual Fusion archive/reopen/native-STL
records, actual-section review, exact right A/B clearance, upper/lower insertion
sweeps, joined-half approach sweeps, and regression results.

The completed digital review reports zero material at Z4.15, Z4.35 and Z4.399
for all nine upper parts. It removed 12.138 mm3 from each left upper and
6.069/7.586 mm3 from the right A/B parts. Above-datum screw-boss section change
is below 2e-14 mm2, all 12 upper/lower insertion sweeps and six joined approach
sweeps have zero overlap, and all three right A/B gaps are about 0.3999 mm.
The 28-test regression suite passes.

Digital checks do not qualify real printer first-layer adhesion, warping,
material strength, screw torque or populated physical fit.
