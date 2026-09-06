# KC2 X3 V2 canonical hardware

> Current PCB-only release: **solid-floor-20260907-r4**, with independently checked continuous lower floors and current native CAD.
> Physical qualification remains pending; no order or payment was performed. Prior r3/r2 packages are historical.
> Exact directory, PCB ZIP, STL, silicone-foot and assembly guide: [root order.md](../../order.md).
> Use [current release instructions and residual-risk conditions](first_order/README.md).

Requirements: `CON-ARCH-004`, `CON-ARCH-006`, `CON-ARCH-007`,
`REL-ARCH-001`, `OPS-ARCH-006`, `OPS-ARCH-007`

Status: **R4 DIGITAL DESIGN/OUTPUTS VERIFIED; PHYSICAL QUALIFICATION PENDING**.
Follow the [first-order files and Korean instructions](first_order/README.md).
The promoted PCB retains the V1 locator clearances and r3 routing. Unchanged r3 Gerber
and fullboard/zoom evidence is combined with newly verified r4 closed-floor CAD/native evidence. OPS-ARCH-007 separates
pre-order design review from post-receipt acceptance; no prerequisite sample is
required. This is PCB-only preparation, not complete assembly compatibility.
Socket contact tolerances and the high-risk keycap/top-screw-head interface are
explicitly unproven; read the guide before spending money. Historical
`fabrication/` ZIPs remain **DO NOT ORDER**. Later physical-gate wording in this
document is interpreted under OPS-ARCH-007, not as a prerequisite sample demand.

The active V2 source projects are the canonical
`hardware/kicad/kc2_left/` and `hardware/kicad/kc2_right/` projects. The
replaced X3 revision is retained through Git history; there is no duplicate
active V2 tree under `hardware/kicad/draft/`.

## Assembly modes

The selected assembly is `mx_receptacle_with_plate`. Four switch modes are
mutually exclusive at all 70 positions (31 left / 39 right):

- Selected MX: solder two individual open-bottom hat-style receptacles per key
  (62 left / 78 right, 140 total). The selected TTC Bluish White 3-pin switch
  requires the 3D-printed MX plate-lid for retention. Existing 5-pin MX locator
  support remains; the selected 3-pin switch leaves those holes unoccupied.
- MX direct-solder fallback: leave receptacles unpopulated and solder the two
  electrical switch pins directly. Qualify this fallback separately.
- Choc V2 / PG1353-class alternative: install the bottom-side Kailh
  `CPG135001S30` socket; do not directly solder the Choc switch. This is not the
  selected assembly and must not be populated together with MX receptacles.
- Choc V1 / PG1350 alternative: use the bottom Choc socket and V1 center ring
  adapter, with the new copper-free PCB locator clearances. No cutting the switch
  or hand-drilling the PCB is required by this design. Full assembly qualification
  remains pending; the ring alone did not make the historical r2 PCB V1-compatible.
- Choc V2 direct-solder and one-piece MX SMD sockets remain unsupported.
  Never populate multiple switch assemblies at one position.

