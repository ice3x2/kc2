# KC2 X3 V2 canonical hardware

Requirements: `CON-ARCH-004`, `CON-ARCH-006`, `CON-ARCH-007`,
`REL-ARCH-001`, `OPS-ARCH-006`

Status: **DIGITAL PASS - ORDER READY: NO**. Exact V2 service geometry and nets
and fresh KiCad 10.0.3 DRC pass digitally. Ordering remains blocked by exact
301230 pack/protection/lead and `J_BAT1` drill selection, controller-stack fit,
solder/strain-relief/service tests, IMMS power-transition and BLE tests,
populated coupon/first articles, and housing/fastener/2.0 N deflection tests.

The active V2 source projects are the canonical
`hardware/kicad/kc2_left/` and `hardware/kicad/kc2_right/` projects. The
replaced X3 revision is retained through Git history; there is no duplicate
active V2 tree under `hardware/kicad/draft/`.

## Assembly modes

The two switch modes are mutually exclusive at every key position:

- Choc V2 / PG1353-class: install a Kailh `CPG135001S30`-class hot-swap socket
  on the PCB bottom. Do not directly solder the switch.
- Cherry MX-style 5-pin PCB-mount: install the switch from the PCB top and
  directly solder its two electrical pins. No MX hot-swap socket is supported.
- Choc V1 / PG1350, Choc V2 direct-solder, and MX hot-swap are unsupported.
- Never install both a Choc socket and an MX switch at one key position.

The intended switch remains the Kailh Deep Sea low-profile / PG1353 family,
but its exact manufacturer MPN and controlled drawing revision are still
pending. `Deep Sea`, `Deep Sea Whale`, a reseller nickname, or a family name
is not an orderable part identity. Do not order the switch until those two
fields are bound to the purchased part and its controlled drawing.

The owned hybrid footprint includes an explicit bottom courtyard from
`(-10.25,1.20)` to `(5.25,8.50)` mm. It encloses the complete bottom socket
body and both B.Cu lands with a `0.25 mm` manufacturing allowance.

The left and right boards use their physical split-keyboard orientations. The
bottom-side socket pattern must be read from the PCB bottom; the 1:1 bottom PDF
is already mirrored for a physical bottom view.

## Matrix diode and polarity

The active V2 BOM contains exactly 70 Diodes Incorporated `1N4148W-13-F`
matrix diodes in flat SOD-123 packages, controlled by `DS30086 Rev. 31-2`.
All are assembled on `B.Cu`. Pin/pad 1 is the cathode connected to the row net; pin/pad
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

The Choc socket and 1N4148W SOD-123 solder-fillet models each include a 0.30 mm
lateral allowance. The routed boards pass the current digital diode gates:
the minima across both halves are 1.946 mm to unused switch NPTH, 1.125 mm to
switch pads and unrelated exposed copper, 2.225 mm to socket bodies, 0.525 mm
between diode and switch-assembly fillet envelopes, and 1.975 mm from the
diode fillet envelope to Edge.Cuts. The diode-to-unrelated-route minima are
0.737 mm left and 0.545 mm right, both above the 0.10 mm gate. Every diode
pad has an unobstructed cardinal solder-tool approach. The enlarged KC2 hand-
solder land is deliberately not the manufacturer's recommended land: implemented
pads are 1.40 x 1.55 mm at 3.60 mm centers, while the official suggested pads
are 0.90 x 0.95 mm at 4.05 mm centers. Regenerated housing evidence provides
0.35 mm cutout XY clearance, 1.525 mm minimum diode perimeter land, and 1.85 mm
nominal / 1.55 mm post-tolerance diode-to-desk clearance. The Choc socket is the
overall open-component limiter at 1.10 mm nominal / 0.80 mm post-tolerance.
This remains digital
evidence only; physical retention, deflection, and populated-coupon tests are
still required before ordering.

## M1.4 retention prototype

