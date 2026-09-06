# KC2 software-verifiable review — 2026-09-06

Requirements: `CON-ARCH-004`, `CON-ARCH-006`, `CON-ARCH-007`, `REL-ARCH-001`, `OPS-ARCH-007`.
Active target `kc2-x3-v2`; relevant requirements are evolving, with no stability blockers.
This is verification evidence, not a replacement requirements document or unconditional order approval.
No PCB, footprint, housing, adapter STL, firmware, or sealed fabrication package was intentionally changed.

## Finding requiring attention: V1 ring does not establish V1 compatibility

The [manufacturer CPG135001D02 drawing](https://m.kailhswitch.com/Content/upload/pdf/201915927/CPG135001D02_-_Brown_Tactile_Choc-%281%29.pdf), page 1,
was downloaded and visually inspected, including its bottom view, PCB pattern and general tolerance table.
Its two plastic locator posts are nominal diameter 1.80 mm, separated by 11.00 mm.
After aligning its electrical contacts to the KC2 Choc socket frame, those posts are at local X=±5.50, Y=0.
All 70 actual board footprints instead have the preserved MX holes at X=±5.08, Y=0, diameter 1.70 mm.

Nominal complete-containment margin per post is `0.85 - 0.42 - 0.90 = -0.47 mm`.
The script checks every available NPTH in each footprint, not only the nearest candidate by name.
Every key has two negative margins. The annular center adapter cannot remove this side-post interference.
**Unmodified V1 switch + current PCB + ring is a digital FAIL**, not merely pending printing.
This result does not invalidate the independent TTC MX population or mean the Gerber electrical connectivity is wrong.
Do not drill the routed PCB or cut parts as an unreviewed workaround.

The same V1 drawing establishes nominal center-post diameter 3.20 mm; general diameter tolerance is ±0.10 mm.
The trial 3.50 mm V1 ring bore therefore leaves 0.20–0.40 mm diametral clearance before unknown print error.
Nominal electrical pin length 2.65 mm minus PCB 1.60 mm minus flange 0.20 mm leaves 0.85 mm below PCB,
assuming the flange actually establishes that seating datum. This is **not** proof of sufficient socket contact engagement.
The manufacturer's recommended original 3.40 mm central PCB hole is not the center-post diameter.

Evidence: [all-70 ring/board measurements](software-audit-20260906/ring-board.json),
[archived V1 reference](software-audit-20260906/reference-v1-CPG135001D02.pdf).

## Coverage and results

| Area | Evidence and scope | Result |
|---|---|---|
| Actual PCB nets and parts | Fresh V2 verifier: 31/39 switches, 31/39 exact diodes, all duplicate contacts, controller/reset/power nets and pad geometry, 17 mounting centers, NPTH, no stabilizers, diode access/clearance | No reported digital errors; connectivity arrays empty |
| Fresh KiCad DRC | Current canonical boards, KiCad 10 CLI through MCP, all severities including exclusions, saved only new reports | Both: 0 violations, 0 unconnected; five ignored rule classes remain disclosed |
| Solder access | Enlarged U1/MX lands and fresh-process generation/replay tests; actual Gerber mask review is source-bound in existing release | Checked land/mask geometry passes; solder wetting is not simulated |
| Routing/library reproducibility | Fresh generation and frozen route snapshot tests; current 738/949 route counts and fingerprints | Targeted tests pass |
| Firmware | Fresh actual matrix/power-path/build-evidence verifier | 70-key matrix and both local build artifacts verify; no fresh firmware compilation or physical scan claimed |
| r2 fabrication ZIP | Rechecked every sealed file, raw Gerber/drill payload and 215 source/review bindings against current files | Package checker passes; this is the pre-adapter, generic-MX release scope, not full selected-part fit qualification |
| Gerber/Excellon/1:1/native output | Existing visual inspection and 1:1 evidence remain bound to unchanged payloads; current overlay and Fusion archive tests rerun | Provenance/content checks pass; no claim that all renders were newly re-viewed this turn |
| Housing contract | Fresh MX housing verifier, current PCB extraction, source-bound native round-trip evidence | `digital_valid=true`, errors=[], native blockers=[]; physical qualification still pending |
| Actual STEP solids | Four STEP files imported into CadQuery; left lower/upper each 1 solid, right lower/upper each 2 solids | All valid; lower/upper intersection volume 0 on both halves |
| Rings versus housing | All 70 centers from current boards; installed ring spans Z=2.90–4.30 mm. Conservative circular V1 ring envelope contains MX ring material | Intersection volume 0 with actual upper and lower solids on both sides; this excludes switch/PCB side-post compatibility |
| Saved ring meshes | Both existing binary STLs parsed; each 2,304 triangles; paired directed edges; specified radii/Z planes | Closed, consistently oriented; 0.20 mm flange, 1.40 mm total height; no claim of calibrated printer toolpath validation |
| V1 side locator fit | Actual board NPTHs versus official drawing | FAIL, both posts on all 70 keys |
| Exact cap swept volume | No selected cap underside CAD or controlled dimensional drawing supplied/found | Cannot conclude; existing 13 overlaps + 1 tangent + 3 clear are only 2D head/nominal-cap projections |

Fresh machine outputs: [board](software-audit-20260906/board.stdout.txt),
[left DRC](software-audit-20260906/left-drc.json), [right DRC](software-audit-20260906/right-drc.json),
[housing](software-audit-20260906/housing.stdout.txt), [actual CAD](software-audit-20260906/cad-solids.json),
[firmware](software-audit-20260906/firmware.stdout.txt), [package](software-audit-20260906/package.stdout.txt).

There is no canonical `.kicad_sch`. Even though the MCP DRC command included `--schematic-parity` and its report array is empty,
that is not an independently authored schematic comparison or ERC proof. Circuit intent is checked against SRS, official physical
pinout review and firmware mapping. The five ignored rules are missing courtyard, track-not-centered-on-via, tuning-profile geometry,
footprint filter mismatch and footprint type mismatch; their exclusion is not an electrical-clearance waiver.
The three previously inspected same-net pad/via mask overlaps remain solder-wicking exceptions; a nominal via-mask flag alone
must not be interpreted as proof that every via is covered in the final Gerber.

## Test audit, not just selected passing tests

The first batch ran 98 tests: 97 passed, 1 failed. The failure is
`test_1n4148w_transition_preserves_firmware_and_documents_pending_physical_scan_gate`:
it expects the old literal text `reviewed canonical SES` in the hardware README. Current route evidence uses the MX route snapshot.
This is a test/documentation synchronization defect, not a demonstrated electrical fault. It is not silently waived or marked green.

The extended batch reported 107 tests, 1 failure and 7 errors. Its genuine assertion failure is
`test_product_spec_uses_current_70_key_v5_quantities`, which expects the old index row declaring 616/803 routes as current.
The current index correctly identifies those routes as historical; current MX routes are 738/949.
The seven errors were missing Shapely/CadQuery in KiCad's Python, including a class setup error, so skipped class tests must not
be counted as executed. In the existing Python 3.12 environment, the two geometry modules subsequently executed all 36 of their
tests successfully; including the separate PCB-integration module in that process added one synthetic import error because Python
3.12 does not have pcbnew. That integration module's six tests pass in KiCad Python (both in the original batch and a separate rerun).
Thus the geometry dependency failures were exhausted by running each module in its appropriate existing environment; the two
documentation assertions remain genuine non-green results. No environment installation or test expectation change was made.

Logs: [first batch](software-audit-20260906/regression.stderr.txt),
[extended batch](software-audit-20260906/extended-tests.log),
[36 geometry tests and the separate environment import error](software-audit-20260906/housing-tests.stderr.txt).

The source snapshot in [run.json](software-audit-20260906/run.json) was compared again after the extended tests and CAD audit:
no previously existing hardware or tool-source bytes changed. Read-only audit drivers are
`.codex-tmp/software-audit-run.py`, `.codex-tmp/audit-ring-board.py`, and `.codex-tmp/audit-cad-solids.py`.

## Bounds of the available inputs

- Selected TTC seller image supplies travel/force, not a controlled blade, plastic post or mounting-datum drawing.
  The [TTC manufacturer Bluish White page](https://en.ttc9.com/product/122.html) was reachable through a direct HTTP fallback;
  its table gives different travel tolerances/tactile force from the selected seller image. It cannot silently replace that variant's
  specification, and yielded no controlled blade/post drawing. Generic Cherry MX dimensions remain reference assumptions only.
- The [official PG1353S01D02-01 drawing](https://www.kailhswitch.com/uploads/15927/files/CPG1353S01D02-01-data-sheet.pdf)
  was also inspected. Its black-base/purple-stem 2024 reference is **not** identified as the user's blue-base/brown-stem Deep Sea lot.
  Its contact/extra feature drawing cannot establish exact selected-part interchangeability merely from the family name.
- Hat socket drawing still lacks barrel/flange tolerances and contact spring position, accepted blade range and usable engagement.
  Published PCB tolerance calculations are conditional on nominal socket dimensions, not worst-case part-pair qualification.
- Cap/head full-travel analysis requires the selected cap's hollow underside and mounting datum. The existing plate+1.50 mm
  underside threshold includes a 1.20 mm head and 0.30 mm engineering reserve; no exact cap is known to satisfy it.
- Screw length/driver/receiver, actual controller header stack and protected battery maximum envelope/rating remain exact-part inputs
  to check. Geometry for the specified nominal interfaces is checked, not every purchasable substitute. RF/charge transient/strength
  simulation without material and electrical models would be speculative, not verification.
- Rings geometrically produce one 0.20 mm flange layer when sliced at the specified height, but actual extrusion paths depend on
  printer/nozzle/profile. MX wall is 0.35 mm and V1 wall 0.65 mm. No selected calibrated slicer/printer profile is available.

Consequently this review separates **passed calculations**, **demonstrated defects**, **missing digital inputs**, and
**post-receipt physical tests**. It does not turn missing inputs into a pass, require a separately fabricated sample before the
first product under OPS-ARCH-007, or approve V1 assembly with a known interference.