The socket contract is dimensional, not a required brand/MPN: total length
`3.00 mm`, barrel OD `1.45 mm`, flange OD `2.00 mm`, flange thickness `0.20 mm`,
and an open bottom. A flush flange on a nominal `1.60 mm` PCB projects `1.20 mm`
below it before solder and switch-pin protrusion. Closed-bottom `4.00 mm` and
hatless `3.50 mm` parts are not equivalent substitutes. See the
[selected seller drawing](https://ae-pic-a1.aliexpress-media.com/kf/S4b47dab427cd4b539a50618bf16a62d9J.jpg).
OD tolerances and flat-blade contact limits are unpublished and remain pending;
a Mill-Max compatibility claim is not qualification evidence.

MX electrical lands are `2.50 x 3.20 mm` ovals in footprint-local Y with a
**trial `1.60 mm` PTH**, not a qualified production finished-hole fit. Both
mask layers expose the full land at explicit nominal zero expansion, without
paste apertures. Center/locator NPTHs remain copper-free. The exact purchased
MX switch drawing, flange relief, blade engagement and replacement/contact
tests remain required. The selected low-profile Choc V2 alternative is the user's
Kailh Deep Sea brown seller option; its exact manufacturer MPN/drawing linkage is
still pending. A marketing family name alone does not qualify the dimensional fit.
See the [exact selected-component source review](../../docs/reports/kc2-selected-component-source-closure-2026-09-06.md).

The owned hybrid footprint includes an explicit bottom courtyard from
`(-10.25,1.20)` to `(5.25,8.50)` mm. It encloses the complete bottom socket
body and both B.Cu lands with a `0.25 mm` manufacturing allowance.

The left and right boards use their physical split-keyboard orientations. The
bottom-side socket pattern must be read from the PCB bottom. The historical 1:1
bottom PDF is already mirrored for a physical bottom view, but is an orientation
reference only, not evidence of the current MX geometry.

## Matrix diode and polarity

The PCBs require exactly 70 Diodes Incorporated `1N4148W-13-F`
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
The retained diode-plus-Choc BOM/CPL is an unselected, mutually exclusive
hand-assembly reference, not an MX receptacle BOM or an authorized placement
order. Selected MX procurement documentation must bind the dimensional socket
contract, supplier trace and plate dependency; qualification remains open.

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

Do not trim removable switch blades in the selected receptacle assembly.
Any trimming applies only to separately qualified direct-solder fallback joints.
The 2.50 mm lower plate has exterior-bottom-open cutouts through the full plate
height for every MX terminal and solder joint, rather than a closed component
cavity. The lateral solder-fillet model includes a 0.30 mm allowance.

The Choc socket and 1N4148W SOD-123 solder-fillet models each include a 0.30 mm
lateral allowance. Current digital diode checks enforce at least `1.00 mm`
to switch copper/unused NPTH/unrelated exposed copper, `1.30 mm` to Edge.Cuts,
and the separate `0.10 mm` conservative fillet-to-route gate. Do not reuse
pre-revision route minima as revised evidence. Every diode
pad has an unobstructed cardinal solder-tool approach. The enlarged KC2 hand-
solder land is deliberately not the manufacturer's recommended land: implemented
pads are 1.40 x 1.55 mm at 3.60 mm centers, while the official suggested pads
are 0.90 x 0.95 mm at 4.05 mm centers. The revised lower housing models
`0.35 mm` component cutout XY clearance and `0.30 mm` support-to-routed-copper
wear reserve. See `../case/kc2_housing_clearance.json` for the bound current
geometry. Socket/flange/solder/full-blade protrusion, physical retention,
deflection and populated-coupon fit remain qualification gates.

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
distance is `3.8990 mm`, within the `4.40 mm` bound; mounting columns are not
credited as typing-load supports. The enlarged-pad routing maintains the
required `0.30 mm` support-to-B.Cu/via copper clearance.

The selected stack is lower housing, PCB, then the plate-integrated MX lid,
clamped by long top-entry screws through the same 17 PCB holes. The former
`4.00 mm` lower-only screw length is not a selected-stack recommendation.
The revised upper design retains provisional `14.0 mm` apertures, `1.5 mm` clip
thickness and `5.2 mm` plate-top height above PCB top. It recesses the screw head
in a `3.4 mm` diameter / `1.5 mm` deep pocket, backed by a `4.6 mm` upper collar
while retaining the `3.0 mm` PCB landing. The nominal maximum `1.2 mm` head sits
`0.3 mm` below the plate top. This removes modeled head protrusion, not unknown
keycap underside or printed-strength qualification. The new nominal under-head-
to-receiver entry distance is `5.3 mm`, replacing the historical `6.8 mm`;
the qualified screw length is still unset. Revised CAD/native export is under
regeneration and must pass before release. Exact
screw/driver, receiver engagement, print material/tolerance, registration,
installation/stripping torque, ten service cycles, full keycap travel, split-joint
retention and 2.0 N deflection require physical evidence. Digital clearance and
the existing `1.10 x 2.80 mm` pilot do not qualify the new long-screw receiver.

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
`1.73 mm` nominal reset-courtyard clearance to the enlarged U1 socket copper.

All 24 U1 lands per half are `1.80 x 2.40 mm` ovals, elongated perpendicular to
the `2.54 mm` pin-row direction, with unchanged `0.95 mm` drills and `15.24 mm`
row spacing. Both mask layers expose the whole land at nominal zero expansion;
there are no paste apertures. The nominal battery-to-socket-copper gap is now
`0.42 mm`, not the former circular-pad `0.72 mm`. Actual solder wetting, bridge
avoidance and battery/controller-stack fit remain unverified physically.

Each placed `SW_PWR1` retains the owned STEP model. That STEP is a nominal
collision proxy only: the exact purchased manufacturer/MPN and controlled
drawing are pending, and `IMMS-12V` / `BSI-10` equivalence is not assumed.

This V2 contract supersedes the historical X3 no-carrier-power,
USB-under-reset, and antenna-side-reset instructions only for `kc2-x3-v2`.
The exact pack stack, USB shell/cable, POWER/RESET access, controller removal,
lead strain relief, keycap clearance, and actuation support still require
physical first-article evidence. The digital package remains not orderable.

## Outputs

- Current routed source boards: `kc2_left/` and `kc2_right/`; current DRC bindings
  are in `kc2_drc_evidence.json`.
- Current route replay: `autoroute/kc2_mx_solder_support_routes.json`.
- Raw revised Gerber/drill review files: `fabrication_review/mx-receptacle-20260906/left/`
  and `right/`, 15 files per half; not an order-approved fabrication package.
- Historical coupon, BOM/quotes, fabrication, 1:1 PDFs and renders: `coupon/`,
  `fabrication/`, `mechanical/`, `renders/`. Their pre-revision evidence must
  not be treated as regenerated MX-receptacle evidence.
- Current lower/MX upper CAD and evidence: `../case/`, including four STEP files,
  six STL part meshes (one left/two right per housing type), and four
  real native F3D archives.

**DO NOT ORDER** `fabrication/kc2_left_jlcpcb.zip`,
`fabrication/kc2_right_jlcpcb.zip` or `fabrication/kc2_coupon_jlcpcb.zip` for
this revision. These retained direct-solder/lower-only packages do not contain
reviewed current enlarged lands, routing and selected assembly evidence.
The old `*-bom.csv/json` direct-solder references and `pcba_quote/` Choc socket
BOM/CPL are likewise excluded from selected 140-contact MX procurement. They
are not authorized placement files, even when their historical package checks pass.

The raw revised files passed bounded actual-board geometry/drill checks,
including the 17 mounting holes and battery legends. See
[the Gerber inspection report](../../docs/reports/kc2-mx-gerber-inspection-2026-09-06.md).
Complete polygon-visual and physical qualification remain pending. Exporting
raw review files is not a fabrication release; no revised order-ready ZIP is
claimed here. Before release, inspect the exact revised copper, full front/back mask openings,
PTH/NPTH drills, plated-hole tolerances, polarity, mechanical fit and source/hash
bindings component by component. The intended board profile remains two-layer
FR-4, nominal 1.6 mm, 1 oz, ENIG, green mask, white silkscreen, hand assembly and
tented vias. The historical manufacturing manifest does not prove that profile
or via tenting in a new export. Any future JLCPCB engineer-generated production
files must also be downloaded and reviewed before approval.

The retained coupon has historical rotated/mirrored Choc and direct-solder MX
samples. It is not the required selected-assembly minimum three-key receptacle
coupon with production-material plate-lid. Finished-hole and blade seating,
socket retention/contact resistance after replacements, exact diode polarity,
solder-tool access and 3.0/3.3 V zero-wait scan tests remain physical gates.

The four F3D files were exported and reopened in real Fusion and independently
compared with the six STEP solids. See
[the native export report](../../docs/reports/kc2-fusion-native-export-2026-09-06.md)
and `../case/kc2_fusion_export_result.json`. They are native archives of imported
solids, not a reconstructed parametric feature history. Native delivery is
complete; printed clip fit, long-screw/receiver qualification and physical
assembly are not. The upper manifest still states `print_ready=false` and
`order_ready=false`.

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
passes, `1` on a digital error, and `2` when PCB checks pass but required
assembly/physical evidence is still pending. After native delivery, the current
expected result is exit `2` with nine qualification/physical blockers, not approval.

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

The retained `autoroute/kc2_left.dsn`, `kc2_right.dsn` and matching SES files
are historical pre-MX-revision inputs. They retain eight/nine M1.4 NPTHs and
0.30 mm routing rules but reconstruct the old 616-left/803-right routing, not
the selected enlarged-land boards. Their role in the generation manifest is
historical base provenance. Do not run the old SES finalizer against the current
canonical boards. Historical finalizer tests use immutable Git fixtures and
verify exact routes, service-pad/matrix connectivity, mounting geometry and
second-run idempotence without claiming current reconstruction.

Current V1-inclusive routing contains 876 left / 1089 right track/via items, with
digests `ccc6190a8f46e251261c6ef981fda11bd6524fc547ca358be1cde63a10ad2da3`
and `aa78af58190800870654a15ce6f772aea41a806705bb645597ed93b9ef0ac533`.
The schema-2 replay at `autoroute/kc2_mx_solder_support_routes.json` binds exact
pad centers, nets, shape/drill dimensions and local/effective mask margins.
`tools.kc2_solder_route_snapshot.restore` refuses a mismatched board before
changing routes. The fresh-generator regression generates only into a unique
temporary directory, applies this replay and verifies both reconstructed boards
with fresh DRC:

```powershell
& $kpy -B -m unittest tools.test_kc2_generator_route_replay
```

This test passed for both halves. Do not bypass the pad fingerprint or label the
historical DSN/SES import as the current route source.

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

This table updates the historical procurement audit for the selected 2026-09-06
assembly. Nominal geometry/pinout checks do not qualify unspecified tolerances,
purchased parts, enlarged hand-solder lands or physical assembly. No `PASS`
entry below is procurement or fabrication approval.

| Placed item | Published body / terminal contract | Actual KC2 footprint | Result |
|---|---|---|---|
| nice!nano v2 `U1` | Published plan `34.1 x 18.3 mm`; official total thickness `3.2 mm` and official Pro Micro pinout. B+ and B- are not socketed; `RAW` and `GND` are their respective carrier equivalents. | Conservative collision envelope `34.1 x 18.3 mm`; 2 x 12 PTH, `2.54 mm` longitudinal pitch, `15.24 mm` row spacing; enlarged `1.80 x 2.40 mm` oval lands, `0.95 mm` drill, full F/B mask openings; `RAW=NN_B+`, `GND_C=GND`, `RST=RST`. | Nominal plan/pinout checked; exact female socket, pin tails, wetting and stack fit PENDING. |
| Kailh Choc V2 socket | Kailh `CPG135001S30`, drawing `KH-PS-1702-35` Rev D; T=1.6 recommended pattern with `2.60 mm` contacts and specified NPTH locations. | Bottom socket body `9.55 x 6.80 mm`, B.Cu pads `2.60 mm`, exact official mechanical holes; duplicate pads 1 and 2 share the MX electrical nets. | Socket PASS; exact mating Kailh switch MPN/drawing PENDING. |
| Selected MX receptacles / direct-solder fallback | Two open-bottom hat contacts per key: length `3.00 mm`, barrel OD `1.45 mm`, flange `2.00 x 0.20 mm`; exact purchased MX drawing/contact tolerances pending. | F.Fab `15 x 15 mm`; electrical lands `2.50 x 3.20 mm` oval, trial `1.60 mm` PTH, full F/B mask openings, existing copper-free `5.00/3.00/1.65 mm` hybrid fixation features. Printed MX plate-lid required for receptacles. | 140 contacts modeled; finished-hole/barrel fit, blade engagement, flange relief, replacement/retention tests PENDING. |
| `1N4148W-13-F` diode | Diodes Incorporated SOD-123, body max `2.85 x 1.70 x 1.35 mm`, terminal span max `3.85 mm`; suggested pads `0.90 x 0.95 mm` at `4.05 mm` centers; pin 1 cathode, pin 2 anode. | B.Fab `2.85 x 1.70 mm`; controlled hand-solder pads `1.40 x 1.55 mm` at `3.60 mm` centers, classified as a KC2 enlargement rather than the manufacturer land; pad 1 row/cathode, pad 2 per-key/anode. | Digital geometry/polarity PASS; populated solder/scan coupon PENDING. |
| `SW_PWR1` | SM Switch `BSI-10`: `10 x 2.5 x 6.4 mm`, `1.6 mm` travel, three `0.6 mm` pins on `2.54 mm` pitch, recommended `0.8 mm` drills; terminal 1 common. | F.Fab `10 x 2.5 mm`, three `1.60 mm` pads / `0.80 mm` drills at `2.54 mm`; pad 1 `BAT+`, pad 2 `NN_B+`, pad 3 NC. | Geometry/net PASS; exact purchased MPN/drawing and former IMMS equivalence PENDING. |
| `SW_RST1` | DeviceMart `NW3-A06-B3`, nominal body `6.1 x 3.7 mm`. | Controlled body `6.1 x 3.7 mm` inside an `8.0 x 3.7 mm` lead-span drawing; SMD pads `1.75 x 1.00 mm`; pad 1 RST, pad 2 GND. | Nominal PASS; purchased-lot drawing/actuation test PENDING. |
| `BAT1` / `J_BAT1` | Nice Keyboards recommends a rechargeable 3.7 V 301230 cell; exact protected-pack maximum, swelling and lead drawing are supplier-specific. | Nominal body `30 x 12 x 3 mm`; direct-lead pads `2.20 x 1.80 mm`, drill `0.90 mm`, pitch `2.54 mm`; pad 1 BAT+, pad 2 GND/B-. | Nominal only; exact protected pack, lead diameter and maximum envelope BLOCK ORDER. |
| `MH*` / long-screw stack | Provisional M1.4 non-countersunk rounded head up to `3.00 x 1.20 mm`; final long-screw length unset. | Copper-free unnetted `1.60 mm` NPTH with provisional lower pilot `1.10 x 2.80 mm`; upper lid, PCB and lower receiver share 17 centers. | Nominal geometry only; exact screw/driver, engagement, receiver torque and deflection PENDING. |

Dimension and terminal sources additionally used by this audit:

- nice!nano mounting/battery guidance: https://nicekeyboards.com/docs/nice-nano/
- nice!nano installation and B+/B-/RAW/GND guidance: https://nicekeyboards.com/docs/nice-nano/getting-started/
- nice!nano published reseller dimensions: https://mechboards.co.uk/products/nice-nano-v2
- SM Switch BSI-10 drawing: https://pf02.ickimg.com/datasheet/upload/2023/10/07/BSI-10.pdf
- DeviceMart NW3-A06-B3 dimensions: https://www.devicemart.co.kr/goods/view?no=1322056
- Diodes Incorporated 1N4148W: https://www.diodes.com/part/view/1N4148W/
