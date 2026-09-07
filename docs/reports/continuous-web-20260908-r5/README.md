# Continuous lower support web, r5

Requirements: `CON-ARCH-006`, `OPS-ARCH-007`; canonical path compatibility under `OPS-ARCH-006`.

Final digital result: **PASS**, with physical qualification still pending.
The full housing verifier exited0: left/right full-depth missing support volume
is0 mm³, all floor/printable/mounting/service checks pass. The independent
populated audit exited0 with errors=[] and unchanged source bindings: sixteen
underside class sweeps, topside service envelopes, both lower/upper pairs and
both adapter alternatives have zero nominal material intersection. Native
checks report no blockers for all four exported/reopened archives. Regression
evidence is44 general tests +18 full-report tests +1 runtime-budget test =63.
All39 ordered-file comparisons pass. No physical tolerance/strength/thermal/RF
qualification or current whole-assembly fabrication approval is claimed.

## Correction and scope

The r4 floor was continuous but its support plate still started at Z0, leaving
an unintended 1 mm horizontal void above the floor. Connected-solid and floor
volume checks alone did not establish bottom-up printability.

The support plan now extrudes from Z-1 to Z2.5. The floor remains Z-2.2..-1.
Component reliefs are retained, not filled. This is one solid per printable part:
left whole and right A/B. The existing 150 mm print-envelope requirement and
right-side keyed joint remain. The right half has not been made monolithic.

Unchanged: PCB Z2.5/4.1, 70 key support positions, 17 pilots, nominal 7.5 mm
fastener, 2.8 mm pilot depth, recessed upper lid and twelve Ø8 mm foot regions.
Physical files stay in `hardware/PCB`, `hardware/GERBER`, `hardware/MODELS`.
Only four broken legacy junctions to the removed `00_CURRENT` tree were replaced;
no real directory was removed. Existing Git index/user moves were preserved.

## Verification evidence

- [Tests](tests.json): captured commands, actual return code and complete output;
  source hashes must remain unchanged during execution.
- [Full-report regression tests](report-tests.json): reuse the freshly computed,
  hash-bound canonical BRep report as the expensive fixture; this exercises
  report mutations and artifact bindings, not a second independent BRep run.
- [Audit runtime regression](audit-budget-test.json): the existing integrated
  artifact checker allows 1800 instead of 300 seconds for the more expensive
  full-volume housing verification. This is a timeout-only change; no electrical
  or geometric acceptance criterion is relaxed and the whole PCB suite is not
  represented as rerun by this AST test.
- [Digital STL/manifest contract](digital.json): nominal digital checks; exit 2
  deliberately retains unresolved physical qualification, not a digital error.
- [Fusion native round trip](native.json): four current STEP/F3D pairs, export and
  reopen, body count, bounds, volume and exact file hash checks.
- [Ordered files](ordered-files.json): 39 PCB/raw fabrication/sealed-package
  inputs compared with their historical expected hashes. No PCB regeneration,
  Gerber export, new order package, purchase, commit or push is performed here.
- [Populated STEP audit](populated-cad.json): corroborating actual support sections,
  bottom-up planar containment, conservative underside component envelopes,
  top service envelopes, lower/upper and adapter intersections. This link is
  complete evidence only after the audit exists with an empty errors list and
  the separate full-depth housing check passes. Sections use 0.00001 mm curve
  deflection and 0.0001 mm comparison tolerance; they do not replace full volume proof.
- [Canonical full housing check](../../../hardware/MODELS/kc2_housing_clearance.json):
  actual floor/STL/STEP, full-volume support, mounting, service and clearance
  checks. The new `web_continuity` fields are required; r4 results are insufficient.

TDD: the old generator failed the new support inclusion test with 772.626883 mm³
missing material in the fixture. A connected but suspended fixture is rejected.
A second mutation placed the gap above the initial probe range: it first passed
incorrectly, then failed after full-depth checking replaced the single-height
probe. Component relief and blind pilot remain empty in the corrected fixture.
The canonical-path mutation initially rejected `hardware/MODELS`; exact approved
alias mapping now accepts it while retaining file-name and SHA checks.

A per-printable-part containment test additionally found simplified outline
chords outside the floor (left 0.044499 mm², right B 0.039690 mm², lateral
extent below 0.02 mm). The support plan is now clipped to the floor outline.
The resulting GEOS vertices exposed sub-kernel edges: a 1e-10 mm edge fixture
reproduced the CAD extrusion failure before consecutive vertices within
1e-7 mm were filtered. This cleanup does not simplify functional reliefs.
These findings required another complete CAD/native/evidence regeneration;
earlier intermediate passes are not substituted for the final files.

## Populated assembly limits

The lower audit sweeps the buffered PCB-derived component plans through
Z-0.4..2.5, covering the entire newly extended region that an allowed underside
component could occupy. It reviews Choc body/fillets, mechanical switch pins,
MX pins/pads/fillets, diode body/fillets, controller sockets, battery terminations,
power-switch leads and battery slot. MX and Choc are alternative populations,
not components to fit simultaneously at the same switch.

| Modeled projection | Nominal floor clearance |
|---|---:|
| Hat socket, 1.2 mm below PCB | 2.3 mm |
| Choc socket including allowance, 2.4 mm | 1.1 mm |
| Diode including fillet, 1.65 mm | 1.85 mm |
| Maximum permitted unknown lead/solder projection, 2.9 mm | 0.6 mm |

The last row is an assembly limit, not a measurement. The 0.6 mm includes an
engineering 0.3 mm print allowance and 0.3 mm remaining reserve. Actual socket
contact tolerances, exact battery/header/wire shape, full-travel keycap skirt,
solder depth, screw tolerances, printed strength, adhesive, charging temperature
and RF performance remain unqualified. Existing unchanged-component orientation
evidence is [the r3 component review](../kc2-v1-recess-component-review-2026-09-06.md);
its mechanical pass is not reused for this changed housing.

Do not solder in the housing, compress the battery/wires with screws, or trim
functional socket/switch bodies. See [current print instructions](../../../hardware/MODELS/PRINT-r5.md).
Historical r4 sealed files remain historical; no current whole-assembly order
approval is inferred from them or from a zero-intersection nominal model.
