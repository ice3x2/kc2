# KC2 native Fusion housing export

Requirement: `CON-ARCH-006`, AC-9 native-deliverable portion only.
Date: 2026-09-06. Physical fit, minimum qualified assembly height and order
readiness are not established by this report; AC-9 remains open as a whole.

## Actual execution

After the user opened Fusion, the previously observed session-limit dialog was
gone. No remote session was suspended or logged out by this agent. The local
Fusion Python text console reported version `2603.1.52`. The repository exporter
was executed in that running Fusion application, not in a mocked Python process:

`tools/fusion/KC2StepToF3D/KC2StepToF3D.py`

Exporter LF-normalized SHA-256:
`8e6c940ebd652e24aefc79904a382708828c48f00c256b899d02cdc8275e70e3`.

All four STEP inputs were imported as Fusion designs. Each F3D was exported with
Fusion's native archive API and re-imported into a separate Fusion document.
Only the documents created by the exporter were closed. The completion dialog
reported successful lower and MX upper exports and was acknowledged.
There were no existing native outputs to overwrite on this first successful run.
No canonical PCB, STEP or STL geometry was modified by the export.

## Deliverables

All paths are under `hardware/case/`.

| Archive | Solid bodies | File SHA-256 |
|---|---:|---|
| kc2_left_lower_housing.f3d | 1 | `0345f8519ed0bb106ec1f23781081d537a425cdead51ca9e928ecaed6f822843` |
| kc2_right_lower_housing.f3d | 2 | `54376043b2762402487496672c58e0637c1e23a308b128ed4739529a1c635fe5` |
| kc2_left_mx_upper_housing.f3d | 1 | `5a44813aa0c15d0c8a9ba6648ce0d0dd769cb8993bd95795bf0e2218c540b4aa` |
| kc2_right_mx_upper_housing.f3d | 2 | `515902ab81000788805f732ad75da5b0b148f020ef076d061679d6e335658bc4` |

`hardware/case/kc2_fusion_export_result.json` records the actual Fusion version,
source/archive SHA-256 values, source/reopened per-body bounds and volumes,
body counts, export success and `status=pass`. `order_ready=false` remains.
These are native archives of imported solid geometry, not a reconstructed
parametric sketch/feature history.

## Independent verification

- The parent ran `tools.verify_kc2_housing_f3d`: PASS. All bodies fit the
  150 mm build envelope, and hashes and reopened geometry satisfy the checker.
- The independent-review agent inspected all four archive containers: ZIP CRC
  checks passed; Fusion metadata and native BREP payloads were present, with
  one/two bodies per side. They are not renamed STEP files or arbitrary ZIPs.
- The housing agent independently imported all four source STEP files using
  CadQuery and compared all six solids with the Fusion source and reopened
  records. Maximum bounds difference was `5.258016244624741e-13 mm`; maximum
  volume difference was `3.6707206163555384e-9 mm3`. Both are within the existing
  0.001 mm / 1 ppm limits. Fusion's own before/after metrics were identical.
- Cross-checking rounded CAD/STL evidence also passed; the maximum bounds
  discrepancy was 0.00005 mm, within 0.001 mm.

Before execution, TDD repaired two evidence issues: occurrence bodies now use
assembly-context proxies instead of untransformed component bodies, and all
four fixed body counts are enforced. Bounding comparisons consistently use the
existing 0.001 mm tolerance and reject nonfinite or nonpositive bounds.
Nine Fusion tooling tests passed (`.codex-tmp/fusion-live-preflight-tests.log`).
After live export, the combined Fusion tooling, MX housing contract and release
integration suites passed all 20 tests (`.codex-tmp/fusion-live-final-tests.log`).
The assembly-context API contract is documented by Autodesk at
https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Occurrence_bRepBodies.htm.

## Remaining qualification

Fresh `tools.verify_kc2_x3_v2` returned exit 2 with PCB `errors=[]` and nine
remaining readiness blockers (`.codex-tmp/mx-post-fusion-release.log`). The five
missing native archive/result blockers have been resolved. The five MX
mechanical qualification groups and four physical evidence bundles remain open.
Exact switch/socket fit, long screw/receiver qualification, printing material
and tolerances, full-travel/service clearances and physical electrical/mechanical
tests cannot be inferred from successful native conversion. No fabrication
package or order approval was produced.
