# Closed-floor mechanical review

Requirements: `CON-ARCH-006`, `OPS-ARCH-007`; user-approved closed-floor revision. This report distinguishes actual geometry verification from physical strength, adhesive and purchased-part qualification. Historical r3 reports and sealed packages are not overwritten.

## Implemented geometry

The integrated floor occupies Z−2.20..−1.00 mm, thickness1.20 mm, below the existing support-column ends. The original support web remains Z0..2.50 mm, PCB underside/top2.50/4.10 mm, with all70 local supports and17 mounting pilots unchanged. The added floor does not change receiver entry, pilot depth or recessed-head bearing; the nominal7.50 mm screw remains unchanged.

Each of the three printable lower parts receives its own continuous floor. Right-side masks use the full outline and existing print-clearanced keyed split, **not** the component-cutout support masks. Two captive keys and their0.20 mm nominal joint clearance are retained. Component cavities are therefore internal reliefs above the floor, not holes through the bonding face. The floor is not claimed waterproof or dust-sealed at the assembly seam.

Each lower part has four flat diameter8 mm silicone-pad bonding regions on Z−2.20 mm, with nominal0.80 mm edge/seam reserve. The generated layout requires non-overlapping regions and a non-degenerate polygon of their centers containing the actual solid's projected mass centroid. These are geometric stability conditions, not measured friction, peel strength or load-deflection results. See `hardware/case/kc2_left_silicone_foot_layout.svg` and the right equivalent; coordinates follow the housing XY frame and identify the bottom bonding plane.

Existing fields named `desk_contact` now describe internal columns ending at the floor top. The generator explicitly labels that role. Legacy numerical desk-clearance aliases refer to the **inner floor**, not the physical desktop; silicone thickness remains unspecified.

## Component clearance and assembly limits

The inner floor is3.50 mm below PCB underside. The maximum permitted unknown lead/post/solder projection is2.90 mm, leaving0.60 mm nominal clearance:0.30 mm engineering print allowance plus0.30 mm residual clearance. This is an assembly acceptance limit, not proof that every unspecified component meets it. Inspect actual dimensions before assembly; do not force or grind switch/socket bodies.

Controlled nominal bottom projections remain Choc socket2.40 mm including allowance, diode1.65 mm including solder allowance, and hat-socket barrel1.20 mm. Their respective nominal inner-floor gaps are1.10,1.85 and2.30 mm. Unknown controller-pin tails, POWER/battery leads, switch posts and solder fillets remain explicitly unqualified. Solder and trim permissible electrical lead tails with the PCB removed from the lower housing; the closed floor intentionally removes through-bottom soldering access.

## TDD and independent evidence

Three initial requirement-linked tests failed because floor datums, complete floor masks and floor integration did not exist. They subsequently passed. A further shallow underside recess mutation exposed a weakness in checking only a middle axial section; full1.20 mm floor-volume inclusion was added so both a through-hole and a shallow bonding-face cavity are rejected. Existing support and mounting tests remain in the generator suite.

The permanent [generator test record](solid-floor-20260907-r4/floor-generator-tests.json) records eight passing tests in16.600 seconds, exit0, exact interpreter/command, log hash and unchanged before/after source hashes. No synthetic CAD fixture is represented as final canonical evidence.

Both canonical generators subsequently completed. The independent actual CAD audit [cad-solids.json](solid-floor-20260907-r4/cad-solids.json) finished with `errors=[]`, process exit0, and unchanged before/after raw source bindings. All four imported STEP models are valid: one left and two right solids for each lower/upper assembly. Both lower/upper intersections and all four conservative V1/MX ring-envelope intersections have zero volume. The ring check is a nominal housing-envelope clearance check, not socket contact qualification.

All three complete1.20 mm floor slabs match independently reconstructed split masks, with zero missing and zero extra floor volume. Measured floor volumes are15773.093791 mm³ left,9059.413698 mm³ right A and9552.127969 mm³ right B, matching their expected areas times thickness. All12 actual diameter8 mm bonding-face probes are complete and flat; every actual part mass centroid lies inside its bonding-center support polygon. No old r3 geometry/native pass is inherited.

The [fresh native check](solid-floor-20260907-r4/native-check.json) returns no blockers, exit0, and unchanged before/after raw bindings for all four current F3D archives, their STEP sources, Fusion result and verifier. This validates the recorded current export/reopen result, not printed fit or strength.

## Physical qualification remains pending

Floor flexure, layer adhesion, threaded-pilot stripping/installation torque, silicone thickness, adhesive preparation/retention, slip resistance, thermal/RF effects and actual received-part clearance require physical acceptance. A continuous valid CAD floor and a support polygon containing the centroid do not establish those properties. This report alone does not approve fabrication or spending.
