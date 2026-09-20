# Continuous raised external sleeve — CON-ARCH-006

Release identity: `hardware/MODELS/kc2_wrap_housing_manifest.json`.
Use the current verifier below; an absent or failing manifest is not a release.
Physical qualification remains pending. Requirements remain in `docs/spec/`.

The approved construction keeps the PCB bottom/top at Z2.50/Z4.10 and raises
the lower outer wall to Z5.60. It overlaps the lower portion of the upper
housing by 1.20 mm, rather than enclosing the entire upper height. The new
wall is 1.20 mm thick with 0.30 mm nominal lateral clearance. Existing
registrars retain their separate local 0.25 mm clearance.

The actual PCB outline and nominal cap envelopes are included in the common
mating outline. Central exclusions follow the actual opposite housing,
rather than a broad rectangular strip. Service openings and existing socket
covers remain. The two existing magnet pairs and normal/magnetic options are
preserved; there is no new central locking feature or third magnet pair.

## Candidate corrections and evidence

- The first outline based only on the old MX plate intruded into nominal wide
  cap footprints. It was rejected before publication.
- A later actual STL exposed a local PCB clearance reduction to 0.20 mm.
  Including the PCB outline restored approximately 0.30 mm in the generated
  left and right normal housings and left magnetic housing sections.
- Boolean outline unions produced near-zero-length edges. A topology-preserving
  cleanup limited to 1e-9 mm removes numerical artifacts, with area and Hausdorff
  limits. It is not a manufacturing-scale geometry simplification.
- Binary STL serialization can create an exactly collinear T-junction.
  The serializer only subdivides such an existing edge without moving vertices;
  it refuses arbitrary holes and checks closed topology and volume afterward.

Development staging is private under `.codex-tmp/wrap-housing-20260920-r1`.
The published evidence in this directory resolves those logical names without
requiring that directory. Every generation and review is source-hash bound.

The [actual left MX cross-section](assembly-section-left-mx.png) shows the
generated lower/upper STL contours at local Y=80 mm and the nominal 1.60 mm
PCB section. The [raised-wall plan section](left-sleeve-preview.png) shows
actual lower STL material at Z5.35 with the PCB outline. These selected views
illustrate the intended stack; they do not substitute for full interference
checks or depict every mounted part.

## Required release checks

1. Ten current source-bound CAD jobs: normal/magnetic lower and MX/V1/Deep Sea
   upper on each side; fifteen individually printable STL files.
2. Actual mesh topology, required wall/floor/rim sections, PCB and nominal cap
   clearance, static upper/lower and joined sections, and print envelope.
3. Actual BRep added-material completeness, baseline preservation, A/B and
   complete assembly collisions, and magnet pocket/insertion access.
   Continuous nominal insertion is checked separately in `motion-review.json`:
   vertical height intervals, A/B full projections and central horizontal sweep.
   Its explicit mesh-roundoff allowance is not a physical print tolerance.
4. Ten actual Fusion archive exports, reopen checks, and independent readback
   STEP comparisons. A partial Fusion batch is explicitly not final approval.
5. Current regression tests, portable source bindings, and unchanged hashes
   for all sixteen canonical ordered PCB/Gerber files.
6. Publication of all thirty-five housing CAD artifacts together, current
   print guidance, Git commit/push, and a final publication audit.

`tools.publish_kc2_wrap_housings` refuses missing full mesh/CAD/native/test
evidence. Baseline models are retained through Git revision `e0e8686`, not a
second active model folder. The new [print guide](../../../hardware/MODELS/PRINT-wrap-housings.md)
identifies the release and its physical limitations.

## Comparison requested by the user

Wrapping the complete **perimeter** (except central/service clearances) is
different from wrapping the complete **height** of the upper housing.
The selected design does the former with a 1.20 mm vertical overlap.
For MX, reaching the upper plate top Z9.30 would require a wall 5.20 mm above
the PCB, rather than 1.50 mm. A common wall that high would extend above the
V1/Deep Sea plate tops Z6.50/Z6.25. Separate lower heights or additional cap
skirt/travel accommodation would be needed. Longer engagement also increases
the area vulnerable to print distortion and rubbing; no force test is claimed.
Therefore partial-height engagement is preferred for the common lower design.
This is a design judgment from the measured stack, not a tested full-height
prototype or a claim that a full-height enclosure is impossible.

## Published verification

```powershell
python -B -m tools.publish_kc2_wrap_housings
```

Run at repository root. The release contains 15 STL, 10 STEP and 10 actual
Fusion archives. Canonical STEP removes only outside-token trailing ASCII
spaces/tabs; `raw-step/` retains the original reviewed bytes. The manifest
proves lexical equivalence and maps source identities to those raw artifacts.
Native readback STEP remains unmodified. All 16 ordered PCB/Gerber files
are unchanged. Regression evidence covers 75 tests in 17 modules.
Actual mesh/CAD/motion reports cover all ten jobs, 12 vertical assembly
combinations and six complete left/right assemblies. Measured A/B projection
gap is at least 0.4000246 mm. Nominal collision checks do not account for an
unknown physical printer distortion field.

The development plan's broad PCB-folder preservation inventory also hashed
unconsumed autosaves, editor state/locks, footprint cache and local `.history`
metadata. These are classified explicitly as historical hash-only observations,
not CAD dependencies or portable release inputs. They are not uploaded.
Actual PCB/project files, geometry sources, reports and all unknown inputs
remain mandatory. Classification is allow-listed and regression-tested;
no actual design source may use this exception.

Digital geometry checks do not qualify actual print strength, assembly force,
wear, torque, magnet adhesion/attraction, exact purchased switch/cap variation,
solder protrusion, cable behavior, or RF. Silicone feet remain deferred.
