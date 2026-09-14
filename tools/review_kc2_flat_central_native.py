"""CON-ARCH-006 independent BRep review of Fusion F3D readback outputs."""
from pathlib import Path
import json

from tools.kc2_flat_central_native import (
    jobs, preflight, digest, validate_native_output, compare_cad_signatures,
)


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".codex-tmp/flat-central-revision"


def _signature(solid):
    box = solid.BoundingBox(); center = solid.Center()
    return dict(volume_mm3=solid.Volume(), area_mm2=solid.Area(),
                center_mm=[center.x, center.y, center.z],
                bounds_mm=[box.xmin, box.ymin, box.zmin, box.xmax, box.ymax, box.zmax],
                faces=len(solid.Faces()), edges=len(solid.Edges()), vertices=len(solid.Vertices()))


def review():
    import cadquery as cq
    master_path = STAGE / "native-generation.json"
    master = json.loads(master_path.read_text())
    if master.get("status") != "pass" or master.get("errors") or set(master.get("outputs", {})) != set(jobs()):
        raise ValueError("Incomplete Fusion-native generation")
    rows = {}; errors = []; bindings = {
        master_path.relative_to(ROOT).as_posix(): digest(master_path),
        Path(__file__).relative_to(ROOT).as_posix(): digest(__file__),
        "tools/kc2_flat_central_native.py": digest(ROOT / "tools/kc2_flat_central_native.py"),
        "tools/test_kc2_flat_central_native.py": digest(ROOT / "tools/test_kc2_flat_central_native.py"),
        "tools/fusion/KC2FlatCentralToF3D/KC2FlatCentralToF3D.py": digest(
            ROOT / "tools/fusion/KC2FlatCentralToF3D/KC2FlatCentralToF3D.py"),
    }
    for label in jobs():
        job = preflight(ROOT, label); folder = job["folder"]
        native_path = folder / "native-generation.json"
        native = json.loads(native_path.read_text()); output = master["outputs"][label]
        if native != output or native.get("status") != "pass" or not native.get("round_trip_verified"):
            raise ValueError("Native record chain differs: " + label)
        f3d = folder / native["f3d"]; readback = folder / native["readback_step"]
        for path in (job["source"], job["generation_path"], native_path, f3d, readback):
            bindings[path.relative_to(ROOT).as_posix()] = digest(path)
        if (native["source_sha256"] != job["source_sha256"] or
                native["generation_sha256"] != job["generation_sha256"] or
                native["f3d_sha256"] != digest(f3d) or native["readback_sha256"] != digest(readback)):
            raise ValueError("Stale native hash chain: " + label)
        source = cq.importers.importStep(str(job["source"])).solids().vals()
        revised = cq.importers.importStep(str(readback)).solids().vals()
        if len(source) != job["body_count"] or len(revised) != job["body_count"]:
            raise ValueError("Native body count differs: " + label)
        unmatched = list(revised); parts = []
        for index, solid in enumerate(source):
            actual = min(unmatched, key=lambda other: (other.Center()-solid.Center()).Length)
            unmatched.remove(actual)
            print("native independent CAD signature", label, index, flush=True)
            source_signature = _signature(solid); actual_signature = _signature(actual)
            part_errors = compare_cad_signatures(source_signature, actual_signature)
            parts.append(dict(part=index, source=source_signature, readback=actual_signature,
                              errors=part_errors))
            errors.extend(label + ": " + error for error in part_errors)
        identity_errors = validate_native_output(native["source_bodies"], native["reopened_bodies"])
        errors.extend(label + ": " + error for error in identity_errors)
        rows[label] = dict(status="pass" if not identity_errors and not any(p["errors"] for p in parts) else "failed",
                           errors=identity_errors, parts=parts, f3d_sha256=digest(f3d),
                           readback_sha256=digest(readback))
    result = dict(status="pass" if not errors else "failed", errors=errors,
                  requirements=["CON-ARCH-006", "OPS-ARCH-006"], rows=rows,
                  source_sha256=bindings, physical_qualified=False)
    (STAGE / "native-review.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "errors": errors}), flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(0 if review()["status"] == "pass" else 1)
