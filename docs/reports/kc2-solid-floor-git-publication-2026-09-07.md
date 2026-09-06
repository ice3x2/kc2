# r4 Git publication checks

Requirement: `OPS-ARCH-007`, approved scoped publication and raw-byte preservation clauses.

Before publication, all294 release-bound files were compared against the staged Git blobs using raw SHA-256. All eight sealed r4 package files were also compared byte-for-byte with their staged contents. Result: no errors.

The reviewed pre-publication tree `651a7ebbaa1fa3be6a1a40391d4f116b1304d10e` was exported with `git archive` into a separate temporary checkout. The package's source-bound validator and independent ZIP/output checks ran against that exported directory: `eligible_to_build=true`, `errors=[]`,294 bindings present. This tree identifier precedes addition of this publication report; it is not asserted to be the final commit identifier.

## Failure found and corrected

The initial Git-preservation tests failed for newline filtering and scratch-file exclusion, then passed after `.gitattributes`/`.gitignore` changes. The first actual index/export audit additionally exposed previously cached normalized blobs and one unprotected adapter manifest. All294 bound paths now have `text` explicitly unset. Their current raw bytes were staged as Git objects, preserving existing file modes, without rewriting the working files or changing sealed evidence hashes. The repeated index and exported-checkout audits passed.

The selected left/right UF2 files are included even though general firmware build/output caches remain ignored. Scratch directories, editor history and backup copies are excluded. Three unrelated tracked local modifications remain outside this commit: the old X2 `.kicad_prl`, `kiwi/.status.json`, and the existing generator `.pyc` cache.

The current source/package verification still reports `first_order_ready=true`, `physical_qualification_complete=false`, `errors=[]`. The previous r3 sealed manifest remains SHA-256 `39926547bfcb4968fc116920869b9aa0b44c862b9c4e09f1af288f32dbfc833d`; its eight-file sealed package check also passes. No order, payment or PCBA upload was performed.

See [root order.md](../../order.md) for the exact PCB ZIPs and print files, and [independent final package review](kc2-solid-floor-final-package-review-2026-09-07.md) for the8-file/30-payload/294-binding audit. Physical socket, printed-part, adhesive, power/thermal and RF qualification remains post-receipt work.
