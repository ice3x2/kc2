# MX receptacle / plate-lid digital revision status

Requirements: `CON-ARCH-004`, `CON-ARCH-006`, `CON-ARCH-007`, `REL-ARCH-001`.

This is partial implementation evidence, not fabrication approval. The user
requires the first small-batch build to be the final product; a provisional
coupon geometry is not a substitute for that outcome. No acceptance criterion
is closed by this report.

## Current PCB evidence

The canonical left/right boards contain enlarged exposed controller lands
(1.80 x 2.40 mm, 0.95 mm drill) and 140 MX receptacle contacts
(2.50 x 3.20 mm, trial 1.60 mm finished PTH). The selected open-bottom hat socket
is specified by nominal length 3.00 mm, barrel OD 1.45 mm, flange OD 2.00 mm and
flange thickness 0.20 mm. Its manufacturing and contact tolerances remain unknown.

LF-normalized board SHA-256 identities:

- Left: `e1a50fa657a2cc8ad10a60eed9e0fd5d326c6a138315f429414b9fc18d3b5583`
- Right: `30029aac80a7d1ce0cdf15ead621dcc9906e51775e031c4dffe4841aff8f618c`

`hardware/kicad/kc2_drc_evidence.json` binds the latest canonical board, project
and DRC reports. Both reports contain no violations or unconnected items.
Five inherited non-electrical check exclusions remain explicitly reported;
DRC alone does not qualify physical pinout, solder access or assembly fit.

`hardware/kicad/autoroute/kc2_mx_solder_support_routes.json` schema 2 records
the current routes and complete pad fingerprint, including mask expansion.
The generation manifest now binds this replay, the PCB generator and replay
tool hashes. Previous DSN/SES records remain explicitly historical; they have
not been relabeled as new routing or fabrication evidence. The manifest was
refreshed after a successful read-only preview, with a backup under
`.codex-tmp/kc2_generation_manifest-before-mx-20260906T020311915200Z.json`.

Fresh checks on 2026-09-06:

- 36 focused tests passed: hand-solder pads, selected assembly metadata, route
  binding/snapshot, MX physical-evidence validation and release integration.
  Command: KiCad Python `-B -m unittest tools.test_kc2_hand_solder_pads
  tools.test_kc2_mx_manifest_contract tools.test_kc2_mx_route_binding
  tools.test_kc2_solder_route_snapshot tools.test_kc2_mx_release_integration
  tools.test_verify_kc2_mx_receptacle_evidence`.
- Fresh generator / route replay test passed for both halves, including DRC
  of the regenerated and rerouted boards. Command: KiCad Python
  `-B -m unittest tools.test_kc2_generator_route_replay`.
  Scratch evidence: `.codex-tmp/generator-route-replay-y2wy_ob1/`.
- Main `tools.verify_kc2_x3_v2` returned exit 2, `errors=[]`, not order ready.
  At this checkpoint it reports an outdated lower-housing schema check and
  four missing physical-evidence bundles. Its printed digital-pass sentence
  must not be read as upper-housing, native Fusion or full-release approval.
- Full `tools.test_verify_kc2_x3_v2` regression at this checkpoint ran 83 tests
  and failed (9 failures, 16 errors). The log is
  `.codex-tmp/mx-current-main-suite.log`. Failures include historical route counts,
  generated-path assumptions, the old two-mode contract and the old reset gap;
  these require investigation and are not waived by the focused test passes.

## Housing deliverables and limits

Canonical `hardware/case/` contains four STEP files (left/right lower and MX
upper), and six STL parts (one left and two right parts for each housing type).
The housing agent recorded 37 passing housing tests. The lower clearance report
binds the PCB hashes above and reports collision-free nominal support geometry.
The upper manifest records watertight parts within the 150 mm build envelope.

The MX lid is still based on provisional 14 mm apertures, 1.5 mm clip thickness
and 5.2 mm PCB-top-to-plate-top distance. These are development inputs, not
validated dimensions for an identified purchased switch. The manifest correctly
retains `print_ready=false` and `order_ready=false`.

## Remaining release work

- Exact MX switch drawing and socket contact/OD tolerance limits; finished-hole
  and blade engagement qualification, practical solder wetting and replacement
  cycle evidence. Nominal fit calculations are not measured evidence.
- Full upper/lower assembly review: switch flange relief, keycap full travel,
  screw/driver collision, qualified long-screw length and receiver torque,
  print material/tolerance, split-joint retention and 2 N deflection.
