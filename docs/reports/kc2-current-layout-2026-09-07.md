# Post-order current-file relocation

Requirements: `OPS-ARCH-006`, `OPS-ARCH-007`; user-approved on2026-09-07.

The physical active files moved to repository-root `00_CURRENT/PCB/kc2_left`, `00_CURRENT/PCB/kc2_right`, `00_CURRENT/GERBER`, and `00_CURRENT/MODELS`. The four former directories are local compatibility junctions to the same physical files, not duplicates. The reproducible setup uses Windows junctions or non-Windows symbolic links. No protected KiCad filename/internal identity or file content was edited; project-relative library depth remains three levels to the repository root. No Konnect identity rename was needed for this directory-only move.

The user reported an order was completed; supplier, order number and receipt have not been provided. This change does not place another order, revise the ordered PCB, regenerate Gerbers/CAD, or qualify physical parts.

## Evidence

- [Relocation inventory](kc2-current-layout-2026-09-07.json):53 tracked files mapped from former to new paths, raw SHA-256 recorded. Existing local backups/editor files also remain reachable through their former directory aliases; historical draft directories were not touched. Some unbound historical text/editor files differ from Git HEAD solely because existing checkout bytes are preserved, not normalized. All294 sealed release input hashes and the8-file package validate unchanged.
- TDD: the initial two tests failed before implementation. Final three tests pass, covering real canonical files, matching sealed hashes, dry-run/no mutation, setup repeatability, conflicting real directories, missing targets and invalidated aliases. Setup preflights every alias before creating any; it never replaces a conflicting directory.
- [Clean exported-tree execution](kc2-current-layout-clean-checkout-2026-09-07.json): archive of the staged tree into a new directory without `.git` or local junctions. Run setup, all3tests, exact r4 package verification and current Fusion archive verification. Every process exits0; package errors and native blockers are empty.
- Fresh DRC at the new physical PCB paths: [left](kc2-current-layout-left-2026-09-07.drc.json), [right](kc2-current-layout-right-2026-09-07.drc.json). Both commands used all severities and exit-on-violations, returned0, and found0violations/0unconnected. They did not refill/save boards or replace sealed DRC records.
- Existing MX manifest/STL checker: digital_valid=true, errors=[], native_archive_blockers=[]; physical qualification blockers remain disclosed.
- All local links in [new current guide](../../00_CURRENT/README.md) resolve. Root README now points there first. Root `order.md` is explicitly linked as the unchanged order-time document because its bytes are part of the sealed294-input review; historical logical paths remain functional after setup.

## Operational distinction

The main storage is physically under `00_CURRENT`. Old generator/verifier logical paths intentionally remain stable and reach this same storage via aliases. Run `python -B -m tools.kc2_current_layout --apply` once after a clean clone before using those tools. A source or model edit after ordering still invalidates the sealed release verification; aliases do not waive that check. Default setup is read-only. New-project generator runs are not fabrication approval and were not used to mutate this ordered revision.

Current hardware bytes are unchanged, so no new component/circuit acceptance or physical PASS is inferred from relocation. Existing unknown socket/contact, printed strength, adhesive, thermal and RF qualifications remain pending. The unrelated X2 editor state, `kiwi/.status.json` and tracked Python cache modifications remain untouched and outside this change.
