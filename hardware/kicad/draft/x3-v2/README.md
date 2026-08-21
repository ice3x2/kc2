# KC2 X3 V2 routed draft

Requirements: `CON-ARCH-004`, `CON-ARCH-006`

Status: **DRAFT - NOT ORDERABLE** until the physical coupon is fabricated,
populated, and checked with the intended switches, socket, keycaps, diode, and
lower housing, and the printed housing passes the 2.0 N deflection test.

These V2 files live only under `hardware/kicad/draft/x3-v2/`. The promoted
`hardware/kicad/kc2_left/` and `hardware/kicad/kc2_right/` projects are the
older verified X3 variant and are not V2 implementation evidence.

## Assembly modes

The two switch modes are mutually exclusive at every key position:

- Choc V2 / PG1353-class: install a Kailh `CPG135001S30`-class hot-swap socket
  on the PCB bottom. Do not directly solder the switch.
- Cherry MX-style 5-pin PCB-mount: install the switch from the PCB top and
  directly solder its two electrical pins. No MX hot-swap socket is supported.
- Choc V1 / PG1350, Choc V2 direct-solder, and MX hot-swap are unsupported.
- Never install both a Choc socket and an MX switch at one key position.

The left and right boards use their physical split-keyboard orientations. The
bottom-side socket pattern must be read from the PCB bottom; the 1:1 bottom PDF
is already mirrored for a physical bottom view.

## Joined spacing

The joined reference places the right half `0.80 mm` farther outward than the
ordinary `19.05 mm` one-unit transform. Corresponding Choc V2 and MX assembly
modes are evaluated with the same selected cap envelope for each physical key.
All five actual seam pairs have a nominal `1.80 mm` cap-to-cap gap and a
`3.80 mm` row-center PCB gap:

| Row | Pair | Cap widths (left/right) | Center pitch | Center-to-PCB-edge (left/right) |
|---:|---|---:|---:|---:|
| 0 | `6`-`7` | `18.05 / 18.05 mm` | `19.85 mm` | `8.025 / 8.025 mm` |
| 1 | `T`-`Y` | `18.05 / 18.05 mm` | `19.85 mm` | `8.025 / 8.025 mm` |
| 2 | `G`-`H` | `18.05 / 18.05 mm` | `19.85 mm` | `8.025 / 8.025 mm` |
| 3 | `B`-`N` | `18.05 / 18.05 mm` | `19.85 mm` | `8.025 / 8.025 mm` |
| 4 | `Space`-`B` | `22.8125 / 18.05 mm` | `22.23125 mm` | `10.40625 / 8.025 mm` |

The two complete closed Edge.Cuts outlines are compared segment by segment,
including horizontal stair transitions. Their exact minimum is `1.10 mm`,
created by a direction-aware `0.55 mm` transition stagger. PCBWay's published
`+/-0.20 mm` CNC outline tolerance gives a conservative two-edge lower bound
of `0.70 mm` at that limiting transition. This is digital nominal geometry;
actual half-to-half housing registration and assembled cap/switch play still
require a printed first article.

After soldering an MX switch, trim both electrical terminals after inspection.
The 2.50 mm lower plate has exterior-bottom-open cutouts through the full plate
height for every MX terminal and solder joint, rather than a closed component
cavity. The lateral solder-fillet model includes a 0.30 mm allowance.

The Choc socket SMD solder-fillet model also includes a 0.30 mm lateral
allowance. The V2-specific rail/post verifier reports zero socket, MX, diode,
track, via, controller/reset, battery-access, and key-travel intersections;
all required exported cutouts retain at least 0.3263 mm measured XY clearance.

The limiting left D2 diode body/pad/0.30 mm solder-fillet envelope is 1.35 mm
inside PCB Edge.Cuts; the release gate is 1.30 mm. It keeps 1.035 mm from the
nearest hybrid switch pad and has no switch/socket/fillet or solder-tool
approach conflict. Other straight-edge-limited relocated diodes are at least
3.95 mm inside Edge.Cuts. With the 0.10 mm housing inset and 0.35 mm cutout
allowance, the left housing retains 0.90 mm of uninterrupted material outside
the limiting diode opening (0.85 mm release gate).

## Battery service path

The direct battery wires do not use carrier-PCB power copper. The netless
3.6 x 2.2 mm NPTH lead slot is at the nice!nano USB/B+ end, matching the
official nice!nano v2 battery-pad location. Route insulated B+ and GND/B-
leads between socket rows, deburr the slot, add strain relief, and keep the
wire path outside the antenna keepout.