The PCB contains eight left and nine right `MH*` features using the owned
`MH_M1.4_NPTH_1.60` footprint. Each is an unnetted, copper-free `1.60 mm`
round NPTH. Each hole is visibly numbered `MH1..MH8` on the left and
`MH1..MH9` on the right using `0.80 mm` / `0.15 mm` front-silkscreen text.
Service is modeled with keycaps removed and either supported switch
type still installed. A final `3.00 mm` vertical PH0 driver envelope and a
provisional non-countersunk rounded pan/button head envelope of maximum
`3.00 x 1.20 mm` clear the modeled Choc V2 and MX assemblies with a separate
`0.25 mm` XY reserve. The driver envelope already includes its search reserve
and must not be buffered a second time.

The matching lower housing provides a `3.00 mm` zero-gap support land and desk
column at every hole, with a provisional `1.10 x 2.80 mm` blind pilot and a
`0.70 mm` closed bottom at the common Z=-1.00 mm desk datum. A separate exact
one-to-one network of 31-left/39-right `2.40 mm` key-load feet provides every
switch center with a local desk load path whose worst center-to-support-edge
distance is `4.3902 mm`, within the `4.40 mm` SOD-123/P3 bound; mounting columns are not credited as typing-load
supports. The provisional 4.00 mm under-head screw
length, exact screw and driver, full-pattern registration, installation and
stripping torque, ten service cycles, keycap-skirt clearance, and 2.0 N
deflection must be proven on physical coupons. These digital files are not a
fastener purchase recommendation and remain not orderable.

## Battery service path

Each half uses one nominal `30.00 x 12.00 x 3.00 mm`, 3.7 V, 100 mAh
301230-class pack above the carrier PCB and below the socketed nice!nano. The
battery centers are left `(131.7125, 50.7500)` and right
`(78.4000, 50.7500)` mm, with the 30 mm axis parallel to the U1 socket rows.
The exact manufacturer/MPN, single-cell protection status, maximum swollen
thickness, lead-exit drawing, and pull limit remain procurement gates.

