# KC2 Plateless Low-Profile Stabilizer Removal Research - 2026-06-04

## Summary

The committee recommendation is to treat `<=1.75U` as the normal stabilizer-free limit for KC2, and to split every current `>=2U` key into smaller keys before fabricating a plateless low-profile PCB.

This is a mechanical requirement change, not just a keymap change. The current KC2 draft places provisional stabilizer markers for all keys with `key.w_u >= 2.0`, and the local specification already states that `2u 이상` keys need stabilizer consideration. If the target is truly "무보강판 + no stabilizers", the wide keys should be removed from the physical layout rather than shipped as unstabilized 2U+ keys.

Final stance:

- Keep `1.75U` keys unstabilized, but physically test them.
- Split all `2U`, `2.25U`, and `2.5U` keys.
- Prefer `1U` and `1.5U` keycaps.
- Use `1.25U` only where preserving existing row width makes it valuable.
- Do not fabricate the provisional `KC2:PCB_Mount_2u_Stabilizer_NPTH` as a final low-profile stabilizer solution.

## Committee Process

Seven roles were used:

1. Mechanical stability
2. PCB geometry and matrix impact
3. Choc keycap ecosystem
4. Ergonomics and keymap usefulness
5. Skeptical reviewer
6. Fabrication and verification checklist
7. Committee chair / synthesis

The agents agreed on the core threshold: a plateless no-stabilizer KC2 should not keep `>=2U` keys unless a real coupon proves the exact switch/keycap combination acceptable. The main disagreement was conservatism around `1.75U`: the skeptical reviewer wanted every `>=1.75U` key physically proven, while the mechanical and local-spec view accepted `1.75U` as the normal upper bound.

## Local Evidence

- `docs/spec.md` states that KC2 has no top plate and that common Kailh Choc V1/V2 stabilizers generally depend on PCB cutouts plus a thin switch plate.
- `docs/spec.md` sets the stabilizer criterion at `2u 이상` and omits stabilizers for `1.75u` and below.
- `tools/generate_kc2_pcbs.py` creates a stabilizer marker whenever `key.w_u >= 2.0`.
- Current wide keys:
  - Left `Shift`: `2.25U`
  - Left `Space`: `2.25U`
  - Right `BSPC`: `2.25U`
  - Right `Enter`: `2.5U`
  - Right `RShift`: `2.0U`
  - Right `Space`: `2.0U`

## External Evidence

Sources checked:

- LowproKB Kailh Choc Stabilizers: https://lowprokb.ca/products/kailh-choc-stabilizers
- Keebio Kailh Choc Stabilizer Installation: https://docs.keeb.io/choc-stabs
- Keebio Kailh Choc V2 Stabilizers: https://keeb.io/products/kailh-choc-v2-stabilizers
- Keebio Kailh Choc V1 switches: https://keeb.io/products/kailh-choc-low-profile-switches-v1
- Holykeebs buyer guide: https://docs.holykeebs.com/guides/buyers-guide/
- Chocfox CFX keycaps: https://shop.yushakobo.jp/en/products/5667
- SliceMK ErgoDoxLP Choc V1 keycap notes: https://docs.slicemk.com/keyboard/ergodox/keycap/choc-v1/
- Keebio-Parts.pretty: https://github.com/keebio/Keebio-Parts.pretty

Findings:

- Choc stabilizers are not a drop-in answer for KC2's no-top-plate design. LowproKB describes the Choc V1 stabilizer as a 2U+ low-profile solution that mounts between PCB and switch plate, and states that a switch plate is required.
- Keebio's Choc stabilizer installation guide is also plate-centered and calls out a thin plate requirement.
- Keebio's Choc V2 stabilizer is explicitly for Choc V2 / Gateron KS-33 style low-profile switches, not Choc V1, and is plate-mounted with a PCB cutout.
- Choc V1 / PG1350 does not share MX keycap/stabilizer assumptions; Choc V1 keycaps and stabilizers must be treated as their own ecosystem.
- Choc keycap availability is strongest at `1U`, `1.5U`, and `2U`. `1.25U` and `1.75U` are possible through profiles such as CFX / MoErgo-style offerings, but they increase sourcing constraints.
- Keebio-Parts has Choc stabilizer cutout footprints, but its README warns that the Choc stab cutouts are experimental and best-effort. That is not a fabrication sign-off for KC2.

## Width Policy

| Width | Stabilizer-free judgement | KC2 policy |
|---:|---|---|
| `1U` | Safe baseline | Use freely |
| `1.25U` | Mechanically acceptable, sourcing narrower than `1U` | Use where preserving row extent matters |
| `1.5U` | Good balance for modifiers/thumb keys | Preferred non-1U size |
| `1.75U` | Acceptable but test on real keycaps | Keep only where useful |
| `2U` | Borderline, stabilizer target in local spec | Split |
| `2.25U` | Not recommended unstabilized | Split |
| `2.5U` | Reject unstabilized for production | Split |

## Final KLE-Style JSON

This JSON preserves current KC2 row extents while removing all `>=2U` physical keys. It raises the layout from 71 keys to 77 keys: left half 30 -> 32, right half 41 -> 45.

