# Independent final r3 package review

Date: 2026-09-06. Requirements: `OPS-ARCH-007`, `CON-ARCH-004`.
Read-only review of `hardware/kicad/first_order/v1-recess-20260906-r3/` after packaging.
This report is outside the sealed package and does not change any bound source.

## Result

`tools.prepare_kc2_first_order --verify-package hardware/kicad/first_order/v1-recess-20260906-r3`
returned process exit **0**, `errors: []`, `first_order_ready: true` and
`physical_qualification_complete: false`. Output is recorded in
`.codex-tmp/v1-recess-independent-package-verify.json` (PowerShell-redirection text encoding).

Separately from that verifier, PowerShell/.NET ZIP inspection and raw SHA-256 recomputation found:

- Exactly 8 package files: manifest, review evidence, digital validation, fabrication profile,
  two manual MX BOM JSONs and two bare-PCB fabrication ZIPs.
- All **282 source/review bindings** match current raw file bytes.
- All **7 non-manifest delivery-file hashes** match the manifest.
- Each ZIP has exactly **15 unique entries**; all **30 entry payload hashes** match the manifest.
- No nested paths, duplicate entries, BOM, CPL, placement data or machine-assembly upload files occur
  inside either ZIP.
- `assembly_service = none_hand_assembly`, `machine_placement_requested = false`,
  `bom_cpl_upload_authorization = false`, and physical qualification remains false.

## Exact ZIP inventory

Both halves use their own `kc2_left` / `kc2_right` prefix and this identical suffix inventory:

| Category | Suffixes | Count |
|---|---|---:|
| Copper | `-F_Cu.gtl`, `-B_Cu.gbl` | 2 |
| Mask | `-F_Mask.gts`, `-B_Mask.gbs` | 2 |
| Paste | `-F_Paste.gtp`, `-B_Paste.gbp` | 2 |
| Silkscreen | `-F_Silkscreen.gto`, `-B_Silkscreen.gbo` | 2 |
| Outline | `-Edge_Cuts.gm1` | 1 |
| Job | `-job.gbrjob` | 1 |
| Separate drills | `-PTH.drl`, `-NPTH.drl` | 2 |
| Drill maps | `-PTH-drl_map.gbr`, `-NPTH-drl_map.gbr` | 2 |
| Drill report | `-drill-report.txt` | 1 |

The actual artwork was independently viewed in the separately source-bound
[r3 Gerber visual review](kc2-v1-recess-gerber-visual-review-2026-09-06.md).
This ZIP check confirms packaging/provenance, not an additional physical trial.

## Raw byte fingerprints

- `manifest.json`: `39926547bfcb4968fc116920869b9aa0b44c862b9c4e09f1af288f32dbfc833d`.
- `kc2_left-pcb-fabrication-only.zip`: `2459c9648476996b46dd6e5f1b66e868756ce085a55620820d7cd34be629a8a1`.
- `kc2_right-pcb-fabrication-only.zip`: `d10b2e424d860e5417186c02d498b9bb79e811a4cd9b99f309fff65ce1e536d1`.

## Scope limits

The source-bound first-product package gate passes, separately from post-receipt acceptance under
`OPS-ARCH-007`. Exact selected socket contact tolerances, selected-switch controlled dimensions,
actual keycap underside, printed fit/strength and solder/contact reliability are not established by
archive integrity. Keep the release's disclosed residual risks and assembly restrictions. No order,
payment, upload or automatic assembly authorization occurred in this review.
