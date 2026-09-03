# KC2 X3 V2 canonical lower support plate

Requirements: `CON-ARCH-006`, `CON-ARCH-007`, `REL-ARCH-001`, and
`OPS-ARCH-006`.

These files are generated only from the current 31-key left and 39-key right
canonical V2 KiCad boards. They supersede the former 77-key housing and do not
reuse any REG/H registration pattern.

## Construction and load path

- The lower housing is a nominal `2.50 mm` constant-Z support plate from
  exterior bottom `Z=0.00 mm` to PCB support plane `Z=2.50 mm`.
- There is no raised key-field bezel. The housing outline is inset `0.10 mm`
  from the PCB outline, preserving the keycap-concealed edge requirement.
- Clearance-cut perimeter regions and dedicated `2.40 mm` key-load support datum
  regions terminate at exactly Z `2.50 mm`, so the PCB has zero nominal
  vertical support gap without screw preload.
- The generated support set contains exactly one local support for every
  switch: 31 left and 39 right. Each support records its `SW*` source reference,
  and the measured worst switch-center-to-support-edge distance is `4.3902 mm`
  on both halves. Mounting columns are not credited as typing-load supports.
- A `2.40 mm` diameter foot continues downward from every key-load support
  datum to desk datum Z `-1.00 mm`. The eight left and nine right mounting
  points add coaxial `3.00 mm` desk-contact columns. A separate `3.00 mm`
  column also backs the exact top-side `SW_RST1` actuator at zero gap. The
  left part therefore has 40 coplanar desk contacts; right parts A/B have
  25 and 24 respectively. Each set is
  non-collinear and its contact hull contains
  the projected plate centroid, so every printable part has an independent
  no-rocking digital support proof. Feet remain inside the housing silhouette
  and have zero intersections with exterior-open component cutouts.
- There are no legacy REG/H pegs or separate fastener bosses. The exact
  `MH1..MH8` left and `MH1..MH9` right M1.4 pattern adds `3.00 mm` zero-gap
  annular support lands at Z `2.50 mm`, aligned `3.00 mm` columns to Z
  `-1.00 mm`, and provisional `1.10 mm x 2.80 mm` blind pilots. Each pilot
  ends at Z `-0.30 mm`, leaving a nominal `0.70 mm` closed column bottom.
  The provisional 4.00 mm under-head screw length yields `2.24..2.56 mm`
  penetration across the PCB thickness tolerance and at least `0.24 mm`
  nominal tip clearance. The exact screw MPN, printed pilot, torque, repeated
  service, and full-pattern registration remain physical gates.
- The exact P3 reinforcement board centers are left `MH1..MH8`: `(112.8625,43.0000)`,
  `(144.1125,66.2500)`, `(39.3625,111.0000)`, `(63.6125,123.0000)`,
  `(81.1125,151.7500)`, `(137.3625,153.5000)`, `(165.8625,148.7500)`,
  `(75.2500,134.0000)`; and right `MH1..MH9`: `(97.1875,43.2500)`, `(72.4375,67.0000)`,
  `(170.4375,95.2500)`, `(194.4375,98.7500)`, `(155.9375,112.5000)`,
  `(70.1875,146.7500)`, `(97.6875,152.0000)`, `(122.6875,151.0000)`,
  `(177.7500,117.2500)`.
- The P3 pattern requires no analytical-rail relief. The complete rounded-head
  envelope retains at least `1.20 mm` to installed component bodies, `0.85 mm`
  to routed copper/vias, `2.10 mm` to PCB Edge.Cuts, `2.00 mm` to the housing
  edge, and `2.50 mm` plan clearance to an unrelated key-load support. Actual limiting values
  are left `1.3375/0.8750/2.1500/2.0500/3.4775 mm` and right
  `1.2250/0.9607/2.2125/2.1125/2.6514 mm` in that order. The support is below
  the PCB while the screw head is above it; the physical full-pattern gate remains pending.
- The mounting service model removes keycaps but leaves switches installed.
  All selected points pass the final `3.00 mm` PH0 driver cylinder and
  provisional `3.00 x 1.20 mm` non-countersunk rounded pan/button-head
  envelope without adding a second driver buffer. Reduced/ultra-low, flat,
  and countersunk head substitutions do not satisfy this contract.
  The driver gate includes the full `30.00 x 12.00 mm` BAT1 body, the complete
  `10.00 x 2.50 mm` SW_PWR1 body, and a conservative `13.20 x 2.50 mm`
  longitudinal envelope covering the full `1.60 mm` actuator travel in both
  directions, independently of the unchanged through-hole lead geometry.
  The screw pattern clamps and registers the PCB; it does not replace the
  perimeter rail or the dedicated 31/39 key-load support network. Exact head
  height, installed keycap-skirt rest clearance, and full-travel clearance
  remain pending physical gates until the final screw MPN is qualified.

## Exterior-open underside clearances

The plate is cut completely through from Z `0.00` to `2.50 mm` wherever a
bottom-side assembly envelope is required. The generated STEP volume is
independently compared with the cutout-differenced support plan, and every
required envelope has zero residual intersection volume.

The verified openings cover:

- Choc V2 socket bodies and solder-fillet envelopes;
- all switch center and locator NPTH/mechanical-pin continuations;
- MX electrical pins, pads, solder joints, and lead-trimming access;
- all 70 Diodes Incorporated `1N4148W-13-F` SOD-123 maximum body, pad, and solder-fillet envelopes;
- nice!nano/controller socket/service geometry;
- both `J_BAT1` direct-solder lead/solder envelopes;
- all three `SW_PWR1` IMMS-12V lead/solder envelopes; and
- the copper-free `BAT_LEAD_SLOT1` strain-relief opening.

