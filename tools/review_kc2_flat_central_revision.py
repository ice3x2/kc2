"""CON-ARCH-006 independent review of the actual flat-seam STEP/STL files."""
from pathlib import Path
import hashlib
import json
import math
import subprocess

from tools.kc2_flat_central_revision import flat_join_cutters


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".codex-tmp/flat-central-revision"
BASELINE = "5b99bcb4567ea1c6bb4f17e54887d4de7614cd03"
TOLERANCE = .002


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("finite measurement required")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("non-negative finite measurement required")
    return value


def evaluate(row):
    """Fail closed on topology, additive edits, or out-of-scope subtraction."""
    errors = []
    if row.get("body_count") != row.get("expected_body_count"):
        errors.append("wrong body count")
    if _finite(row.get("removed_mm3")) <= TOLERANCE:
        errors.append("former guides were not removed")
    for name in (
        "added_mm3", "off_guide_removed_mm3", "baseline_removed_mm3",
        "remaining_protrusion_mm3", "step_roundtrip_missing_mm3",
        "step_roundtrip_extra_mm3", "magnetic_missing_mm3",
        "unexpected_magnetic_mm3",
    ):
        if _finite(row.get(name)) > TOLERANCE:
            errors.append(name)
    mesh_errors = row.get("mesh_errors")
    if not isinstance(mesh_errors, list) or mesh_errors:
        errors.append("mesh topology or STEP/STL identity failed")
    return errors


def _box(row):
    import cadquery as cq
    return cq.Workplane("XY").box(
        row["x1"] - row["x0"], row["plan"].bounds[3] - row["plan"].bounds[1],
        row["z1"] - row["z0"], centered=False,
    ).val().translate((row["x0"], row["plan"].bounds[1], row["z0"]))


def _guides(side):
    import cadquery as cq
    paths = [ROOT / f"docs/reports/registered-housing-fit-20260913/evidence/central/{side}-central-y{y}.step"
             for y in (95, 117)]
    solids = [solid for path in paths for solid in cq.importers.importStep(str(path)).solids().vals()]
    return cq.Compound.makeCompound(solids), paths


def _git_sha(name):
    return hashlib.sha256(subprocess.check_output(
        ["git", "show", BASELINE + ":" + name], cwd=ROOT)).hexdigest()


def _mesh_names(side, magnetic):
    stem = f"kc2_{side}_lower_housing"
    suffix = "_magnetic" if magnetic else ""
    if side == "left":
        return [stem + suffix + ".stl"]
    return [stem + "_part_a" + suffix + ".stl", stem + "_part_b" + suffix + ".stl"]


def review():
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import inspect_mesh
    from tools.kc2_flat_central_native import compare_cad_signatures
    from tools.review_kc2_flat_central_native import _signature

    generation_path = STAGE / "generation.json"
    generation = json.loads(generation_path.read_text())
    if generation.get("status") != "generated_pending_independent_review" or generation.get("errors"):
        raise ValueError("Incomplete staged generation")
    rows = {}; all_errors = []
    bindings = {
        Path(__file__).relative_to(ROOT).as_posix(): digest(__file__),
        "tools/test_review_kc2_flat_central_revision.py": digest(ROOT / "tools/test_review_kc2_flat_central_revision.py"),
        generation_path.relative_to(ROOT).as_posix(): digest(generation_path),
    }
    for side in ("left", "right"):
        allowed, guide_paths = _guides(side)
        cutters = [_box(row) for row in flat_join_cutters(side)]
        for magnetic in (False, True):
            kind = "magnetic" if magnetic else "normal"
            label = side + ":" + kind
            stem = f"kc2_{side}_lower_housing" + ("_magnetic" if magnetic else "")
            canonical = ROOT / "hardware/MODELS" / (stem + ".step")
            folder = STAGE / "lower" / (side + "-" + kind)
            step = folder / (stem + ".step")
            baseline_path = folder / ("baseline-" + stem + ".step")
            report_path = folder / "generation.json"
            report = json.loads(report_path.read_text())
            for path in [canonical, step, baseline_path, report_path, *guide_paths]:
                bindings[path.relative_to(ROOT).as_posix()] = digest(path)
            if digest(baseline_path) != _git_sha(canonical.relative_to(ROOT).as_posix()):
                raise ValueError("Historical protection solid differs from Git")
            source = cq.importers.importStep(str(canonical)).val()
            revised = cq.importers.importStep(str(step)).val()
            expected = source.cut(*cutters).clean()
            if not revised.isValid() or not expected.isValid():
                raise ValueError("Invalid actual STEP")
            if any(digest(ROOT / name) != sha for name, sha in report.get("source_sha256", {}).items()):
                raise ValueError("Changed generation source binding: " + label)
            signature_errors = compare_cad_signatures(_signature(expected), _signature(revised))
            print("independent CAD signature and mesh", label, flush=True)
            solids = sorted(revised.Solids(), key=lambda solid: solid.Center().x)
            mesh_errors = []
            meshes = []
            for name, solid in zip(_mesh_names(side, magnetic), solids):
                path = folder / name
                bindings[path.relative_to(ROOT).as_posix()] = digest(path)
                mesh = inspect_mesh(path, solid); meshes.append(mesh)
                mesh_errors.extend(mesh.get("errors", []))
            row = dict(
                body_count=len(revised.Solids()), expected_body_count=1 if side == "left" else 2,
                removed_mm3=source.Volume()-revised.Volume(),
                added_mm3=report["preservation"]["added_mm3"],
                off_guide_removed_mm3=report["preservation"]["off_guide_removed_mm3"],
                baseline_removed_mm3=report["preservation"]["baseline_removed_mm3"],
                remaining_protrusion_mm3=sum(revised.intersect(tool).Volume() for tool in cutters),
                step_roundtrip_missing_mm3=.01 if signature_errors else 0.0,
                step_roundtrip_extra_mm3=.01 if signature_errors else 0.0,
                magnetic_missing_mm3=0.0, unexpected_magnetic_mm3=0.0,
                mesh_errors=mesh_errors+signature_errors, meshes=meshes,
                generation_output_sha256=report.get("outputs", {}).get(step.name),
                actual_step_sha256=digest(step),
            )
            row["errors"] = evaluate(row)
            rows[label] = row
    for side in ("left", "right"):
        magnetic = generation.get("magnetic_preservation", {}).get(side, {})
        missing = magnetic.get("old_missing_mm3", .01)
        unexpected = magnetic.get("unexpected_new_mm3", .01)
        for kind in ("normal", "magnetic"):
            row = rows[side + ":" + kind]
            row["magnetic_missing_mm3"] = missing
            row["unexpected_magnetic_mm3"] = unexpected
            row["errors"] = evaluate(row)
    for label, row in rows.items():
        all_errors.extend(label + ": " + error for error in row["errors"])
        if row["generation_output_sha256"] != row["actual_step_sha256"]:
            all_errors.append(label + ": staged output hash mismatch")
    result = dict(
        status="pass" if not all_errors else "failed", errors=all_errors,
        requirements=["CON-ARCH-006", "CON-ARCH-007", "OPS-ARCH-006"],
        controller_magnet_pair_added=False,
        controller_magnet_fallback="no safe aligned controller-side reserve without wall expansion",
        rows=rows, source_sha256=bindings, physical_qualified=False,
        independent_scope="fresh STEP import, expected subtractive CAD signature, remaining-window intersection and actual STL topology; full BRep subtraction is source-bound generation evidence",
    )
    (STAGE / "independent-review.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "errors": result["errors"]}), flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(0 if review()["status"] == "pass" else 1)
