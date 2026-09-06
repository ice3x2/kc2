# MX Gerber/Excellon inspection, not fabrication approval

Requirements: `CON-ARCH-004` AC-3/AC-7/AC-8/AC-10, `CON-ARCH-006`,
`CON-ARCH-007`. The user requested final fabrication preparation including
Gerbers. Raw files were generated for the pre-package inspection required by
AC-8. This does not waive the remaining fabrication/order gates.

## Source and output identity

Canonical board LF-normalized SHA-256 values remain unchanged:

- Left: `e1a50fa657a2cc8ad10a60eed9e0fd5d326c6a138315f429414b9fc18d3b5583`
- Right: `30029aac80a7d1ce0cdf15ead621dcc9906e51775e031c4dffe4841aff8f618c`

Inspection outputs: `hardware/kicad/fabrication_review/mx-receptacle-20260906/`.
Each `left/` and `right/` directory contains 15 files: nine layer Gerbers,
one Gerber job file, separate PTH/NPTH Excellon files, two drill-map Gerbers
and one drill report. There is no ZIP, BOM/CPL, placement authorization or
fabrication approval in this output set.

Output-set SHA-256 values are computed by sorting the 15 files by filename,
concatenating UTF-8 `filename + TAB + canonical_hash.sha256_file(file) + LF`
for each file, then hashing the concatenation:

- Left: `3340930d00f3ec28d06497d98bc83d728d2637960f936b4b617ac2b860f2d6aa`
- Right: `9dad96fd77bca793de050547e9b16ad687f58a770df186bbea24811b833db01f`

## Execution and recovery

KiCad MCP exported nine layers with `--check-zones`, using KiCad 10.0.3:
`F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts`.
The MCP drill tool's default output merged plated/nonplated holes. Its interface
does not expose the required separation flag, so the official KiCad CLI was used
with `--format excellon --excellon-separate-th --generate-map --map-format gerberx2
--generate-report --report-path <side>-drill-report.txt`. Coordinates remain
absolute, metric, decimal, with the default alternate oval format.

The four initial mixed-drill/PDF-map files were moved, not deleted, to
`.codex-tmp/mx-first-drill-20260906/`; they are excluded from the inspection set.
Existing historical fabrication ZIPs were not overwritten or relabeled.
An initial MCP inventory query used an unsupported category; retrying the full
inventory identified the actual `manufacturing_exports` category.

## Reviewed evidence

Fresh MCP DRC on both canonical boards passed with no violations or unconnected
items. Reports: `.codex-tmp/mx-order-request-left.drc.json` and
`.codex-tmp/mx-order-request-right.drc.json`. The five inherited excluded check
classes remain visible. There are no canonical schematic files, so this is not
independent schematic-parity or ERC evidence.

Before raw export, independent component/circuit review checked actual U1,
70 hybrid switches and their alternate-pad ties, 70 bottom SOD-123 diodes,
POWER/RESET, battery terminals, lead slots, mounting holes and other NPTHs.
Digital family geometry, intended net identities and actual matrix/service
connectivity passed. Physical received-part identity/orientation/fit remains
unqualified. U1 uses RAW/GND battery equivalents; top B+/B- socket assumptions
were not introduced. Diodes retain pad 1 row/cathode and pad 2 per-key/anode.

Both parent and independent reviewer compared the new files with the source
boards. The parent used the existing text-based board parser; the independent
reviewer used the actual pcbnew board objects.

| Check | Left | Right |
|---|---:|---:|
| PTH holes, including vias | 118 | 166 |
| NPTH holes/slots | 195 | 244 |
| MX 1.60 mm trial PTH contacts | 62 | 78 |
| U1 0.95 mm PTH contacts | 24 | 24 |
| Via 0.30 mm drills | 27 | 59 |
| Mounting 1.60 mm NPTH holes | 8 | 9 |
| U1 + MX flashes per copper/mask layer | 86 | 102 |

Every exported PTH/NPTH center, round diameter and slot span matched the source
within the existing 0.002 mm output-comparison tolerance; no extra/missing holes
were found. Both halves include one 3.60 x 2.20 mm nonplated battery-lead slot.
All enlarged U1/MX oval copper and mask aperture sizes and centers matched the
source on both sides. There were no PTH-centered paste flashes, and no
via-centered mask flashes. All nine layer files had plotted operations and
M02 terminators. Existing plotted-glyph checks passed all 17 mounting labels
and each board's B+ and B-/GND battery legends.

These are parser/aperture/stroke checks, not a full independently rendered
Gerber polygon/boolean inspection. In particular, absence of a via-centered
flash alone is not proof that an unrelated mask region cannot cross a via.
No manufactured drill tolerance, contact fit or practical solderability was
established by file inspection.

## Remaining final-release work

The exact V2 release gate still returns exit 2: PCB `errors=[]`, five selected-MX
mechanical qualification groups and four physical evidence bundles pending.
The 1.60 mm MX PTH is explicitly a trial geometry; socket OD/contact tolerances
and the exact MX switch are not qualified. Controller/service, battery,
power/RF, long screws/receivers, printed fit and deflection remain open.

Full rendered/1:1 inspection and the revised dedicated derivative/release gates
must also pass before final packaging. Historical `fabrication/` direct-solder
BOMs and Choc-only quote files are not selected-MX procurement evidence. The
legacy exporter was not run because it would regenerate those stale contracts
and create ZIPs before the current gate passes. The canonical README was
updated to distinguish current MX geometry and raw inspection files from those
historical artifacts. No requirement or acceptance criterion was marked verified.
