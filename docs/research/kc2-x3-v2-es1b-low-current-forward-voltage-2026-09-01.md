# KC2 X3 V2 ES1B low-current forward-voltage review

Date: 2026-09-01

> **2026-09-01 supersession:** This is historical ES1B analysis. Active V2 uses exact Diodes Incorporated `1N4148W-13-F` SOD-123 and P3 geometry; `CON-ARCH-004` is authoritative. Any selected/current/preferred ES1B wording below describes the superseded ES1B snapshot only.

Active target: `kc2-x3-v2`

Scope requirement: `CON-ARCH-004`, especially AC-7 and AC-9

Status: analytical design evidence only; populated 3.0 V / 3.3 V scan validation remains pending

This note records the manufacturer-data comparison and analytical DC simulation performed after a concern was raised that the ES1B data-sheet forward voltage of approximately `0.92 V` might make the nice!nano v2 matrix input unreliable. It is research evidence, not a second requirements source. The acceptance contract remains in `docs/spec/10.product-architecture.srs.md`.

## Conclusion

The `0.92 V` value is specified at `1 A`; it is not the expected drop at the KC2 row current of approximately `0.20 mA` to `0.25 mA`. Official curves and the Diodes Incorporated manufacturer SPICE model consistently indicate a much lower typical drop at low current. An analytical simulation of the current board topology passes the nRF52840 input-high threshold at both 3.0 V and 3.3 V, including the maximum five simultaneous keys in one active column.

For the historical ES1B candidate, this was not a formal worst-case guarantee for Jingdao `ES1B` / LCSC `C437840`. Jingdao, Vishay, and onsemi do not publish a guaranteed maximum forward voltage at the actual sub-milliampere operating point. The Diodes Incorporated SPICE model describes that manufacturer's device, not the Jingdao production lot. The analysis therefore did not justify a firmware change; the current `CON-ARCH-004 AC-9` still requires populated maximum-row and maximum-column press/release testing at 3.0 V and 3.3 V for the active diode.

## Historical ES1B electrical contract and retained firmware invariant

The active firmware overlays preserve:

- `diode-direction = "col2row"`;
- active-high column GPIOs;
- active-high row GPIOs with internal pull-downs;
- diode pad 1 as cathode/row and pad 2 as anode/per-key switch net;
- unchanged zero-wait scan timing.

References:

- `firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2_left.overlay`
- `firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2_right.overlay`
- `hardware/kicad/draft/x3-v2/kc2_x3_v2_generation_manifest.json`

Both halves have five rows, so at most five closed switches load one driven column simultaneously. Each pressed row has its own controller pull-down.

## Official manufacturer evidence

