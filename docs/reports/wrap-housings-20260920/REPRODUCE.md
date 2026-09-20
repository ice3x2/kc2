# Rebuild and verify the sleeve models

Requirements: CON-ARCH-006, OPS-ARCH-006. Use the release commit containing
the final `kc2_wrap_housing_manifest.json`, not an intermediate working tree.

Do not run the generator against already-replaced canonical models. It is an
additive revision of the exact baseline at Git `e0e8686`; its source checks
intentionally reject a different baseline. Do not bypass those checks or
replace expected hashes merely to make regeneration run.

## Isolated working tree

Create a separate disposable Git worktree at the baseline, outside the active
repository. Keep its canonical `hardware/PCB`, `hardware/GERBER` and
`hardware/MODELS` files at that baseline. Bring only `tools/`, `docs/spec/`
and this report's documentation from the final sleeve release commit into
the new worktree. Do not restore the new release's `hardware/MODELS` there:
those are outputs, not the required baseline inputs.

Use Python 3.12 with `requirements-cad.txt`, the existing KiCad Python runtime
used by the board-envelope extractor, and an installed Fusion application.
The mesh reviewers additionally require Trimesh and NumPy; this run used
Trimesh 5.1.0 and NumPy 2.4.1. Matplotlib is needed only for preview plots.
Run commands from the isolated worktree root:

```powershell
python -B -m tools.extract_kc2_wrap_envelopes
python -B -m tools.stage_kc2_wrap_housings plan
```

Generate each combination of `left`/`right` and
`normal`/`magnetic`/`mx`/`choc_v1`/`deep_sea` once. For example:

```powershell
python -B -m tools.build_kc2_wrap_housings left normal
```

Use the `build` wrapper, not the lower-level `stage ... left normal` command:
the wrapper performs the lossless conforming binary-STL edge repair. Do not
change hash-bound generator files or `plan.json` while jobs are running.
Inspect exit status and `generation.json`, not just the presence of a STEP.

## Actual outputs

Run both independent actual-output reviews. Missing jobs, stale sources,
invalid meshes or interference are failures, not release waivers:

```powershell
python -B -m tools.review_kc2_wrap_housings
python -B -m tools.review_kc2_wrap_cad
python -B -m tools.review_kc2_wrap_motion
```

The CAD reviewer can retain a completed job checkpoint only when its actual
STEP, generation record, plan and auditor dependencies are byte-identical.
Incomplete runs do not produce a passing full assembly report.
The motion review separately checks continuous vertical insertion using
height-bounded, near-prismatic actual mesh layers with an explicit outward
roundoff allowance, plus conservative A/B and horizontal-approach projections.

For Fusion, execute `tools/fusion/KC2WrapHousings.py` in Fusion's Python
console. Before calling `run()`, explicitly set its global `ROOT` to the
isolated worktree's absolute `Path`, rather than the default original repo.
It imports STEP, writes a real F3D, reopens that archive, and exports a
readback STEP. `run()` processes all ten jobs. Explicit batches are allowed,
but the master remains `partial` until all ten current jobs pass.

Then run:

```powershell
python -B -m tools.review_kc2_wrap_native
```

Refresh regression evidence with `python -B -m tools.run_kc2_wrap_tests`.
Its exact module list is recorded in `tests.json`; copying a previous passing
result is not evidence.
Native archives and STEP headers need not reproduce identical serialized
bytes across application versions. Compare actual geometry with the recorded
volume/area/placement tolerances and produce a new source-bound evidence chain.

## Publication

Do not publish a partial rebuild over the active project. All ten CAD jobs,
fifteen STL files, native readbacks, full mesh/CAD/native reports and current
tests must pass together. The final guide and entry-point documentation must
also be finalized. Only then is `tools.publish_kc2_wrap_housings --publish`
applicable to that reviewed worktree. Without `--publish` it verifies an
existing release and does not replace files.

Publication normalizes only outside-token trailing ASCII STEP whitespace,
retains all raw source STEP files under `raw-step/`, and records the exact
lexical proof. Source bindings resolve to raw evidence, not to normalized
canonical STEP. Native readback and F3D bytes are retained unchanged.
The old plan's unused local autosave/editor/history inventory is a hash-only
preservation observation, not a required rebuild input. A clean worktree need
not recreate it. All actual boards, projects and geometry code remain bound.

The normal portable release verifier uses committed evidence aliases and the
Git baseline; it does not require `.codex-tmp`. Physical print qualification
remains separate. Never change the ordered PCB/Gerber bytes for a housing rebuild.
