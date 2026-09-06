# V1-inclusive documentation regression update

Requirements: `CON-ARCH-004`, `OPS-ARCH-007`. Date: 2026-09-06.

The canonical hardware README now describes four mutually exclusive assembly modes, preserves the
selected TTC 3-pin MX and Kailh Deep Sea brown choices, identifies the newly supported V1 locator/ring
assembly, and retains ORDER HOLD. The old readiness headline was replaced so that it cannot contradict
the hold banner. Current route counts and digests are read from the canonical schema-2 replay:

- Left: 876 track/via items; `ccc6190a8f46e251261c6ef981fda11bd6524fc547ca358be1cde63a10ad2da3`.
- Right: 1089 items; `aa78af58190800870654a15ce6f772aea41a806705bb645597ed93b9ef0ac533`.

## Index update mechanism

SpecKiwi CLI has no custom index-summary row mutation. `sync-index --help` and its installed
`dist/core/mutation/sync-index.js` implementation were inspected: it changes only Status Summary and
Requirement Type Summary. `edit-requirement-table-rows` is limited to a requirement's verification
evidence or trace links. Therefore the coordinating agent authorized a narrow `apply_patch` fallback
for derived index summary text only, rather than leaving known-stale current-route/readiness claims.
No Requirement ID, acceptance criterion, lifecycle status or stability was manually changed.

The index now distinguishes current 876/1089 V1-inclusive routing from historical 616/803 and 738/949
revisions. Housing regeneration and revised release review remain in progress, not passed. Sealed old
fabrication packages were not edited.

## Regression evidence

The two formerly stale documentary tests pass against the new canonical boards and snapshot:
`.codex-tmp/doc-regression-v1-focused.log`, 2 tests, 0.309 seconds, OK. They check exact actual pad/route
capture, current route digest documentation, historical provenance and replay hash; firmware and
post-receipt qualification checks remain intact.

The full two-module rerun in `.codex-tmp/doc-regression-v1-full-modules.log` completed with
**98 tests passing in 194.744 seconds**, final unittest result `OK`. PowerShell reports wrapper exit 1
because native KiCad emits stderr warnings; the actual test summary has no failures or errors.
This report does not mark hardware or physical requirements verified.
