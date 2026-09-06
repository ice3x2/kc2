# KC2 MX mechanical follow-up — 2026-09-06

Scope: read-only follow-up under `CON-ARCH-006` (in progress/evolving) and `OPS-ARCH-007` (implemented/evolving), queried through SpecKiwi before this review. No sealed PCB, CAD, SVG, manifest or first-order binding was edited. This report is analysis, not a substitute SRS or physical qualification.

## Actual cap evidence search

Repository-wide filename/content searches, including hidden development artifacts and third-party models, found no exact selected keycap STEP/STL/F3D or dimensioned underside/travel model. Available 3D assets are the housings and an IMMS service-switch model. The renderer's keycaps are rectangular plan envelopes derived from unit widths, not actual hollow cap geometry. Therefore an exact swept-volume check cannot presently be performed from repository evidence. Substituting an unrelated Cherry/OEM/DSA cap would not establish the user's cap fit.

The existing [all-17 review](kc2-first-order-socket-fit-2026-09-06.md) remains valid: 13 head discs overlap nominal keycap rectangles, one is tangent, and three are disjoint. That is not a proven 3D collision. Current head top is plate top +1.20 mm; including an explicit 0.30 mm engineering reserve requires cap underside at least plate top +1.50 mm at the overlapping locations throughout travel.

## Minimal local alternatives, same PCB and 17 centers

All calculations retain the 3.00 mm maximum diameter ×1.20 mm rounded pan/button head, 1.60 mm free PCB hole, plate top 9.30 mm, plate thickness 1.50 mm, PCB top 4.10 mm, receiver entry 2.50 mm and 2.80 mm blind pilot. A cylindrical counterbore is not a countersunk-head substitution. Proposed 3.40 mm pocket diameter gives 0.20 mm radial head/driver clearance; this is an engineering nominal, not demonstrated FDM tolerance.

| Candidate | Recess depth | Remaining plate floor | Head top relative plate | Suggested under-head length | Nominal insertion / tip reserve |
|---|---:|---:|---:|---:|---:|
| Current | 0 | 1.50 mm | +1.20 mm | 9.00 mm | 2.20 / 0.60 mm |
| Smallest CAD change | 1.00 mm | 0.50 mm | +0.20 mm | 8.00 mm | 2.20 / 0.60 mm |
| Flush, thin membrane | 1.20 mm | 0.30 mm | 0 | 7.50 mm | 1.90 / 0.90 mm |
| Fully recessed with collar | 1.50 mm | 0; requires collar | −0.30 mm | 7.50 mm | 2.20 / 0.60 mm |

The 1.00 mm recess is the smallest bounded improvement: unchanged existing posts and PCB contacts, an ordinary 8 mm nominal length candidate, and a 1.00 mm reduction in the unknown cap-interface height. With the same 0.30 mm reserve, cap underside need only remain ≥plate +0.50 mm rather than +1.50 mm. It reduces risk but does not independently prove full travel. The 0.50 mm floor is backed directly by the existing annular post under the 3.00 mm head; its surrounding diaphragm still connects the post to the plate and carries anti-lift/lateral loads. Do not infer adequate strength from axial support alone.

Simply cutting a 3.40 mm pocket through the full 1.50 mm plate is **invalid**: the existing post is only 3.00 mm OD, so the pocket extends radially 0.20 mm beyond it and removes the plate connection. A deeper pocket therefore needs a widened upper collar joined to the plate, not just a deeper subtractive cut. This is a concrete topological issue discoverable before printing.

## Fully recessed collar feasibility

A proposed collar OD 4.60 mm around the 3.40 mm pocket leaves 0.60 mm radial wall. With its bearing plane at Z=7.80 mm, the head top is Z=9.00 mm, 0.30 mm below the existing plate top. This can eliminate the head as a protruding obstacle wherever the cap already clears the plate, without changing switch seating height, the external outline or PCB drilling. It is not a claim that every cap clears the plate itself.

Do not widen the PCB contact from the required 3.00 mm OD to 4.60 mm by default. The existing minimum head-to-copper plan gap is 0.875 mm; increasing radius by 0.80 mm leaves only 0.075 mm, below the 0.30 mm copper separation if that enlarged contact touches PCB. Instead preserve the existing 3.00 mm landing at PCB Z=4.10 mm and enlarge only an upper collar, with a separately dimensioned transition above PCB and all solder envelopes. For example an upper shoulder beginning at Z=5.30 mm leaves 1.20 mm geometric space above PCB before unknown top-side fillets; that number is not a verified solder-height limit. The head bearing plane then has 2.50 mm axial material down to that shoulder, apart from the shaft hole. This must be modeled and collision-checked before implementation.