## Outputs

- Routed boards: `kc2_left-x3-v2/` and `kc2_right-x3-v2/`
- Physical fit coupon CAD: `coupon/`
- Draft Gerber/Excellon packages: `fabrication/`
- 1:1 top/bottom assembly PDFs: `mechanical/`
- KiCad 3D inspection renders: `renders/`
- Housing clearance evidence: `../../../case/draft/x3-v2/`

The coupon contains conservative representative 0-degree and 180-degree
bottom socket orientations plus a 5-pin MX direct-solder sample at 19.05 mm
pitch. The 180-degree sample deliberately exercises the rotated/mirrored
assembly risk required by `CON-ARCH-004` AC-8. Its CAD and fabrication package
do not satisfy the physical evidence gate by themselves.

## Reproduction and verification

Run PCB tools with KiCad 10 Python:

```powershell
$kpy = 'C:\Program Files\KiCad\10.0\bin\python.exe'
& $kpy -m tools.generate_kc2_pcbs --variant x3-v2 --output-dir tmp_x3_v2_clean
& $kpy -m tools.render_kc2_x3_joined --variant x3-v2 --placement-mode key-pitch --scale 7 --output-dir hardware/kicad/draft/x3-v2/renders
& $kpy -m tools.verify_kc2_x3_v2
& $kpy -m tools.verify_kc2_x3_v2_coupon
& $kpy -m tools.verify_kc2_x3_v2_outline
& $kpy -m tools.verify_kc2_x3_v2_fabrication
& $kpy -m tools.verify_kc2_x3_v2_mechanical
& $kpy -m tools.verify_kc2_x3_v2_zmk_firmware
python -m tools.verify_kc2_x3_v2_housing
```

The render command writes both SVG and PNG evidence. If Pillow is unavailable
in KiCad Python, it automatically uses an installed Chromium-family browser;
on Windows it detects Microsoft Edge in its standard install locations. Set
`KC2_HEADLESS_BROWSER` to an explicit browser executable when auto-detection is
not appropriate. The focused test launches this exact CLI with the active
KiCad Python and verifies that both fresh PNG files have valid dimensions.

The isolated generator output is intentionally unrouted. The committed board
files include the reviewed route completion and must retain KiCad DRC results
of zero violations and zero unconnected items.

When only the generated outline policy changes, use
`tools.repair_kc2_x3_v2_compact_edge --sync-edge-cuts-from <fresh-board>`.
The command rejects non-rigid switch geometry, replaces only Edge.Cuts, and is
covered by route/footprint-preservation and idempotence tests.

The final diode-edge autoroute snapshots are
`autoroute/kc2_left-x3-v2-71-r14.{dsn,ses}` and
`autoroute/kc2_right-x3-v2-71-r12.{dsn,ses}`. After importing the left session,
run `tools.finalize_kc2_x3_v2_routes` with
`--restore-left-controller-columns`; this restores the reviewed L_COL0/L_COL1
fanout that Freerouting leaves open and is covered by a reconstruction and
idempotence test. After importing the right session, run
`tools.repair_kc2_x3_v2_compact_edge --cleanup-dangling-tracks` to remove only
connectivity-proven dangling autorouter branches.

The project explicitly ignores five KiCad diagnostic classes: missing
courtyard, track-not-centered-on-via, tuning-profile track geometry,
symbol/footprint-filter mismatch, and footprint component-type mismatch.
These are generated-board metadata, custom hybrid-footprint library, or
non-applicable tuning diagnostics. The
electrical implications remain covered by exact footprint geometry checks,
matrix-island connectivity checks, NPTH copper-free checks, Gerber/Excellon
inspection, and zero DRC violations/unconnected items.

Official geometry references:

- Kailh Choc V2 switch: https://www.kailhswitch.com/mechanical-keyboard-switches/key-switches/kailh-low-profile-switch-choc-v2.html
- Kailh socket drawing: https://www.kailhswitch.com/uploads/15927/files/CPG135001S30.pdf?rnd=925
- Cherry MX2A 5-pin datasheet: https://www.cherry.de/fileadmin/media/Industrial/Switch/MX_BLACK/Data_sheet_MX2A_Black.pdf
- nice!nano v2 pinout and schematic: https://nicekeyboards.com/docs/nice-nano/pinout-schematic/