| Manufacturer | Official evidence | Low-current coverage | Limitation |
| --- | --- | --- | --- |
| Jingdao Microelectronics, selected `C437840` | [LCSC-hosted Jingdao ES1B data sheet](https://datasheet.lcsc.com/datasheet/pdf/2343098076327222563a84c9a80dbd7d.pdf?productCode=C437840) | Figure 4 typical forward curve extends to about `1 mA`; visually it is roughly `0.39 V` at `1 mA` and `0.50 V` at `10 mA`. | Guaranteed maximum is `1.0 V` at `1 A`; no guaranteed sub-mA maximum. |
| Vishay | [ES1A through ES1D data sheet](https://www.vishay.com/docs/88586/es1.pdf) | Figure 3 provides typical curves down to `10 mA` over several junction temperatures. | Maximum values are `0.865 V` at `0.6 A` and `0.920 V` at `1 A`; no sub-mA maximum. |
| onsemi | [ES1A through ES1D data sheet](https://www.onsemi.com/pdf/datasheet/es1d-d.pdf) | Figure 2 provides a typical 25 C curve down to `1 mA`. | `0.92 V` is specified at `1 A`; the document warns that performance outside listed test conditions may not be indicated. |
| Diodes Incorporated | [ES1B product page](https://www.diodes.com/part/view/ES1B) and [official ES1B SPICE model](https://www.diodes.com/spice/download/616/ES1B.spice.txt) | The manufacturer model permits a continuous low-current DC calculation. | It is a typical model for the Diodes Incorporated part and cannot guarantee Jingdao-lot limits. |

The Diodes Incorporated model is:

```text
.MODEL DI_ES1B D (
  IS=123n
  RS=42.0m
  BV=100
  IBV=5.00u
  CJO=18.5p
  M=0.333
  N=2.12
  TT=28.8n
)
```

The controller limits used for comparison are from the official [Nordic nRF52840 GPIO specification](https://docs.nordicsemi.com/r/bundle/ps_nrf52840/page/gpio.html): input-high minimum `VIH = 0.7 x VDD`, and internal pull-down range `11 / 13 / 16 kOhm`. The worst input-loading case uses `11 kOhm`. The [nice!nano documentation](https://nicekeyboards.com/docs/nice-nano/) identifies VCC as the regulated `3.3 V` output; AC-9 additionally requires the explicit 3.0 V stress point.

## Analytical DC model

For each closed key in the active column:

```text
Vrow = Irow * Rpull-down
VDD = Vrow + Vf(Irow) + key_count * Irow * Rdriver
```

Inputs and conservative assumptions:

| Input | Value | Reason |
| --- | ---: | --- |
| `Rpull-down` | `11 kOhm` | Lowest nRF52840 pull-down resistance produces the highest diode/driver current. |
| `Rdriver` | `400 Ohm` | Conservative equivalent derived from the standard-drive `1 mA` output guarantee at `VDD - 0.4 V`. It is shared by all pressed rows on the active column. |
| Simultaneous keys | `1` and `5` | `5` is the exact maximum number of KC2 rows on either half. |
| Temperature | `25 C` | Matches the published typical curve/model condition; temperature corners remain physical-test scope. |
| Input threshold | `0.7 x VDD` | nRF52840 guaranteed input-high minimum. |

For the Diodes Incorporated model, the forward drop is solved using:

```text
Vf(I) = N * Vt * ln(1 + I / IS) + I * RS
```

### Diodes Incorporated SPICE-model result

| VDD | Closed keys in active column | Row current | Model Vf | Row voltage | VIH minimum | Margin |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3.0 V | 1 | 0.2272 mA | 0.4097 V | 2.4994 V | 2.1000 V | +0.3994 V |
| 3.0 V | 5 | 0.1998 mA per row | 0.4027 V | 2.1977 V | 2.1000 V | +0.0977 V |
| 3.3 V | 1 | 0.2530 mA | 0.4156 V | 2.7832 V | 2.3100 V | +0.4732 V |
| 3.3 V | 5 | 0.2224 mA per row | 0.4086 V | 2.4466 V | 2.3100 V | +0.1366 V |

### Jingdao typical-curve sensitivity result

The Jingdao Figure 4 curve was visually digitized only as a typical curve. To expose model sensitivity rather than claim a guaranteed limit, the same five-key network was solved for the nominal fit and for artificial `+0.10 V` and `+0.20 V` offsets applied across the low-current curve.

| VDD | Curve case | Row voltage | VIH minimum | Margin |
| ---: | --- | ---: | ---: | ---: |
| 3.0 V | typical fit | 2.2967 V | 2.1000 V | +0.1967 V |
| 3.0 V | typical fit + 0.10 V | 2.2139 V | 2.1000 V | +0.1139 V |
| 3.0 V | typical fit + 0.20 V | 2.1312 V | 2.1000 V | +0.0312 V |
| 3.3 V | typical fit | 2.5453 V | 2.3100 V | +0.2353 V |
| 3.3 V | typical fit + 0.10 V | 2.4624 V | 2.3100 V | +0.1524 V |
| 3.3 V | typical fit + 0.20 V | 2.3795 V | 2.3100 V | +0.0695 V |

As an intentionally unrealistic sparse-data extreme, anchoring a single exponential only to the `1 A / 1.0 V` maximum can produce a failing result. That construction is not a manufacturer low-current model and demonstrates why a high-current maximum must not be extrapolated directly to the matrix operating point.

## Interpretation and remaining evidence

The official evidence supports these engineering conclusions:

1. The claimed `0.92 V` to `0.95 V` drop is a high-current value and is not representative of the approximately `0.2 mA` KC2 scan current.
2. Independent manufacturer curves and the official Diodes Incorporated model support a typical low-current drop near `0.4 V`, not near `0.92 V`.
3. The conservative five-key calculation still has only about `0.10 V` to `0.14 V` guaranteed-threshold margin with the Diodes Incorporated typical model. This is adequate analytical evidence to retain the present design, but not enough to waive process, temperature, lot, contact, leakage, and dynamic scan testing.
4. Generic `ES1B` markings do not make different manufacturers electrically identical. Vishay, onsemi, and Diodes Incorporated data were comparison evidence only; the controlled BOM at the time was Jingdao `ES1B`, LCSC `C437840`, Eleparts `9475342`.
5. No firmware scan-delay change should be made before the unchanged zero-wait baseline is measured, as required by `CON-ARCH-004 AC-9`.

The populated coupon or first article should record, for both halves:

- actual VDD at 3.0 V and 3.3 V;
- maximum same-column five-key press and release;
- maximum same-row press and release required by AC-9;
- row-node minimum/maximum voltage or logic trace during scanning;
- missing, false, or stuck-key count;
- diode manufacturer/lot, temperature, firmware/build identity, and instrument/calibration identity.

Until that record exists, the repository must continue to report `order_ready=false` and `fabrication_or_order_ready=false`.

## Budget procurement survey

The following price survey was captured on 2026-09-01 KST for budget planning. Prices, stock, selectable variants, coupons, VAT, and shipping are dynamic and must be rechecked in the cart. KC2 uses 70 diodes per complete keyboard, or 350 diodes for five keyboards. A marketplace listing is not a manufacturer-identity or incoming-inspection record.

### Eleparts

| Candidate | Displayed terms | Approximate five-keyboard material cost | Assessment |
| --- | --- | ---: | --- |
| [Jingdao ES1B, Eleparts goods 9475342](https://www.eleparts.co.kr/goods/view?no=9475342) | Exact selected manufacturer and part for the historical ES1B candidate; SMA; stock `114,900`; MOQ/sales unit `50`; average dispatch `9` working days; `21.82 KRW` before VAT / about `24 KRW` with VAT per piece | `350 x 24 = 8,400 KRW`; approximately `11,400 KRW` with the site's ordinary sub-60,000 KRW domestic shipping | **Historical preferred budget source.** It preserved the then-controlled Jingdao `ES1B` / LCSC `C437840` / Eleparts `9475342` identity and 350 was a valid multiple of 50. |
| [JSCJ ES1B(SMAG), goods 12614916](https://www.eleparts.co.kr/goods/view?no=12614916) | JSCJ; package listed as `SMAG`; stock `2,520`; MOQ/sales unit `20`; approximately `49 KRW` including VAT each | Must buy `360`; approximately `17,640 KRW` before shipping | Cheap, but `SMAG` drawing and terminal geometry must be compared with the owned SMA footprint before substitution. Not approved by the current BOM. |
| [Diodes Inc. ES1B-13-F, goods 18843678](https://www.eleparts.co.kr/goods/view?no=18843678) | Diodes Incorporated; DO-214AC/SMA; stock `180,000`; displayed about `309 KRW` including VAT each, but current MOQ/sales unit is `5,000` | Approximately `1,545,000 KRW` minimum purchase | Electrically well documented and has an official SPICE model, but the listed minimum quantity is uneconomical. |
| [Vishay ES1B-E3/5AT, goods 3409082](https://www.eleparts.co.kr/goods/view?no=3409082) | Vishay; DO-214AC/SMA; stock `320`; MOQ/sales unit `10`; approximately `561 KRW` including VAT each | `350 x 561 = 196,350 KRW` | Controlled manufacturer source, but far more expensive and available stock is ten pieces short of the five-keyboard requirement. |

For comparison, the [LCSC controlled Jingdao C437840 listing](https://www.lcsc.com/product-detail/C437840.html) showed a 50-piece minimum and about `USD 0.0081` each at the same review time. That component is already the JLCPCB quote BOM identity; direct-shipping and assembly-service charges determine whether it is cheaper in the final cart.

### AliExpress

AliExpress search results are option-dependent. A displayed card price may belong to another diode or quantity in the same listing, and manufacturer traceability is generally weaker than the exact Eleparts/LCSC record. The following are price-discovery links, not approved substitutes:

| Listing | Search-card price and quantity | Nominal cost for at least 350 | Risk |
| --- | ---: | ---: | --- |
| [Item 1005007110689047](https://www.aliexpress.com/item/1005007110689047.html) | `50` pieces, displayed `1,291 KRW` | Seven lots, about `9,037 KRW` before shipping | ES1A/ES1B/ES1C/etc. shared option listing; exact ES1B option price and manufacturer must be checked. |
| [Item 1005006026709349](https://www.aliexpress.com/item/1005006026709349.html) | `20` pieces, displayed `1,558 KRW` | Eighteen lots/360 pieces, about `28,044 KRW` before shipping | Claims ES1B-E3/61T/EB marking, but seller traceability and authenticity are not controlled. |
| [Item 1005012931443334](https://www.aliexpress.com/item/1005012931443334.html) | `10` pieces, displayed `1,240 KRW` | Thirty-five lots, about `43,400 KRW` before shipping | Claims ES1B-E3/61T; still more expensive than the exact Eleparts Jingdao listing before shipping. |
| [Item 1005008479894445](https://www.aliexpress.com/item/1005008479894445.html) | Mixed 2,000-piece ES1A/ES1B/etc. listing, displayed `13,100 KRW` | One oversized lot | Very low nominal unit price, but shared model/package options and unknown manufacturer make the card price especially unreliable. Excess quantity is also unnecessary. |

The search also returned a listing that described an ES1B option as a Schottky diode. ES1B is an ultrafast silicon rectifier, not a Schottky part; such inconsistent listings should be rejected unless the delivered manufacturer's marking, data sheet, package, polarity, and sample electrical behavior are independently verified.

### Procurement decision

For the current board and five-keyboard quantity, buying exactly 350 Jingdao `C437840` parts from Eleparts is both cheaper and more traceable than the reviewed AliExpress offers. Ordering 400 instead would provide 50 spares for approximately `9,600 KRW` before shipping while retaining the exact controlled identity. The JLCPCB PCBA quote may still be cheaper once placement and service charges are known, but its current package remains price-discovery only and `order_ready=false`.
