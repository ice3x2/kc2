# Independent r4 final package review

Requirement: `OPS-ARCH-007`, preserving `CON-ARCH-004/006` digital/physical separation.

Result: **PASS for the actual sealed r4 package and current source bindings**. Physical qualification remains false. No order, payment, PCBA authorization or sealed-package mutation was performed.

Target: `hardware/kicad/first_order/solid-floor-20260907-r4`.

The independent audit used Python standard-library SHA-256, ZIP CRC and direct byte comparisons without importing the production release checker. [Machine result](kc2-solid-floor-final-package-review-2026-09-07.json) reports errors=[] and process exit0.

- Package contains exactly8 files: manifest, review evidence, digital validation, fabrication profile, two manual BOMs and two fabrication ZIPs; the manifest binds exactly the other7 outputs.
- Both ZIPs contain exactly15 expected entries with no extras/duplicates. CRC checks and every embedded entry SHA pass. All30 payloads are byte-identical both to the exact reviewed r3 RAW files and to their corresponding entries in the sealed r3 ZIPs. Thus r4 updates housing/assembly evidence without modifying PCB fabrication bytes.
- All294 manifest source bindings exist and match current raw SHA-256. The manifest and review-evidence binding maps agree exactly. Sealed package bytes were unchanged before/after inspection.
- `first_order_ready=true`; `physical_qualification_complete=false`; machine placement and BOM/CPL upload authorization remain false. The digital-validation record has errors=[] and eligible_to_build=true.
- Both BOMs identify the1.20 mm closed floor with exterior Z-2.20 mm, unchanged7.5 mm nominal screw and12 nominal silicone feet with physical qualification false.
- All16 local links in root `order.md` exist. Both left/right silicone-foot SVG paths are correct; order ZIP links select r4, not historical r3. The guide itself is one of the294 current source bindings.

| File | Raw SHA-256 |
|---|---|
| r4 manifest.json | `2906bf329030840634a5cee1c53c74dd8efb1a70226d1fdc24b66156f693dc92` |
| Left fabrication ZIP | `5f4d65a3f45e4efddb093bb8909eef03ea83c54483616d0d0d52935626806811` |
| Right fabrication ZIP | `bfeb90e32a9dc7dd73c8b3ace95cf3cd7601e220daa7eefbdd51e2e940cf397c` |
| Root order.md | `63940fa7f2e6ce9eb01600abe19dea86807274faebbb09689394a7727d17dddb` |

This final review checks delivered package integrity and provenance; it does not reclassify actual contact fit, unknown lead/solder projections, printed strength, thermal/RF or silicone adhesive behavior as measured passes. The source-bound engineering reviews and post-receipt limits remain applicable.
