"""CON-ARCH-006 subtractive flat-seam revision, never a canonical writer."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

from tools.kc2_flat_central_revision import flat_join_cutters


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".codex-tmp/flat-central-revision"
VOLUME_TOLERANCE = .002
BASELINE = "5b99bcb4567ea1c6bb4f17e54887d4de7614cd03"
CURRENT = "03b9135b42c0de5730d1c67228ec858b08f3facb"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _solid_box(row):
    import cadquery as cq
    return cq.Workplane("XY").box(row["x1"]-row["x0"],
                                  row["plan"].bounds[3]-row["plan"].bounds[1],
                                  row["z1"]-row["z0"], centered=False).val().translate(
        (row["x0"], row["plan"].bounds[1], row["z0"]))


def cut_tools(side):
    return [_solid_box(row) for row in flat_join_cutters(side)]


def apply_flat_join(shape, side):
    result = shape.cut(*cut_tools(side)).clean()
    if not result.isValid() or len(result.Solids()) != len(shape.Solids()):
        raise ValueError("Flat join removal disconnected housing")
    return result


def _difference_volume(left, right):
    return left.cut(right).Volume()


def audit_flat_join(before, after, side, allowed_guide, baseline):
    errors = []
    valid = after.isValid() and len(after.Solids()) == len(before.Solids()) and len(after.Solids()) > 0
    if not valid:
        errors.append("Invalid/disconnected flat housing")
        return dict(errors=errors, removed_mm3=None, added_mm3=None,
                    off_guide_removed_mm3=None, baseline_removed_mm3=None,
                    remaining_protrusion_mm3=None)
    removed = before.cut(after)
    added = after.cut(before)
    off = _difference_volume(removed, allowed_guide) if removed.Volume() > 1e-9 else 0.0
    # Attribute only material removed by this operation. Historical stock can
    # already differ because of separately approved receiver/clearance relief.
    baseline_removed = removed.intersect(baseline).Volume()
    remaining = sum(after.intersect(tool).Volume() for tool in cut_tools(side))
    values = dict(removed_mm3=removed.Volume(), added_mm3=added.Volume(),
                  off_guide_removed_mm3=off, baseline_removed_mm3=baseline_removed,
                  remaining_protrusion_mm3=remaining)
    if values["removed_mm3"] <= VOLUME_TOLERANCE:
        errors.append("No former guide material removed")
    for name in ("added_mm3", "off_guide_removed_mm3", "baseline_removed_mm3",
                 "remaining_protrusion_mm3"):
        if values[name] > VOLUME_TOLERANCE:
            errors.append(name)
    return dict(errors=errors, **values)


def audit_magnetic_preservation(normal_before, magnetic_before,
                                normal_after, magnetic_after):
    """Require the complete magnetic subtraction to remain byte-independent geometry."""
    old_removed = normal_before.cut(magnetic_before)
    new_removed = normal_after.cut(magnetic_after)
    old_missing = old_removed.cut(new_removed).Volume()
    unexpected = new_removed.cut(old_removed).Volume()
    errors = []
    if old_missing > VOLUME_TOLERANCE:
        errors.append("Existing magnetic removal lost")
    if unexpected > VOLUME_TOLERANCE:
        errors.append("Unapproved magnetic removal added")
    return dict(errors=errors, old_removed_mm3=old_removed.Volume(),
                new_removed_mm3=new_removed.Volume(),
                old_missing_mm3=old_missing,
                unexpected_new_mm3=unexpected)


def _git_blob(name):
    return subprocess.check_output(["git", "show", BASELINE+":"+name], cwd=ROOT)


def _guide_reference(side):
    import cadquery as cq
    files = [ROOT/f"docs/reports/registered-housing-fit-20260913/evidence/central/{side}-central-y{y}.step"
             for y in (95, 117)]
    solids = [s for path in files for s in cq.importers.importStep(str(path)).solids().vals()]
    return cq.Compound.makeCompound(solids), files


def _export_mesh(shape, path):
    import cadquery as cq
    from tools.kc2_stl_zero_area_filter import normalize
    from tools.generate_kc2_magnetic_housings import inspect_mesh
    cq.exporters.export(shape, str(path), tolerance=.005, angularTolerance=.08)
    clean, record = normalize(path.read_bytes())
    path.write_bytes(clean)
    return inspect_mesh(path, shape), record


def generate():
    """Generate four lower jobs from the immutable current publication."""
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import bounds
    feasibility_path = STAGE/"controller-magnet-feasibility.json"
    feasibility = json.loads(feasibility_path.read_text())
    if feasibility.get("status") not in ("pass_no_safe_candidate", "pass_safe_candidate") or feasibility.get("errors"):
        raise ValueError("Controller magnet feasibility is not complete")
    if feasibility.get("selected") is not None:
        raise ValueError("Safe candidate implementation needs an explicit reviewed cutter; none expected in this revision")
    manifest_path = ROOT/"hardware/MODELS/kc2_registered_housing_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "digitally_verified_physical_pending":
        raise ValueError("Wrong current publication baseline")
    results = {}; before_shapes = {}; after_shapes = {}
    code = [Path(__file__), ROOT/"tools/test_stage_kc2_flat_central_revision.py",
            ROOT/"tools/kc2_flat_central_revision.py", ROOT/"tools/test_kc2_flat_central_revision.py",
            ROOT/"tools/kc2_stl_zero_area_filter.py", ROOT/"tools/test_kc2_stl_zero_area_filter.py",
            ROOT/"tools/review_kc2_controller_magnet_feasibility.py",
            ROOT/"tools/test_review_kc2_controller_magnet_feasibility.py",
            feasibility_path, manifest_path]
    for side in ("left", "right"):
        allowed, guide_paths = _guide_reference(side)
        for magnetic in (False, True):
            kind = "magnetic" if magnetic else "normal"
            stem = f"kc2_{side}_lower_housing" + ("_magnetic" if magnetic else "")
            print("build and audit", side, kind, flush=True)
            source = ROOT/"hardware/MODELS"/(stem+".step")
            expected = manifest.get("outputs", {}).get(source.relative_to(ROOT).as_posix())
            if digest(source) != expected:
                raise ValueError("Current canonical lower changed: "+stem)
            folder = STAGE/"lower"/(side+"-"+kind); folder.mkdir(parents=True, exist_ok=True)
            old_path = folder/("baseline-"+stem+".step")
            old_bytes = _git_blob(source.relative_to(ROOT).as_posix()); old_path.write_bytes(old_bytes)
            before = cq.importers.importStep(str(source)).val()
            baseline = cq.importers.importStep(str(old_path)).val()
            after = apply_flat_join(before, side)
            audit = audit_flat_join(before, after, side, allowed, baseline)
            if audit["errors"]:
                raise ValueError(str(audit))
            step = folder/(stem+".step")
            print("export and reopen", side, kind, flush=True)
            cq.exporters.export(after, str(step))
            reopened = cq.importers.importStep(str(step)).val()
            if (not reopened.isValid() or len(reopened.Solids()) != len(after.Solids()) or
                    abs(reopened.Volume()-after.Volume()) > .01):
                raise ValueError("STEP round trip failed: "+stem)
            outputs = {step.name: digest(step)}; meshes=[]; filters=[]
            solids = sorted(after.Solids(), key=lambda s: s.Center().x)
            if side == "left":
                stl = folder/(stem+".stl")
                mesh, filtered = _export_mesh(solids[0], stl)
                outputs[stl.name] = digest(stl); meshes.append(mesh); filters.append(filtered)
            else:
                for index, solid in enumerate(solids):
                    stl = folder/(stem.replace("_magnetic", "")+"_part_"+chr(97+index)+
                                  ("_magnetic" if magnetic else "")+".stl")
                    mesh, filtered = _export_mesh(solid, stl)
                    outputs[stl.name] = digest(stl); meshes.append(mesh); filters.append(filtered)
            sources = code+[source,*guide_paths]
            report = dict(status="generated_pending_independent_review", errors=[],
                requirements=["CON-ARCH-006", "CON-ARCH-007", "OPS-ARCH-006"],
                side=side, magnetic=magnetic, baseline_revision=BASELINE,
                input_publication_revision=CURRENT, source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in sources},
                git_baseline_sha256=hashlib.sha256(old_bytes).hexdigest(),
                controller_magnet_pair_added=False,
                controller_magnet_fallback=feasibility["conclusion"],
                guide_locations_removed_y_mm=list((95.,117.)), flat_face_x_mm=flat_join_cutters(side)[0]["x1" if side=="left" else "x0"],
                preservation=audit, body_count=len(after.Solids()), bounds_mm=bounds(after),
                volume_mm3=after.Volume(), outputs=outputs, meshes=meshes,
                mesh_normalization=filters, physical_qualified=False)
            (folder/"generation.json").write_text(json.dumps(report, indent=2)+"\n")
            results[side+":"+kind] = report
            before_shapes[side+":"+kind] = before; after_shapes[side+":"+kind] = after
    magnetic = {}
    for side in ("left", "right"):
        row = audit_magnetic_preservation(before_shapes[side+":normal"], before_shapes[side+":magnetic"],
                                          after_shapes[side+":normal"], after_shapes[side+":magnetic"])
        if row["errors"]:
            raise ValueError(str(row))
        magnetic[side] = row
    master = dict(status="generated_pending_independent_review", errors=[],
                  requirements=["CON-ARCH-006", "CON-ARCH-007", "OPS-ARCH-006"],
                  jobs={label:{"report":f"lower/{label.replace(':','-')}/generation.json",
                               "outputs":row["outputs"]} for label,row in results.items()},
                  controller_magnet_feasibility=digest(feasibility_path),
                  controller_magnet_pair_added=False, magnetic_preservation=magnetic,
                  physical_qualified=False)
    (STAGE/"generation.json").write_text(json.dumps(master, indent=2)+"\n")
    print(json.dumps({"status":master["status"], "jobs":len(results),
                      "controller_magnet_pair_added":False}))
    return master


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.parse_args()
    generate()