The existing installed-component union includes switch-service bodies, controller/socket/reset features and battery/POWER bodies/sweep. Expanding the head disc's radius by 0.80 mm bounds the proposed collar's remaining plan gap to that same union: left ≥0.5375 mm and right ≥0.4250 mm. The latter is only 0.1250 mm beyond a proposed 0.30 mm reserve. Thus the nominal collar is not already ruled out by those modeled bodies, but print error and missing exact-part envelopes cannot be ignored. To nominal 14 mm switch apertures the minimum collar gap is 1.225 mm, leaving 0.625 mm beyond the existing 0.60 mm continuous clip ring. The pocket edge itself has at least 1.825 mm aperture separation.

**Actual STEP check found a split conflict at right MH8.** CadQuery 2.8 imported the canonical upper STEP files read-only. At every one of the 17 actual housing mounting centers, a 4.60 mm diameter cylinder over Z=8.00–9.20 mm was intersected with each actual solid. Sixteen centers retain the complete local plate annulus in exactly one solid, volume 17.531809 mm³ (the slight difference from an ideal circular 1.60 mm hole is the existing polygonal bore approximation). Right MH8 instead intersects both split parts: 1.558624 and 14.378322 mm³, with approximately 1.593141 mm³ absent in the seam compared with the ideal annulus. A circular 4.60 mm collar there is **not a drop-in addition** to the current split. It needs a locally rerouted split with retained captive-joint behavior, or a separately checked noncircular collar. This is a digital conflict, not something to defer until printing. No modified CAD was exported.

Further right MH8 probes confirm radii 1.70 and 1.80 mm lie entirely in one part: measured annular volumes 8.484022 and 9.803491 mm³ over the same 1.20 mm slice. Radius 2.00 mm loses approximately 0.727 mm³ to the seam; radius 2.10 mm begins entering the other part. Thus the shallow **3.40 mm diameter pocket** fits the current split at the limiting mount, and also fits the other sixteen larger verified local regions. It avoids the newly identified 4.60 mm collar/split conflict. This checks pocket plan containment, not the strength of the resulting 0.50 mm diaphragm.

## Screw, printing and requirement tradeoffs

For each candidate, insertion is `L − (6.80 − recess_depth)` and tip reserve is `2.80 − insertion`. PCB-only thickness variation ±0.16 mm changes insertion by ±0.16 and tip reserve oppositely. Thus the 1.00 mm recess/8.00 mm screw and 1.50 mm recess/7.50 mm screw both retain insertion 2.04–2.36 mm and reserve 0.44–0.76 mm before screw/print tolerances. A 7.00 mm screw with the deep recess gives 1.70 mm nominal insertion and 1.10 mm reserve; a pointed tip further reduces full-thread engagement. A 7.50 mm exact purchasable screw has not been identified here. Keeping the current 9 mm screw after either proposed recess risks bottoming and is not permissible.

The collar's 0.60 mm wall and shallow recess's 0.50 mm diaphragm are engineering candidates, not strength minima sourced from a material or printer specification. Material, layer height, perimeter count, hole compensation and torque remain unspecified. With plate-top-on-bed orientation, the pocket roof is a small approximately 3.40 mm bridge; supports or a controlled bridge process may affect the bearing surface. A local collar may be printed in the same overall orientation but cannot inherit the old flat-plate mesh/strength evidence. There is no basis for claiming the required stripping/installation torque ratio or 2 N deflection result from these dimensions alone.

Both alternatives preserve the user-facing architecture, exact MH centers, rounded-head style, thin flat plate and lower housing thickness. `CON-ARCH-006` AC-4 allows a head to bear on a supported lid land and does not explicitly prohibit a cylindrical recess. Nonetheless actual bearing height, free-hole profile, long-screw selection and validation contracts must be recorded through a reviewed SRS update before implementation, particularly a collar that alters the upper hard-stop geometry. Preserve the fixed 3.00 mm PCB landing and lower receiver unless separately authorized. Any implementation requires failing tests first, source-bound CAD/mesh regeneration, split/clip/service/copper checks, native F3D re-export/reopen, and renewed release binding; none was performed or implicitly approved in this read-only task.

## Recommendation

Best minimal improvement is the **1.00 mm local recess plus 8.00 mm nominal screw candidate**: it preserves the current supported land topology and lowers the head obstruction by 1.00 mm without PCB changes. If the objective is to remove all head projection above the plate without exact cap data, prefer the **1.50 mm recessed, widened-upper-collar concept**, but only after the actual collar transition, split containment and exact screw are resolved. Do not adopt the unsupported full-depth cut or declare either candidate physically qualified. No existing sealed artifact was modified.
