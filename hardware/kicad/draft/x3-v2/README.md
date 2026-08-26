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

## Matrix diode and polarity

The active V2 BOM contains exactly 70 Jingdao Microelectronics `ES1B` matrix
diodes: LCSC `C437840`, Eleparts goods `9475342`, SMA, 100 V / 1 A. All are
assembled on `B.Cu`. Pin/pad 1 is the cathode connected to the row net; pin/pad
2 is the anode connected to the per-key switch net. A physical bottom view is
mirrored relative to KiCad's top/front view, so place the cathode band toward
the marked pad 1 rather than relying on an assumed left/right direction.

The firmware contract remains `col2row`, active-high columns, and active-high
row inputs with pull-downs. The existing pinned build remains zero-wait: no
extra delay before reading inputs and no delay between driven columns. Do not
change those scan delays until a populated physical coupon has passed both
3.0 V and 3.3 V maximum same-row and maximum same-column stress tests. Those
tests remain pending, so these digitally verified boards are not orderable.

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
| 4 | `Space`-`B` | `32.3375 / 18.05 mm` | `26.99375 mm` nominal (`26.9937 mm` in the routed coordinate serialization) | `15.16875 / 8.025 mm` nominal |

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

The Choc socket and ES1B SMD solder-fillet models each include a 0.30 mm
lateral allowance. The routed ES1B boards pass the current digital diode gates:
the minima across both halves are 1.605 mm to unused switch NPTH, 1.000 mm to
switch pads and unrelated exposed copper, 1.725 mm to socket bodies, 0.400 mm
between diode and switch-assembly fillet envelopes, 0.213 mm to an unrelated
route, and 1.475 mm from the diode fillet envelope to Edge.Cuts. Every diode
pad has an unobstructed 1.50 mm cardinal solder-tool approach. These PCB
measurements supersede the old SOD-123 D2 values. Regenerated ES1B housing
evidence reports 0.3279 mm minimum cutout XY clearance overall, 0.3282 mm for
ES1B, and 1.0250 mm minimum diode perimeter land on both halves. The compact
controller revision extends the common desk datum to Z=-1.00 mm, providing
1.00 mm nominal diode-to-desk clearance while the provisional 3.00 mm battery
envelope retains 0.50 mm nominal desk clearance. This remains digital
evidence only; physical retention, deflection, and populated-coupon tests are
still required before ordering.

## M1.4 retention prototype

The PCB contains eight left and ten right `MH*` features using the owned
`MH_M1.4_NPTH_1.60` footprint. Each is an unnetted, copper-free `1.60 mm`
round NPTH. Each hole is visibly numbered `MH1..MH8` on the left and
`MH1..MH10` on the right using `0.80 mm` / `0.10 mm` front-silkscreen text.
Service is modeled with keycaps removed and either supported switch
type still installed. A final `3.00 mm` vertical PH0 driver envelope and a
`2.00 x 0.50 mm` head envelope clear the modeled Choc V2 and MX assemblies;
the driver envelope already includes the search reserve and must not be
buffered a second time.

The matching lower housing provides a `3.00 mm` zero-gap support land and desk
column at every hole, with a provisional `1.10 x 2.80 mm` blind pilot and a
`0.70 mm` closed bottom at the common Z=-1.00 mm desk datum. The original
14-left/11-right distributed supports
remain the primary typing-load path. The provisional 4.00 mm under-head screw
length, exact screw and driver, full-pattern registration, installation and
stripping torque, ten service cycles, keycap-skirt clearance, and 2.0 N
deflection must be proven on physical coupons. These digital files are not a
fastener purchase recommendation and remain not orderable.

## Battery service path

The direct battery wires do not use carrier-PCB power copper. The netless
3.6 x 2.2 mm NPTH lead slot is at the nice!nano USB/B+ end, matching the
official nice!nano v2 battery-pad location. Route insulated B+ and GND/B-
leads between socket rows, deburr the slot, add strain relief, and keep the
wire path outside the antenna keepout.

## Compact controller tab

The V2-only compact-controller layout keeps all 70 key centers and all 18
numbered mounting-hole centers fixed. Each U1 is at `Y=50.7500 mm`, and each
portrait reset switch is stacked beneath the socket-elevated USB end at
`Y=50.7500 mm`, offset `2.05 mm` toward the USB-facing board edge. The
battery reference is at `Y=53.0500 mm`, and the top Edge.Cuts centerline is
`Y=39.2500 mm`. The board height is therefore `122.50 mm`, 4.25 mm shorter
than the preceding prototype. The reset body retains `0.50 mm` nominal planar
clearance to the battery-lead slot; controller-to-reset Z clearance remains a
socketed-controller physical gate.

This is a V2-only supersession of the older antenna-side reset placement; the
no-carrier-power and direct battery-lead rules remain unchanged. Reset
courtyard/pad projection, actual USB shell/cable, keycap skirt, battery pouch,
lead strain relief, and actuation support still require a populated first
article. The digital package remains not orderable.

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
assembly risk required by `CON-ARCH-004` AC-9. Its CAD and fabrication package
do not satisfy the physical evidence gate by themselves. A populated coupon
must additionally verify ES1B polarity and solder access plus the pending 3.0 V
and 3.3 V zero-wait same-row/same-column matrix stress cases.

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
of zero violations and zero unconnected items. After producing both fresh DRC
JSON reports, regenerate the exact board/report evidence binding before running
the release verifier:

