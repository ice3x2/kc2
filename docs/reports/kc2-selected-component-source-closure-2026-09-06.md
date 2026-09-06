# Selected-component source closure review

Date: 2026-09-06. Requirement: `CON-ARCH-004`; release interpretation: `OPS-ARCH-007`.
Read-only component research; no board, requirements, old evidence or part selection was changed.

## Result

The bounded primary-source search did **not** close the exact selected TTC blade/post/seat tolerances,
the selected hat socket's admissible contact range, or the selected Deep Sea brown switch's controlled
manufacturer drawing/MPN linkage. These remain unknown, not zero-tolerance fits or newly discovered
dimensional failures. No seller was contacted and no order was placed.

## TTC selected listing

The user selected [AliExpress item 1005012442816250](https://ko.aliexpress.com/item/1005012442816250.html).
Its [seller image](https://ae-pic-a1.aliexpress-media.com/kf/Sd76e89944bdc4bf2881f9a82ffc9d9b5z.jpg),
re-inspected locally as `.codex-tmp/selected-ttc-0.jpg`, identifies Bluish White, tactile/silent,
3-pin, operating force 42 ± 5 gf, tactile force 50 ± 5 gf, pretravel 2.0 ± 0.4 mm and total travel
3.5 ± 0.4 mm. It shows two electrical contacts and one plastic center post, not a dimensioned drawing.
Raw image SHA-256: `faa5dfdca7bc4e5258707617f1183e0d1f4be8e548b13f78eef98a6a620eb799`.

The [TTC manufacturer Bluish White page](https://en.ttc9.com/product/122.html) was fetched successfully
with direct HTTP after the browser tool failed. Its product text/table gives 42 ± 5 gf operating force,
58 ± 5 gf tactile force, 2.0 ± 0.3 mm pretravel and 3.5 ± 0.3 mm total travel. Those tactile-force and travel
tolerances differ from the seller image. The inspected product text and links provide no controlled
blade cross-section, exposed blade length, center-post diameter/length or board/plate seating datum.
No exact manufacturer order code ties that manufacturer's page revision to this AliExpress lot.
Do not silently substitute the manufacturer's narrower travel tolerance or infer a V2 revision.

The seller's stated travel has an upper end of 3.9 mm. This can bound a travel-only engineering
scenario; it does not establish a keycap underside or socket engagement depth.

## Selected hat socket

The selection is [AliExpress item 1005010364025678](https://ko.aliexpress.com/item/1005010364025678.html),
hat style. The [seller section drawing](https://ae-pic-a1.aliexpress-media.com/kf/S4b47dab427cd4b539a50618bf16a62d9J.jpg)
was visually re-inspected from `.codex-tmp/hat-seller-3.jpg`; raw SHA-256
`0bdb35b93473ce078fcd53aafcb68abb7cc7c5bdea75106ccb31a1afc4d260fc`.
It shows 3.00 mm overall length, 1.45 mm barrel OD, 2.00 mm flange OD, 0.20 mm flange thickness,
an internal claw spring and open bottom. It gives no bore diameter, spring throat dimension,
contact working depth, insertion force, rectangular-blade acceptance range or tolerances.

The same image also shows a different hatless 3.50 mm / 1.50 mm OD variant. It is not selected.
Neither a genuine Mill-Max family specification nor the previously downloaded closed-bottom
4 mm socket drawing can establish contact acceptance for this untraceable hat-compatible part.
No controlled manufacturer part identity for the selected hat was found in the inspected sources.

## Kailh selected brown listing

The user selected the brown option of [AliExpress item 1005008743343263](https://ko.aliexpress.com/item/1005008743343263.html).
Cached seller photographs `.codex-tmp/kailh-selected-main.jpg`, `kailh-selected-second.jpg` and
`kailh-selected-last.jpg` were visually re-inspected. They show the low-profile blue-base product,
brown circular-wall cross stem, and a separate pink-stem option. They contain no dimension annotations
or readable manufacturer part code. Main image raw SHA-256:
`9b2a86dd47a460c159f2f768d14cd5e16e1b5c2874a36418b33bb98e89f53ed3`.

The [Kailh product datasheet index](https://www.kailh.net/pages/product-datasheet) separates normal-height
Deep Sea Silent Box from Choc V2. Its [Choc V2 product page](https://www.kailh.net/products/kailh-choc-v2-low-profile-switch-set)
lists brown `CPG135301D02` and links a [manufacturer datasheet](https://cdn.shopify.com/s/files/1/0657/6075/5954/files/SPEC-CPG135301D02_Kailh_Choc_V2_Low_Profile_Brown_Switch_828a8159-bda2-47ea-a12f-4da0c9767f5d.pdf?v=1667190177).
That link is a genuine family reference, but no inspected source binds its MPN to the selected
blue-base Deep Sea seller lot. Similarly, the normal-height Deep Sea Box/Pro data must not be applied
to this low-profile selection merely because the marketing names overlap.

## Search boundary and closure evidence

All three original AliExpress URLs failed in the browser reader on this pass; existing original seller
image caches were used explicitly. Manufacturer-domain searches in English and Chinese, the reachable
TTC product page, Kailh store product/datasheet pages, and the cached selected drawings/photos produced
no exact-part dimensional closure. This is a bounded search result, not a claim that unpublished supplier
drawings cannot exist.

Closure would require a controlled drawing tied to the supplied lot (TTC blade/post/seat; Kailh exact
low-profile brown geometry), and a hat socket specification covering both selected rectangular blades
and working engagement depth. Without these, keep nominal family CAD checks separate from actual-part
qualification and report the remaining contact/fit uncertainty explicitly.
