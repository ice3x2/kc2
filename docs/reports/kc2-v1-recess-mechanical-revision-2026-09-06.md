# V1 / recessed-lid mechanical revision

Requirements: `CON-ARCH-006` and `OPS-ARCH-007`; the user approved the expanded scope before implementation. This report records requirement-linked RED/GREEN development evidence and geometry limits. It is not an alternate requirement source or final native-CAD/fabrication approval.

## Recessed MX lid

The previous head envelope projected1.20 mm above the plate. The revised cylindrical pocket retains the non-countersunk head requirement while placing the conservative3.00 mm diameter ×1.20 mm head0.30 mm below the unchanged plate top. Removing the head projection does not certify an unprovided keycap's clearance to the plate itself.

| Datum / feature | Revised nominal geometry |
|---|---|
| PCB bottom / top | Z2.50 /4.10 mm |
| Plate bottom / top | Z7.80 /9.30 mm;1.50 mm clip thickness |
| Switch aperture |14.00 mm; all70 centers and continuous0.60 mm clip-support rings retained |
| Pocket | Diameter3.40 mm, depth1.50 mm |
| Head bearing / maximum head top | Z7.80 /9.00 mm |
| Upper collar | Diameter4.60 mm, begins Z5.30 mm |
| Supported bearing-floor depth |2.50 mm above collar start, interrupted only by shaft bore |
| Nominal radial wall |0.60 mm; engineering choice, not strength qualification |
| PCB-contact landing | Diameter3.00 mm, unchanged; widening the landing is prohibited |
| Screw candidate |7.50 mm under head; nominal2.20 mm insertion and0.60 mm tip reserve in existing2.80 mm receiver |

The previous naive full-depth cut would detach the narrower post from the plate. The added collar supplies the missing connection. Its enlarged section begins1.20 mm above PCB, rather than touching additional routed copper. The upper right split is locally reserved around each collar with a2.60 mm radius mask; this resolves the previously observed MH8 split conflict without changing any of the17 mounting centers. Two captive keys remain, with four and five mounting clamps on the right parts.

Initial tests failed for missing recessed-head metadata and acceptance of an unsupported short stack. After implementation, the seven then-current upper/lower housing tests passed. The contract verifier also received a focused mutation test: before the fix, changing pocket diameter was ignored; afterward, pocket, collar, landing, derived bearing/head Z and section-evidence mutations fail closed. A real CadQuery miniature BRep test accepts the complete collar and rejects removal of its wall.

The diagnostic candidate was independently reimported from STEP and checked at all17 mounting centers. Every3.00 ×1.20 mm head envelope had zero solid intersection; the wall annulus over radii1.75..2.25 mm and a0.50 mm axial slice had volumeπ mm³; no material existed outside the3.00 mm landing in the slice immediately above PCB. The source generator now repeats these actual-BRep measurements during export and records each named MH result plus whole-collar part containment in the upper manifest. The lightweight verifier requires complete8/9 named-MH coverage and correct finite measurements; the manifest remains bound to current source/STEP/STL identities.

The diagnostic candidate had one left /two right valid solids and three watertight single-shell STL files. Bounds were left134.9125 ×122.30 ×5.20 mm, right88.7875 ×92.05 ×5.20 mm and90.0874 ×122.30 ×5.20 mm. These are candidate evidence, not a substitute for the regenerated canonical artifact bindings. The candidate generator hash predates a section-SVG-only drawing polish and must not be used as a final release binding.

## Lower-housing split regression caused by revised locator holes

With the promoted V1/MX shared locator holes, the existing actual-board housing test reproduced `could not place keyed puzzle feature near board Y=113.1`. The coarse fallback scan skipped the surviving narrow lane. A read-only0.10 mm-step scan over board Y100..150 found admissible complete slots at112.50,125.50,125.60 and125.70 mm, with every existing component cutout and explicit support union preserved.