```powershell
& "C:\Program Files\KiCad\10.0\bin\python.exe" -B -m tools.generate_kc2_x3_v2_drc_evidence
& "C:\Program Files\KiCad\10.0\bin\python.exe" -B -m tools.verify_kc2_x3_v2
```

`kc2_x3_v2_drc_evidence.json` binds each current board and `.kicad_pro`
SHA-256 to its DRC report SHA-256, schema, source filename, KiCad version,
report date, included severity classes, and the project's `Default` netclass
clearance. The release verifier requires that clearance to remain at least
`0.30 mm`, a KiCad 10.x report, a valid ISO timestamp, and both `error` and
`warning` coverage; `exclusion` is the only optional additional severity. A
changed board, project, or report cannot pass against stale evidence.

When only the generated outline policy changes, use
`tools.repair_kc2_x3_v2_compact_edge --sync-edge-cuts-from <fresh-board>`.
The command rejects non-rigid switch geometry, replaces only Edge.Cuts, and is
covered by route/footprint-preservation and idempotence tests.

The current compact-controller, mounting-hole-aware trackless inputs are
`autoroute/kc2_left-x3-v2-70-es1b-controller-r3.dsn` and
`autoroute/kc2_right-x3-v2-70-es1b-controller-r3.dsn`; they contain exactly
eight and ten visibly numbered M1.4 NPTHs. Their reviewed r3 sessions bind the
moved controller/reset fanout and shortened outline. Against empty-track
generated boards, the finalizer imports those sessions and applies only the
exact, precondition-checked edge cleanup:

```powershell
& "C:\Program Files\KiCad\10.0\bin\python.exe" -B -m tools.finalize_kc2_x3_v2_routes `
  hardware/kicad/draft/x3-v2/kc2_left-x3-v2/kc2_left-x3-v2.kicad_pcb `
  --import-controller-compact-session hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-es1b-controller-r3.ses
& "C:\Program Files\KiCad\10.0\bin\python.exe" -B -m tools.finalize_kc2_x3_v2_routes `
  hardware/kicad/draft/x3-v2/kc2_right-x3-v2/kc2_right-x3-v2.kicad_pcb `
  --import-controller-compact-session hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.ses
```

The helper rejects wrong controller/reset/switch geometry, stale sessions, and
partial or unexpected nonempty routes. Both importers verify complete matrix connectivity,
reproduce the committed route exactly, and are covered by second-run
idempotence tests. The deterministic final track/via counts are 543 left and
706 right, with route digests
`9bc9cbf981da8d452b82e52d54a4e8ab3cafcc6121ec578f36a4cf43f3dde19d`
and `83dcc6f764670b379b6c9104d643925cd6eff3c0b16286f12bae14dd1397c67f`.
Running either command against its already exact committed board is a verified
no-op. The generation manifest binds each current controller-r3 DSN and
reviewed controller-r3 SES by SHA-256. It also verifies both
current DSN global/default clearance rules remain at least `300` internal units
(`0.30 mm` at the recorded DSN resolution).

The project explicitly ignores five KiCad diagnostic classes: missing
courtyard, track-not-centered-on-via, tuning-profile track geometry,
symbol/footprint-filter mismatch, and footprint component-type mismatch.
These are generated-board metadata, custom hybrid-footprint library, or
non-applicable tuning diagnostics. The
electrical implications remain covered by exact footprint geometry checks,
matrix-island connectivity checks, NPTH copper-free checks, Gerber/Excellon
inspection, and zero DRC violations/unconnected items.

The production release gate compares every placed ES1B pad, B.Fab body,
courtyard, and mirrored B.Silkscreen cathode mark against the KC2-owned
footprint. It also compares every hybrid-switch pad/NPTH and the side-specific
24-pad nice!nano socket against its owned footprint, requires the matching
front-silkscreen `USB_OUT_LEFT`/`USB_OUT_RIGHT` label, and hard-checks
`SW_RST1` pad 1=`RST`, pad 2=`GND`.

Official geometry references:

- Kailh Choc V2 switch: https://www.kailhswitch.com/mechanical-keyboard-switches/key-switches/kailh-low-profile-switch-choc-v2.html
- Kailh socket drawing: https://www.kailhswitch.com/uploads/15927/files/CPG135001S30.pdf?rnd=925
- Cherry MX2A 5-pin datasheet: https://www.cherry.de/fileadmin/media/Industrial/Switch/MX_BLACK/Data_sheet_MX2A_Black.pdf
- Jingdao ES1B / LCSC C437840 datasheet: https://www.lcsc.com/datasheet/C437840.pdf
- Eleparts goods 9475342: https://www.eleparts.co.kr/goods/view?no=9475342
- nice!nano v2 pinout and schematic: https://nicekeyboards.com/docs/nice-nano/pinout-schematic/