Only the pack's pre-attached insulated leads are soldered to `J_BAT1`; do not
solder a bare pouch tab and do not add an A2501, JST, or other detachable
battery connector. `J_BAT1` is left `(115.8125, 59.4000)` R180 and right
`(94.3000, 59.4000)` R0. Its visible assembly marks identify pad 1 `B+` and
pad 2 `B-/GND`; the electrical pad nets remain `BAT+` and `GND`, respectively.
The [official nice!nano documentation](https://nicekeyboards.com/docs/nice-nano/)
identifies the carrier's `RAW` and `GND` pins as the battery-positive and
battery-negative connections, so no extra net tie is required.
`BAT_LEAD_SLOT1` remains an unnetted, copper-free
strain-relief feature identified by the exact board text
`BAT STRAIN RELIEF`, at left `(117.9125, 50.7500)` and right
`(92.2000, 50.7500)` mm; it is not a lower battery exit.

The electrical path is
`J_BAT1 BAT+ -> SW_PWR1 pad 1 common -> pad 2 ON -> NN_B+ -> U1 RAW`. Pad 3 is
NC. J_BAT1 B-/GND remains directly connected to
local GND and U1 GND. Keep BAT+ and its GND return paired in the USB-side
corridor and outside the antenna keepout. The lower housing has no TW301525 or
301230 battery-body cavity; it provides only the required U1, J_BAT1,
strain-relief, IMMS lead, and solder-fillet openings.

## Compact controller tab

The V2-only compact-controller layout keeps all 70 key centers and all 17
numbered mounting-hole centers fixed. U1 centers are left
`(132.7125, 50.7500)` and right `(77.4000, 50.7500)` mm. The top Edge.Cuts
centerline is `Y=39.2500 mm`, and the nominal board height is `122.50 mm`.

POWER and RESET occupy the controller-key gap. `SW_PWR1` is left
`(115.8125, 63.4500)` R0 and right `(94.3000, 63.4500)` R180. `SW_RST1` is
left `(126.0625, 63.4500)` R0 and right `(84.0500, 63.4500)` R180, with pad
1=RST on the POWER/USB-facing side and pad 2=GND on the keyboard-center side.
Top-view absolute order is left `PWR|RST` and right `RST|PWR`; from each
USB-facing outer edge toward the antenna, the service order is POWER then
RESET. The centers are 10.25 mm apart, giving 2.20 mm nominal controlled-body
clearance, 3.20 mm reset-body clearance to the nearest keycap envelope, and
at least 2.03 mm reset-courtyard clearance to U1 socket copper.

Each placed `SW_PWR1` retains the owned STEP model. That STEP is a nominal
collision proxy only: the exact purchased manufacturer/MPN and controlled
drawing are pending, and `IMMS-12V` / `BSI-10` equivalence is not assumed.

This V2 contract supersedes the historical X3 no-carrier-power,
USB-under-reset, and antenna-side-reset instructions only for `kc2-x3-v2`.
The exact pack stack, USB shell/cable, POWER/RESET access, controller removal,
lead strain relief, keycap clearance, and actuation support still require
physical first-article evidence. The digital package remains not orderable.

## Outputs

- Routed boards: `kc2_left/` and `kc2_right/`
- Physical fit coupon CAD: `coupon/`
- Canonical Gerber/Excellon packages: `fabrication/`
- JLCPCB upload-preview archives: `fabrication/kc2_left_jlcpcb.zip`,
  `fabrication/kc2_right_jlcpcb.zip`, and
  `fabrication/kc2_coupon_jlcpcb.zip`
- 1:1 top/bottom assembly PDFs: `mechanical/`
- KiCad 3D inspection renders: `renders/`
- Housing clearance evidence: `../case/`

The fabrication, mechanical, and housing derivatives were regenerated from
the current left/right board hashes
`3a6f80a5bc1afe897056107be9522a26079766fd4963f2115a9237737470268d` and
`a4361040d81b3189cce8cdfcedaf54e570248d2fd513835dfadf80bcc187ef6d`.
Their dedicated V2 verifiers pass. The joined SVG/PNG set was regenerated from
the same current boards and reports 1.1000 mm minimum Edge.Cuts clearance and
1.8000 mm cross-seam keycap gap. All outputs remain digital evidence and
do not change **ORDER READY: NO**.

The JLCPCB upload-preview archives contain exactly 15 root-level manufacturing
files each: copper, mask, paste, silkscreen, Edge.Cuts, plated/non-plated drill,
drill maps/report, and the Gerber job. They intentionally exclude the BOM JSON
and CSV carried by the broader traceability archives. The machine-readable
profile in `fabrication/kc2_fabrication_manifest.json` records 2-layer
FR-4, 1.6 mm, 1 oz, ENIG, green solder mask, white silkscreen, hand assembly,
and both-side tented vias with a 0.50 mm maximum tented drill. The verifier
checks the source-board tenting settings and confirms that neither mask Gerber
opens at any via center. JLCPCB production-file confirmation must be enabled
and the engineer-generated production Gerbers must be downloaded and reviewed
before approval. These are prototype upload previews only while the physical
coupon, housing/fastener, controller-service, and power/RF evidence remains
pending.

The coupon contains conservative representative 0-degree and 180-degree
bottom socket orientations plus a 5-pin MX direct-solder sample at 19.05 mm
pitch. The 180-degree sample deliberately exercises the rotated/mirrored
assembly risk required by `CON-ARCH-004` AC-9. Its CAD and fabrication package
do not satisfy the physical evidence gate by themselves. A populated coupon
must additionally verify 1N4148W polarity and solder access plus the pending 3.0 V
and 3.3 V zero-wait same-row/same-column matrix stress cases.

## Reproduction and verification

Run PCB tools with KiCad 10 Python:

Run these commands from the repository root. The housing verifier additionally
requires the documented CadQuery environment. The exact executable release
gates for the active V2 target are `tools.verify_kc2_x3_v2` and the dedicated
V2 fabrication, mechanical, outline, coupon, firmware, and housing verifiers
below. Apply the `kc2-pcb-preflight` component-by-component and
circuit-by-circuit review workflow as an additional audit. Its bundled CLI
supports the historical `--variant x3` path only; an `ORDER READY` result from
that historical X3 run is not evidence for `kc2-x3-v2`.

`tools.verify_kc2_x3_v2` exits `0` only when every digital and physical gate
passes, `1` on a digital error, and `2` when digital checks pass but required
physical evidence is still pending. The current expected result is exit `2`.

```powershell
$kpy = 'C:\Program Files\KiCad\10.0\bin\python.exe'
& $kpy -m tools.generate_kc2_pcbs --variant x3-v2 --output-dir tmp_x3_v2_clean
& $kpy -m tools.render_kc2_x3_joined --variant x3-v2 --placement-mode key-pitch --scale 5 --output-dir hardware/kicad/renders
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
& "C:\Program Files\KiCad\10.0\bin\python.exe" -B -m tools.generate_kc2_drc_evidence
& "C:\Program Files\KiCad\10.0\bin\python.exe" -B -m tools.verify_kc2_x3_v2
```

`kc2_drc_evidence.json` binds each current board and `.kicad_pro`
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
`autoroute/kc2_left.dsn` and
`autoroute/kc2_right.dsn`; they contain exactly
eight and nine visibly numbered M1.4 NPTHs. Their reviewed canonical SES files bind the
moved controller/reset fanout and shortened outline. Against empty-track
generated boards, the finalizer imports those sessions and applies only the
exact, precondition-checked edge cleanup:

```powershell
& "C:\Program Files\KiCad\10.0\bin\python.exe" -B -m tools.finalize_kc2_x3_v2_routes `
  hardware/kicad/kc2_left/kc2_left.kicad_pcb `
  --import-controller-compact-session hardware/kicad/autoroute/kc2_left.ses
& "C:\Program Files\KiCad\10.0\bin\python.exe" -B -m tools.finalize_kc2_x3_v2_routes `
  hardware/kicad/kc2_right/kc2_right.kicad_pcb `
  --import-controller-compact-session hardware/kicad/autoroute/kc2_right.ses
```

The helper rejects wrong controller/reset/switch geometry, stale sessions, and
partial or unexpected nonempty routes. Both importers verify complete matrix connectivity,
reproduce the committed route exactly, and are covered by second-run
idempotence tests. The retained deterministic route reconstruction has final track/via counts of
616 left and 803 right, with route digests
`b37c88d783baa27e6358d1c3baf33528d282934c41c507f2da5edc44e739ebbb`
and `44a0c7fdd446f3153d2faf2506194947577b74147713c9a097c7ac83a9c1a964`.
Running either command against its already exact committed board is a verified
no-op. The generation manifest binds each current canonical DSN and reviewed
canonical SES by SHA-256. It also verifies both
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

The production release gate compares every placed 1N4148W pad, B.Fab body,
courtyard, and mirrored B.Silkscreen cathode mark against the KC2-owned
footprint. It also compares every hybrid-switch pad/NPTH and the side-specific
24-pad nice!nano socket against its owned footprint, requires the matching
front-silkscreen `USB_OUT_LEFT`/`USB_OUT_RIGHT` label, and hard-checks
`SW_RST1` pad 1=`RST`, pad 2=`GND`.

Official geometry references:

- Kailh Choc V2 switch: https://www.kailhswitch.com/mechanical-keyboard-switches/key-switches/kailh-low-profile-switch-choc-v2.html
- Kailh socket drawing: https://www.kailhswitch.com/uploads/15927/files/CPG135001S30.pdf?rnd=925
- Cherry MX2A 5-pin datasheet: https://www.cherry.de/fileadmin/media/Industrial/Switch/MX_BLACK/Data_sheet_MX2A_Black.pdf
- Diodes Incorporated 1N4148W product page: https://www.diodes.com/part/view/1N4148W/
- Diodes Incorporated DS30086 Rev. 31-2 datasheet: https://www.diodes.com/datasheet/download/1N4148W.pdf
- nice!nano v2 pinout and schematic: https://nicekeyboards.com/docs/nice-nano/pinout-schematic/

## Component and terminal audit

The 2026-08-31 procurement audit compares the placed footprints with the
published part drawings rather than relying only on KiCad DRC. `PASS` below
means the nominal PCB land pattern matches the cited drawing; it does not
replace incoming inspection or the physical evidence gates.

| Placed item | Published body / terminal contract | Actual KC2 footprint | Result |
|---|---|---|---|
| nice!nano v2 `U1` | Published plan `34.1 x 18.3 mm`; official total thickness `3.2 mm` and official Pro Micro pinout. B+ and B- are not socketed; `RAW` and `GND` are their respective carrier equivalents. | Conservative collision envelope `34.1 x 18.3 mm`; 2 x 12 PTH, `2.54 mm` longitudinal pitch, `15.24 mm` row spacing, pad `1.80 mm`, drill `0.95 mm`; `RAW=NN_B+`, `GND_C=GND`, `RST=RST`. | Plan/pinout PASS; exact female socket and pin-leg MPN/tail height PENDING. |
| Kailh Choc V2 socket | Kailh `CPG135001S30`, drawing `KH-PS-1702-35` Rev D; T=1.6 recommended pattern with `2.60 mm` contacts and specified NPTH locations. | Bottom socket body `9.55 x 6.80 mm`, B.Cu pads `2.60 mm`, exact official mechanical holes; duplicate pads 1 and 2 share the MX electrical nets. | Socket PASS; exact mating Kailh switch MPN/drawing PENDING. |
| Cherry MX alternative | Official MX2A 5-pin PCB-fixation variants; nominal `15 x 15 mm` body and two electrical plus three fixation terminals. | F.Fab `15 x 15 mm`; electrical pads `2.50 mm` with `1.50 mm` drill plus `5.00/3.00/1.65 mm` fixation NPTHs. | Nominal 5-pin geometry PASS; exact optional MX MPN PENDING. |
| `1N4148W-13-F` diode | Diodes Incorporated SOD-123, body max `2.85 x 1.70 x 1.35 mm`, terminal span max `3.85 mm`; suggested pads `0.90 x 0.95 mm` at `4.05 mm` centers; pin 1 cathode, pin 2 anode. | B.Fab `2.85 x 1.70 mm`; controlled hand-solder pads `1.40 x 1.55 mm` at `3.60 mm` centers, classified as a KC2 enlargement rather than the manufacturer land; pad 1 row/cathode, pad 2 per-key/anode. | Digital geometry/polarity PASS; populated solder/scan coupon PENDING. |
| `SW_PWR1` | SM Switch `BSI-10`: `10 x 2.5 x 6.4 mm`, `1.6 mm` travel, three `0.6 mm` pins on `2.54 mm` pitch, recommended `0.8 mm` drills; terminal 1 common. | F.Fab `10 x 2.5 mm`, three `1.60 mm` pads / `0.80 mm` drills at `2.54 mm`; pad 1 `BAT+`, pad 2 `NN_B+`, pad 3 NC. | Geometry/net PASS; exact purchased MPN/drawing and former IMMS equivalence PENDING. |
| `SW_RST1` | DeviceMart `NW3-A06-B3`, nominal body `6.1 x 3.7 mm`. | Controlled body `6.1 x 3.7 mm` inside an `8.0 x 3.7 mm` lead-span drawing; SMD pads `1.75 x 1.00 mm`; pad 1 RST, pad 2 GND. | Nominal PASS; purchased-lot drawing/actuation test PENDING. |
| `BAT1` / `J_BAT1` | Nice Keyboards recommends a rechargeable 3.7 V 301230 cell; exact protected-pack maximum, swelling and lead drawing are supplier-specific. | Nominal body `30 x 12 x 3 mm`; direct-lead pads `2.20 x 1.80 mm`, drill `0.90 mm`, pitch `2.54 mm`; pad 1 BAT+, pad 2 GND/B-. | Nominal only; exact protected pack, lead diameter and maximum envelope BLOCK ORDER. |
| `MH*` | Provisional M1.4 non-countersunk rounded head up to `3.00 x 1.20 mm`. | Copper-free unnetted `1.60 mm` NPTH with housing pilot `1.10 x 2.80 mm`. | Digital clearance PASS; exact screw/driver MPN and physical torque/deflection PENDING. |

Dimension and terminal sources additionally used by this audit:

- nice!nano mounting/battery guidance: https://nicekeyboards.com/docs/nice-nano/
- nice!nano installation and B+/B-/RAW/GND guidance: https://nicekeyboards.com/docs/nice-nano/getting-started/
- nice!nano published reseller dimensions: https://mechboards.co.uk/products/nice-nano-v2
- SM Switch BSI-10 drawing: https://pf02.ickimg.com/datasheet/upload/2023/10/07/BSI-10.pdf
- DeviceMart NW3-A06-B3 dimensions: https://www.devicemart.co.kr/goods/view?no=1322056
- Diodes Incorporated 1N4148W: https://www.diodes.com/part/view/1N4148W/