The smallest change moves the first target from113.10 to112.50 mm, a0.60 mm shift. The second stays125.50 mm. No puzzle-neck/head size, slot allowance, straight seam, support disk, mounting hole or component keepout was reduced. The actual-board regression now explicitly checks two captures, the new first absolute board-Y datum, and no slot intersection with component cutouts, key-load supports or mounting lands. Existing checks retain all70 dedicated supports, their copper clearance and maximum load span, the17 exact mounting points, and printable-part bounds. Five housing tests passed after this correction.

`generate_outputs` additionally resolves a relative output directory before constructing output paths. This prevents `.relative_to(ROOT)` from rejecting a valid relative CLI destination late in export. No canonical regeneration was performed by the fixing agent; the coordinating agent owns backed-up regeneration of both lower and upper models because the lower generator hash changed.

## Test provenance and canonical status

Permanent interpreter-separated test records are supplied as `kc2-v1-recess-mechanical-tests-*.json` and matching geometry/KiCad-integration logs in this directory. They record exact commands, process return codes, log hashes and before/after source hashes. Main Python supplies CadQuery/Shapely for geometry tests; KiCad's bundled Python runs the PCB-dependent release integration suite. Synthetic mutation fixtures are explicitly identified as fixtures, not current canonical geometry evidence.

At this report's initial creation, both canonical generators were still running. They subsequently completed and the final tests below were run on the regenerated geometry. Final release requires direct current source/mesh/STEP validation and fresh actual Fusion export/reopen evidence, not the optional historical rebinding path.

The [during-regeneration test record](kc2-v1-recess-mechanical-tests-during-regeneration.json) records46 geometry tests in226.012 seconds with10 failures while the old lower manifest still referenced prior PCBs/generator/outputs; failures include current-hash, fresh extraction, support-plan and split load-path bindings. They remain failures, not waived passes. The separately executed KiCad release-integration suite passed6 tests. These interim results require a post-generation rerun.

The [post-generation rerun](kc2-v1-recess-mechanical-tests-regenerated.json) passes all46 geometry tests in248.176 seconds and all6 separately executed KiCad integration tests in0.004 seconds, both processes exiting0. Before/after differences are exactly the four F3D archives and the separately regenerated `kc2_housing_clearance.json`; PCB, source, STEP, STL and housing manifests are unchanged. The clearance JSON is a derived report consumed by one mutation-fixture test, so the full snapshot is not called unchanged. The independently calculated direct geometry result below provides the stable source/model verification without relying on that report. No stale geometry failure remains in this final run.

The [direct canonical geometry verification](kc2-v1-recess-direct-housing-geometry-2026-09-06.json) independently returns `errors=[]`, `sources_unchanged=true`, and `used_source_rebinding=false`. Both lower STEP/STL bindings match; the actual support geometry has maximum load span4.1444 mm on both halves, below the previous4.3902 mm limit. The regenerated upper contract includes all17 named recess checks and current generator/board/STEP/STL bindings. This direct run does not substitute a fixture or hash-only refresh for actual geometry analysis.

The one clearance-report-consuming mutation test was then [rerun after the refresh](kc2-v1-recess-mechanical-tests-clearance-stable.json), along with the six KiCad integration tests: all pass, both exit0, with the complete recorded before/after snapshot unchanged. This resolves the derived-report timing difference without pretending the longer run's full snapshot was immutable.

After actual Fusion export/reopen completed, a [separate fresh native verification](kc2-v1-recess-native-independent-2026-09-06.json) returned no native blockers and exit0. Its own raw bindings cover the four current F3D archives, source STEP files, Fusion result and checker, independently of their replacement during the longer geometry test run. These digital passes do not change the physical qualification limits below.

## Remaining engineering limits

The0.60 mm wall, printed1.10 mm receiver pilot, layer adhesion, installation/stripping torque and repeated disassembly require physical qualification. The7.50 mm screw length is a nominal candidate, not a measured length-tolerance result; shorter or longer substitutions require a new engagement/tip calculation. Conservative head-envelope clearance does not prove printed pocket diameter tolerance or driver fit. The plate-top-on-bed orientation includes a small pocket roof/bridge whose print quality must be inspected. No strength, contact reliability, exact cap-underside fit or final order readiness is inferred from valid solids or passing software tests.