The `30.00 x 12.00 x 3.00 mm` `BAT1` body sits above the carrier PCB beneath
the socketed nice!nano, so the lower housing deliberately has no battery-body
cavity.

`SW_RST1` is intentionally absent from this underside-cutout list. Its pads
are F.Cu-only, and the exact board-axis `2.70 x 1.30 mm` actuator projection
at left `0` / right `180` degrees is backed by the local
zero-gap support/desk column. The support intersects no via, bottom-exposed
pad, exterior-open cutout, B.Cu route, or B.Mask opening on either current
board. Protection is derived from exact B.Cu and B.Mask geometry rather than
declared as a constant; a routed-copper overlap exposed by a B.Mask opening is
a hard failure.

Every class has at least `0.30 mm` nominal XY clearance. The generated diode
openings use `0.35 mm` XY clearance. No diode
opening breaks the lateral housing perimeter: the limiting opening leaves
`1.5250 mm` of housing material on both sides, against the `0.85 mm` release
gate. The
vertical model uses the official Kailh CPG135001S30 maximum socket depth
`2.30 mm` plus `0.10 mm` assembly allowance, leaving `0.10 mm` to the
plate bottom. It uses Diodes Incorporated's SOD-123 maximum
`2.85 x 1.70 x 1.35 mm` body and `3.85 mm` terminal span plus `0.30 mm`
solder allowance. The feet provide `1.85 mm` nominal diode-to-desk clearance
and `1.55 mm` after the documented `0.30 mm` print allowance. The Choc socket
controls the overall open-component figures at `1.10 mm` nominal and `0.80 mm`
after print tolerance.
Maximum battery thickness/swelling, socket/controller stack clearance,
insulation, retention, lead bend, strain relief, and J_BAT1/IMMS solder
protrusion remain physical gates above the carrier and at the service openings.

- Kailh drawing:
  <https://www.kailhswitch.com/uploads/15927/files/CPG135001S30.pdf>
- Diodes Incorporated 1N4148W product page:
  <https://www.diodes.com/part/view/1N4148W/>
- Diodes Incorporated DS30086 Rev. 31-2 datasheet:
  <https://www.diodes.com/datasheet/download/1N4148W.pdf>

Bottom copper tracks and tented vias do not protrude below the PCB support
plane. Their electrical/mask state remains covered by the V2 board verifier.

## 150 mm printable right split

The left housing is one printable part. The right housing is exactly two parts
and has no stale monolithic STL:

- left: `134.9125 x 122.3000 x 3.5000 mm`;
- right part A: `86.9938 x 92.0500 x 3.5000 mm`;
- right part B: `81.6438 x 122.3000 x 3.5000 mm`.

Every STL is one watertight shell and fits the `150 mm` cube. The two right
parts use two full-depth neck-and-head puzzle captures. They assemble
vertically, use `0.20 mm` nominal print clearance, provide `1.25 mm`
minimum in-plane capture per side, and require neither screws nor adhesive.
This joint provides in-plane case-part registration; it does not claim to
replace the still-pending physical PCB-registration validation.

The generator strips trailing spaces and tabs from exported STEP/STL lines
while preserving newline bytes. The manifest and verifier hard-check
`step_has_trailing_whitespace=false` for both STEP files.

## Regeneration and verification

Use a repository-local Python 3.12 virtual environment with CadQuery 2.8.0.
The current system-default Python 3.14 environment has no CadQuery installed
and is not the supported housing regeneration environment. First confirm that
the Python launcher can resolve Python 3.12:

```powershell
py -3.12 --version
```

If that command fails and `winget` is available, install Python 3.12, open a
new PowerShell session, and confirm the launcher again:

```powershell
winget install --exact --id Python.Python.3.12
py -3.12 --version
```

If `winget` is unavailable, download the Windows x64 Python 3.12 installer
from <https://www.python.org/downloads/windows/>. In the installer, enable the
Python launcher (`py.exe`) option, complete installation, open a new shell,
and rerun `py -3.12 --version` before continuing.

After the version check succeeds, run the following from the repository root:

```powershell
py -3.12 -m venv .venv-cad
.\.venv-cad\Scripts\Activate.ps1
python -m pip install -r requirements-cad.txt
python -B -m tools.generate_kc2_component_models
python -B -m tools.generate_kc2_x3_v2_housings
python -B -m tools.verify_kc2_x3_v2_housing
python -B -m unittest tools.test_generate_kc2_component_models -v
python -B -m unittest tools.test_verify_kc2_x3_v2_housing -v
```

The manifest binds the current source-board SHA-256, generator SHA-256, STEP
and STL SHA-256, support/desk-contact locations, component openings, printable
bounds, M1.4 land/pilot/column/head/driver contract, and joint geometry. The
verifier independently extracts each STL's
bottom contact components and compares their count, centers, Z datum, and
stability hull with the generated plan.

## Remaining physical gate

This is digital clearance and geometry evidence only. `CON-ARCH-006` AC-7 is
still pending: the printed, assembled housing must pass the 2.0 N load test at
the worst spans with no more than 0.30 mm downward PCB displacement, while PCB
registration, pilot/torque/ten-cycle behavior, switch/keycap clearance, and
real component insertion are checked. AC-11 additionally requires the exact
reset supplier Z/travel/force/reflow limits, socketed-controller and
nonconductive-probe service, USB shell/cable clearance, ten double-reset and
bootloader-enumeration cycles, plus the battery physical gates above.
`order_ready` remains false. These canonical files are not fabrication/order-readiness
approval.
