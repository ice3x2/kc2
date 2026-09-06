# Revised assembly and 1:1 review

Requirements: `CON-ARCH-004`, `CON-ARCH-006`, `OPS-ARCH-007`.

This is an engineering review of the revised nominal assembly, not measured switch contact, printed strength, or universal keycap qualification. The final release must additionally bind passing current CAD/native/output evidence.

## Interfaces preserved

The regenerated `hardware/case/kc2_first_order_1to1_manifest.json` records the actual current PCB coordinates and raw source hashes. Both full-size SVGs were rasterized and visually inspected: 31/39 switch openings, 24 controller pins per half, 8/9 mounting centers and the enlarged locator circles align with the same board-coordinate datum. The drawings use physical millimetres and a 50 mm calibration line; print at 100%, without fit-to-page. This is digital scale/registration evidence, not a claim that a particular printer has been calibrated.

The central rings retain one 0.20 mm flange layer, 4.80 mm barrel OD, 6.00 mm cap OD and 1.20 mm barrel length. V1 bore is 3.50 mm, MX bore is 4.10 mm. The flange is printed on the bed; total height is 1.40 mm (seven 0.20 mm layers), with only the cap occupying one layer. The smaller V1 bore is conservative for the CAD ring-material collision envelope; saved mesh topology and dimensions are checked separately. Do not force a switch into a poorly printed bore.

V1 uses the bottom Choc socket and its appropriate central ring, not the MX retention plate. MX uses two individual hat receptacles and the MX plate-lid. Choc V2 is the separate bottom-socket assembly. These alternatives are mutually exclusive at each switch; one plate is not claimed to retain all three switch families. V1 locator clearance has been corrected on all70 switches; the ring alone could not correct the old locator-hole conflict.

## Recessed screw stack

The reviewed nominal section has PCB bottom/top at Z2.50/4.10 mm and plate top at Z9.30 mm. Each head pocket is diameter3.40 mm and depth1.50 mm, with bearing Z7.80 mm. A conservative diameter3.00 mm, height1.20 mm head occupies Z7.80..9.00, leaving0.30 mm below the plate top. Unlike r2, the head no longer projects above the plate. This removes that additional obstacle for caps that otherwise clear the plate; no unprovided cap underside or swept volume is invented.

Upper collars are diameter4.60 mm from Z5.30 mm, retaining the existing diameter3.00 mm PCB contact landing at Z4.10..5.30. The bearing floor is2.50 mm thick and the nominal pocket wall0.60 mm. These dimensions are not material-strength or torque measurements. The right upper seam locally reserves the entire MH8 collar, preserving both captive joints. The generated BRep section checks must show all17 head envelopes clear, full collar-wall sections and no enlarged PCB contact landing.

For this lower receiver, nominal under-head-to-entry span is5.30 mm. A7.50 mm under-head screw gives2.20 mm insertion into a2.80 mm blind pilot, leaving0.60 mm nominal tip reserve. The [Monotaro40411061 supplier table](https://www.monotaro.com/p/4041/1061/) specifies M1.4, pitch0.30 mm, length7.50 mm, head diameter2.50(+0.05/-0.10) mm and height0.70±0.05 mm. That head fits within the conservative modeled envelope. Length/point tolerance and printed thread retention are not supplied or measured. The former9 mm candidate is obsolete; do not substitute8/9/10 mm without recalculating the complete actual stack. Do not bottom screws or use torque to pull an obstructed stack together.

## Explicit remaining receipt checks

- Hat receptacle barrel/flange nominal dimensions are specified, but exact barrel tolerances, permissible flat blade dimensions, contact spring depth and insertion/removal forces are unknown. A compatibility label is not a contact datasheet.
- The selected TTC and Kailh seller variants lack a controlled exact-part drawing link; the manufacturer TTC listing has different force/travel figures and cannot supply tighter assumed tolerances. See `kc2-selected-component-source-closure-2026-09-06.md`.
- V1 nominal pin protrusion after a0.20 mm flange and1.60 mm PCB is0.85 mm. This is not proof of sufficient engagement with the socket spring. Check unpowered seating/contact before soldering the full assembly.
- Align receptacles with the actual intended switch and plate, tack one joint, allow cooling, and confirm straight seating and removal before completing joints. Avoid excess solder entering the open contact cavity. The three documented same-net exposed-via exceptions may wick solder; they are not electrical shorts and are not falsely called tented.
- Verify printed aperture/clip/ring dimensions, both split joints, insulation, actual screw tip reserve, full key travel, torque/retention,2 N deflection and long-term contact performance on received parts. Verify battery polarity and POWER/RESET continuity before energizing; do not bridge an unqualified charge-boost option.

The first lot remains a product lot with explicit rework risk under OPS-ARCH-007. These pending physical tests are not represented as passed, and any newly discovered known incompatibility blocks the final release rather than being hidden in this list.
