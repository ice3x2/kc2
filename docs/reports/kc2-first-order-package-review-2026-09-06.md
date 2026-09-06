# First-product package code review — 2026-09-06

Requirement: `OPS-ARCH-007 AC-1/2/3/4/5` (evolving, in progress).

Independent review covered `tools/prepare_kc2_first_order.py` and
`tools/test_prepare_kc2_first_order.py`. No production package was created by
this review and no PCB or manufacturing input was modified.

## Result and regression evidence

The original nine tests passed. Two additional mutation tests then failed as
expected: removing a selected manual BOM and its output hash was accepted;
changing the manifest to request machine placement was also accepted. The
small correction requires the exact output inventory and explicit hand-assembly
flags. All eleven tests now pass:

```powershell
python -B -m unittest tools.test_prepare_kc2_first_order
```

Current raw-byte SHA-256:

- Package tool: `0abdecc87b28862c83c6cb502a47e4c8b6a6693fb87ad013e1fef5fb94aef743`
- Tests: `1d0109b281c6c6583914765b97948e5abcc175543ac0a3e017204ef4bf5e0215`

The review confirmed required raw-byte source/review bindings, independent
board/project/DRC-sidecar consistency, source/output drill and solder-land
comparison, explicit unchecked-review/known-blocker rejection, no overwrite,
staged publication and rechecking source bytes before publication.

## Exact delivery inventory

The sealed delivery directory must contain exactly eight files:

- `manifest.json`
- `review-evidence.json`
- `digital-validation.json`
- `fabrication-profile.json`
- `kc2_left-manual-mx-bom.json`
- `kc2_right-manual-mx-bom.json`
- `kc2_left-pcb-fabrication-only.zip`
- `kc2_right-pcb-fabrication-only.zip`

The manifest hashes the seven other files. Each ZIP must contain exactly fifteen
reviewed files for its own half: nine Gerbers (front/back copper, mask, paste and
silk, plus outline), the Gerber job, separate PTH/NPTH drills, two drill maps,
and the drill report. Names and bytes must match the bound input allowlist.
No BOM, CPL, historical ZIP or other placement file may enter those ZIPs.
The selected manual MX BOMs are separate hand-assembly references.

`machine_placement_requested=false`, `bom_cpl_upload_authorization=false`,
`assembly_service=none_hand_assembly` and
`physical_qualification_complete=false` remain enforced. A successful first-order
build does not turn pending physical records into passed records.

## Limits

The qualitative review booleans are engineering sign-offs backed by hashed
reports, not an independent geometric proof or cryptographic reviewer identity.
The standalone `verify_package()` function checks offline package bytes and
inventory. The CLI `--verify-package` additionally revalidates the bound evidence
against current repository sources. The package verifier does not independently
rederive the entire manual BOM from the source board; the build derives it and
binds its bytes. An entirely rewritten evidence set still requires legitimate
engineering review, not merely recalculated hashes.

Actual Gerber visual observations, including the three same-net exposed-via
solder-wicking exceptions, are recorded in
[the visual review](kc2-mx-gerber-visual-review-2026-09-06.md). Exact component,
housing and full-travel assessments belong to their separate bound reports.
This code review alone is not first-order approval, physical qualification,
machine-placement permission or authorization to purchase.