```json
{
  "left": [
    ["~", "1", "2", "3", "4", "5", "6"],
    [{ "w": 1.5 }, "TAB", "Q", "W", "E", "R", "T"],
    [{ "w": 1.75 }, "Caps", "A", "S", "D", "F", "G"],
    [{ "w": 1.25 }, "LShift", "CapsWord", "Z", "X", "C", "V", "B"],
    [{ "w": 1.25 }, "Ctrl", { "w": 1.25 }, "Win", { "w": 1.25 }, "Alt", { "w": 1.25 }, "Fn", "Nav", { "w": 1.25 }, "Space"]
  ],
  "right": [
    [{ "x": 0.5 }, "7", "8", "9", "0", "-", "=", "Esc", { "w": 1.25 }, "BSPC", "Del"],
    ["Y", "U", "I", "O", "P", "[", "]", { "w": 1.75 }, "\\", "Home"],
    [{ "x": 0.25 }, "H", "J", "K", "L", ";", "'", "Sym", { "w": 1.5 }, "Enter", "PgUp"],
    [{ "x": 0.75 }, "N", "M", ",", ".", "/", "RShift", "Fn", "Up", "PgDn"],
    [{ "x": 0.75 }, "B_RH", "Space", "Num", "RAlt", "Fn", "RCtrl", "Left", "Down", "Right"]
  ]
}
```

## Split Decisions

| Original key | Original width | Replacement | Reason |
|---|---:|---|---|
| Left `Shift` | `2.25U` | `1.25U LShift` + `1U CapsWord` | Keeps primary Shift at the left pinky edge and adds a useful typing function. |
| Left `Space` | `2.25U` | `1U Nav` + `1.25U Space` | Keeps Space at the inner thumb position and uses the extra key for navigation layer access. |
| Right `BSPC` | `2.25U` | `1U Esc` + `1.25U BSPC` | Preserves a larger Backspace while recovering a dedicated Escape key and avoiding duplicate Delete keys. |
| Right `Enter` | `2.5U` | `1U Sym` + `1.5U Enter` | Keeps Enter larger than ordinary keys, and gives symbol-layer access next to punctuation. |
| Right `RShift` | `2.0U` | `1U RShift` + `1U Fn` | Keeps Shift in the expected row and moves low-frequency layer access to the second half. |
| Right `Space` | `2.0U` | `1U Space` + `1U Num` | Keeps a right thumb Space and adds a number-layer key. |

## Matrix and PCB Impact

Expected key count:

- Left: 32 keys
- Right: 45 keys
- Total: 77 keys

The proposal preserves each row's physical width, so the outer outline can remain close to the current row extents. However, the implementation is not a trivial label change:

- Add 6 switch footprints.
- Add 6 diodes.
- Remove all six provisional stabilizer markers.
- Re-run routing and DRC for every PCB variant intended to support the new layout.
- Update ZMK matrix and keymap definitions.
- Revisit right-side column assignment. A naive `col_idx`-based generator change will shift right-side column meanings and can invalidate the current `R_COL7`/`R_COL8` rationale.

## Debate Notes

Arguments for splitting:

- Removes dependency on hard-to-retain low-profile stabilizers in a plateless design.
- Avoids shipping a provisional MX-style stabilizer marker as a false low-profile solution.
- Keeps all keys below the generator's current `>=2U` stabilizer threshold.
- Makes the board more self-contained mechanically: switch + keycap only.

Arguments against splitting:

- Adds six switches, six diodes, routing work, firmware positions, and QA cases.
- Makes the layout less conventional, especially for Space, Backspace, Enter, and Shift.
- `1.25U` keycaps are more constrained than `1U`/`1.5U`.
- No-stabilizer feel still must be proven on real Choc switches and real target keycaps.

Committee resolution:

- Splitting is the better direction for KC2 if the design remains plateless.
- `1.75U` should remain allowed but must be physically tested.
- `2U` exceptions should not be accepted by default; they require a coupon and a written waiver.

## Verification Checklist Before Implementation

- [ ] Confirm final policy: "no stabilizer holes on all keys" versus "no plate-mounted stabilizers only".
- [ ] Test `Caps 1.75U` and `\\ 1.75U` with the actual Choc switch and target keycap.
- [ ] Test off-center presses on every proposed `1.25U`, `1.5U`, and `1.75U` key.
- [ ] Confirm target keycap supply for `1.25U` and `1.5U`.
- [ ] Decide whether right top-row outer key should be `Del`, `Ins`, or another function after Backspace is split.
- [ ] Implement explicit matrix columns or update the `R_COL7`/`R_COL8` rationale.
- [ ] Re-run PCB generation, routing, and KiCad DRC after the layout change.
- [ ] Inspect `track_dangling`, `silk_over_copper`, `text_height`, and `lib_footprint_issues` warnings after reroute.
- [ ] Verify hotswap socket orientation and bottom-side clearance with real parts.
- [ ] Verify bottom plate relief for sockets, switch pins, SOD-123 diodes, controller pins, battery, and wire loops.
- [ ] 1:1 print both halves with scale marks and test keycap envelopes, join edge, USB cable clearance, M2 holes, and controller tab recess.
- [ ] Build a mechanical coupon before full fabrication.

## Follow-Up Implementation Direction

The clean implementation should not only edit the row arrays. It should also:

- introduce stable per-key physical IDs,
- decouple matrix column assignment from visual row order where needed,
- regenerate board files for selected variants,
- update `docs/spec.md`,
- update ZMK definitions once firmware files exist in the repository,
- document the final wide-key removal decision as a spec change.
