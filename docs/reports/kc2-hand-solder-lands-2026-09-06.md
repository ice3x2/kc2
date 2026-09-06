# Enlarged hand-solder lands: partial implementation

Requirements: CON-ARCH-004 AC-3/AC-10; CON-ARCH-007 AC-2.

This is development evidence, not fabrication approval. All corresponding acceptance criteria remain open.

## Independent-review correction

The initial three-test PASS below was insufficient: creating the controller mutated KiCad's shared `LSET.AllCuMask()` value, which made subsequent in-process mask checks pass and caused wildcard serialization to omit explicit mask layers on saved PTHs. A fresh isolated process read the saved U1, POWER and battery pads with no mask openings. Treat the initial mask claim as disproven until saved-board fresh-process tests pass after repair.

The generator and MX updater now copy the copper layer set before adding mask layers. New tests first reproduced both static-set mutation and missing saved-board masks. PCB repair is restoring explicit masks along with route detours; current completion must be established from new reports, not the earlier test result.

Subsequent verification: all eight `tools.test_kc2_hand_solder_pads` tests now pass, including isolated-process reads of saved canonical U1 masks. The combined source-footprint, hand-solder, dimensional-manifest and MX-evidence tests ran 31 tests with an `OK` result (`.codex-tmp/mx-focused-regressions.log`). This restores confidence in the specific pad/mask checks; routing, housing support wear clearance and complete release verification remain unfinished.

The independent review also added a separate MX receptacle physical-evidence gate, integrated with typed hashed specification documents, actual switch/coupon identity, three-key/two-contact coverage, replacement-cycle records and numeric contact limits. Fifteen focused gate tests pass with synthetic test data only. No physical measurements have been supplied. The existing positive legacy physical fixture now fails because it lacks the new evidence; it is not valid receptacle qualification.

## Implemented geometry

Both canonical boards and their source footprints now use:

| Contact | Copper land (mm) | Drill (mm) | Mask |
|---|---|---|---|
| Controller U1, 24 per half | 1.80 x 2.40 oval | 0.95 | Explicit F.Mask and B.Mask, no paste |
| MX, two per key / 70 keys | 2.50 x 3.20 oval | 1.60 trial | Explicit F.Mask and B.Mask, no paste |

Oval elongation is footprint-local Y. Centers and net identities are unchanged. Duplicate-number Choc SMD contacts remain unchanged. The controller generator retains the enlarged lands and mask openings for x3-v2 only. Previously U1 pads specified copper layers without mask openings; copper enlargement alone would not correct that defect.

The selected socket nominal dimensions and qualification gates are recorded in CON-ARCH-004. The 1.60 mm hole is a coupon starting value, not a qualified finished plated-hole fit. CON-ARCH-007 now accounts for the reduced nominal battery-to-controller copper gap.

## Verification

Command: `"C:/Program Files/KiCad/10.0/bin/python.exe" -B -m unittest tools.test_kc2_hand_solder_pads`

Result: three tests pass. Tests were added before implementation and initially failed on the old pad sizes/mask layers. Coverage includes controller generation, controller source/placed pads, and all 70 switch locations plus source footprint. This does not verify routes, plotted mask output, physical fit or hand-solder performance.

KiCad 10 DRC with zone refill, exclusions included, save_board=false:

| Result | Left | Right |
|---|---:|---:|
| Shorting items | 8 | 10 |
| Copper clearance errors | 17 | 32 |
| Hole clearance errors | 0 | 1 |
| Library footprint mismatch warnings | 1 | 1 |
| Unconnected items | 0 | 0 |

Raw reports: `docs/reports/kc2-hand-solder-left-2026-09-06.drc.json` and `docs/reports/kc2-hand-solder-right-2026-09-06.drc.json`.

The enlarged pads intersect existing routes. These errors are unresolved. The earlier zero-error baseline does not apply to these modified boards. Project ignored checks are listed in the raw reports and are not manufacturing signoff.

## Remaining work

Repair affected routing and drill spacing; resolve library mismatches; rerun all electrical/net/physical-component checks and inspect mask plots. Qualify socket tolerances and MX blade contact on coupons, controller/switch solderability and battery insulation. Regenerate dependent artifacts only from a validated board. No new fabrication package was generated and no order approval is given.

Edit backups are beside the boards/controller libraries (`*.bak-20260906-*`) and in `.codex-tmp/*-before-mx-lands-*.kicad_pcb`.