- Four real native Fusion F3D exports and reopen evidence. No F3D archives have
  been delivered. The observed Fusion session conflict requires user direction
  before suspending another computer's session.
- Explicit MX upper/F3D integration in the main release gate, refreshed
  mechanical/render/BOM/coupon and fabrication evidence as permitted by the
  fabrication gate, and full regression/independent review.
- Controller/service, scan/contact, housing and power/RF physical bundles remain
  unsubmitted. Synthetic unit-test observations are not production evidence.

Historical direct-solder/lower-only fabrication packages must not be ordered
as the revised MX assembly. No revised fabrication package or order approval
was generated by the metadata refresh.

## Follow-up: selected housing gate repaired

The new `tools.verify_kc2_mx_housing_contract` reads the actual upper STL
topology/bounds/volume and STEP solid counts, checks canonical artifact and
generator hashes, and independently recomputes the current PCB extraction when
the lower manifest has source-rebinding evidence. It accepts the nominal digital
geometry while retaining explicit qualification and native-archive blockers.
It is not a replacement for the lower CAD collision verifier or physical tests.

The main release verifier now requires this selected-assembly gate and six
additional physical source bindings: the MX upper manifest, Fusion export result
and all four F3D archives. Legacy lower-only physical evidence cannot waive the
new assembly. The CLI now says `PCB CHECKS PASS`, not the broader digital/housing
pass sentence quoted at the earlier checkpoint.

The parent reran both housing-contract and release-integration suites: 11 tests
passed. Fresh main verification returned exit 2 with `errors=[]`; the obsolete
lower-schema blocker is gone. Five specific MX qualification blockers, five
missing native-file/result blockers and four physical-bundle blockers remain.
Logs: `.codex-tmp/mx-current-upper-gates.log`,
`.codex-tmp/mx-current-contract.log`,
`.codex-tmp/mx-current-release-with-upper.log`.

The parent also reran the full three-module housing suite: 37 tests passed in
170.941 seconds (`.codex-tmp/mx-current-housing-suite.log`). This is digital
geometry evidence only.

Native-verifier review identified a remaining limitation for the eventual
Fusion delivery: the current checker binds hashes and declared round-trip
metrics but does not independently recognize Autodesk native container contents;
upper body counts were derived from the declared source records. A failing
regression then drove a fix that independently requires left upper 1 and right
upper 2 bodies, matching the current STEP geometry. All six Fusion tooling tests
pass (`.codex-tmp/mx-fusion-count-red.log` and `mx-fusion-count-green.log`).
Genuine Fusion export/reopen and native-container inspection remain necessary
before native acceptance. With all four archives absent today, this remaining
limitation does not create an order pass.

## Follow-up: historical replay mutation gap

After updating stale regression fixtures, eight service-pad mutation subcases
exposed a real historical-finalizer gap: an exact final-route hash could take
the idempotent path without checking pad connectivity. The fast path now invokes
the existing pad-net, actual matrix/service connectivity and mounting-geometry
checks for the support-detoured route stage before returning. No hash constants
or tolerances changed. Three targeted historical tests passed, including the
disconnected-pad mutations; an independent reviewer also reran the mutation
test successfully. Historical fixtures are loaded from immutable Git commit
`2c82b4eb8a2bcf091f7e594a5267c71d11d64572` into temporary files; revised boards
are not represented as historical finalizer inputs.

The parent reran all ten focused modules together after integration: 54 tests
passed in 10.436 seconds (`.codex-tmp/mx-final-focused.log`). Canonical PCB
LF-normalized hashes remain exactly those recorded above.

The final full main regression rerun also passed: 83 tests in 119.246 seconds,
recorded in `.codex-tmp/mx-main-suite-final.log`. This supersedes the earlier
83-test failures in this report as the current result. It does not supersede
the explicit physical/native/fabrication limitations or authorize ordering.
The route agent's PowerShell wrapper reported exit 1 from KiCad duplicate-image
stderr handling; the unittest log itself ends in `OK`. This is not a claim that
that wrapper returned zero. The final main release command independently remains
exit 2 with the 14 genuine blockers (`.codex-tmp/mx-final-release.log`).

## Later native-delivery update

The user subsequently opened Fusion. All four real F3D archives were exported
and reopened successfully, with independent STEP geometry comparison. The
earlier missing-native statements above are historical; see
[the native export report](kc2-fusion-native-export-2026-09-06.md) and
`hardware/case/kc2_fusion_export_result.json` for current evidence. Nine physical
and assembly qualification blockers remain; this is not order approval.
