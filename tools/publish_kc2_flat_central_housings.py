"""CON-ARCH-006 publish/verify the flat non-interlocking lower seam revision."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil


ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(".codex-tmp/flat-central-revision")
PARENT = Path("hardware/MODELS/kc2_registered_housing_manifest.json")
MANIFEST = Path("hardware/MODELS/kc2_flat_central_housing_manifest.json")
REPORT = Path("docs/reports/flat-central-seam-20260914")
LABELS = ("left:normal", "left:magnetic", "right:normal", "right:magnetic")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lower_inventory():
    result = {}
    for side in ("left", "right"):
        for magnetic in (False, True):
            kind = "magnetic" if magnetic else "normal"
            folder = STAGE / "lower" / (side + "-" + kind)
            base = f"kc2_{side}_lower_housing"
            suffix = "_magnetic" if magnetic else ""
            names = [base + suffix + extension for extension in (".step", ".f3d")]
            if side == "left":
                names.append(base + suffix + ".stl")
            else:
                names.extend(base + "_part_" + part + suffix + ".stl" for part in ("a", "b"))
            for name in names:
                result[(Path("hardware/MODELS") / name).as_posix()] = (folder / name).as_posix()
    return result


def evidence_inventory():
    result = {
        REPORT / "generation.json": STAGE / "generation.json",
        REPORT / "controller-magnet-feasibility.json": STAGE / "controller-magnet-feasibility.json",
        REPORT / "independent-review.json": STAGE / "independent-review.json",
        REPORT / "native-generation.json": STAGE / "native-generation.json",
        REPORT / "native-review.json": STAGE / "native-review.json",
        REPORT / "regressions.json": STAGE / "regressions.json",
    }
    for label in LABELS:
        folder = Path("lower") / label.replace(":", "-")
        result[REPORT / folder / "generation.json"] = STAGE / folder / "generation.json"
        result[REPORT / folder / "native-generation.json"] = STAGE / folder / "native-generation.json"
    return {target.as_posix(): source.as_posix() for target, source in result.items()}


def _read_records(root):
    root = Path(root)
    return {
        "generation": json.loads((root / STAGE / "generation.json").read_text()),
        "feasibility": json.loads((root / STAGE / "controller-magnet-feasibility.json").read_text()),
        "independent": json.loads((root / STAGE / "independent-review.json").read_text()),
        "native_generation": json.loads((root / STAGE / "native-generation.json").read_text()),
        "native_review": json.loads((root / STAGE / "native-review.json").read_text()),
    }


def validate_evidence(records):
    errors = []
    generation = records.get("generation", {})
    feasibility = records.get("feasibility", {})
    independent = records.get("independent", {})
    native_generation = records.get("native_generation", {})
    native_review = records.get("native_review", {})
    if generation.get("status") != "generated_pending_independent_review" or generation.get("errors"):
        errors.append("staged generation incomplete")
    if generation.get("controller_magnet_pair_added") is not False:
        errors.append("unreviewed controller magnet pair")
    if (feasibility.get("status") != "pass_no_safe_candidate" or feasibility.get("errors") or
            feasibility.get("selected") is not None or feasibility.get("added_pair") is not False or
            feasibility.get("wall_expansion_required") is not True):
        errors.append("unsafe or ambiguous controller magnet fallback")
    if (independent.get("status") != "pass" or independent.get("errors") or
            independent.get("controller_magnet_pair_added") is not False or
            set(independent.get("rows", {})) != set(LABELS)):
        errors.append("independent STEP/STL review incomplete")
    native_outputs = native_generation.get("outputs", {})
    if (native_generation.get("status") != "pass" or native_generation.get("errors") or
            set(native_outputs) != set(LABELS) or any(
                row.get("status") != "pass" or row.get("round_trip_verified") is not True
                for row in native_outputs.values())):
        errors.append("Fusion-native generation incomplete")
    native_rows = native_review.get("rows", {})
    if (native_review.get("status") != "pass" or native_review.get("errors") or
            set(native_rows) != set(LABELS) or any(row.get("status") != "pass" for row in native_rows.values())):
        errors.append("independent native review incomplete")
    return errors


def build_manifest(root=ROOT):
    root = Path(root).resolve(); records = _read_records(root)
    errors = validate_evidence(records)
    if errors: raise ValueError("; ".join(errors))
    parent_path = root / PARENT; parent = json.loads(parent_path.read_text())
    if parent.get("status") != "digitally_verified_physical_pending":
        raise ValueError("Wrong parent publication")
    lower = lower_inventory(); outputs = {}
    for name, expected in parent.get("outputs", {}).items():
        if name not in lower:
            if digest(root / name) != expected: raise ValueError("Changed retained upper: " + name)
            outputs[name] = expected
    if len(outputs) != 21: raise ValueError("Wrong retained upper inventory")
    for target, source in lower.items():
        outputs[target] = digest(root / source)
    if len(outputs) != 35: raise ValueError("Wrong complete CAD inventory")
    preserved = parent.get("preserved_pcb_gerber_sha256", {})
    if len(preserved) != 16 or any(digest(root / name) != sha for name, sha in preserved.items()):
        raise ValueError("Ordered PCB/Gerber bytes changed")
    evidence = {target: digest(root / source) for target, source in evidence_inventory().items()}
    code = [
        "tools/kc2_flat_central_revision.py", "tools/test_kc2_flat_central_revision.py",
        "tools/stage_kc2_flat_central_revision.py", "tools/test_stage_kc2_flat_central_revision.py",
        "tools/review_kc2_controller_magnet_feasibility.py", "tools/test_review_kc2_controller_magnet_feasibility.py",
        "tools/review_kc2_flat_central_revision.py", "tools/test_review_kc2_flat_central_revision.py",
        "tools/kc2_flat_central_native.py", "tools/test_kc2_flat_central_native.py",
        "tools/review_kc2_flat_central_native.py", "tools/publish_kc2_flat_central_housings.py",
        "tools/test_publish_kc2_flat_central_housings.py",
        "tools/fusion/KC2FlatCentralToF3D/KC2FlatCentralToF3D.py",
        "tools/fusion/KC2FlatCentralToF3D/KC2FlatCentralToF3D.manifest",
    ]
    return dict(
        status="digitally_verified_physical_pending", requirement_ids=["CON-ARCH-006", "CON-ARCH-007", "OPS-ARCH-006"],
        parent_manifest=PARENT.as_posix(), parent_manifest_sha256=digest(parent_path),
        outputs=outputs, changed_lower_sha256={name: outputs[name] for name in lower},
        retained_upper_sha256={name: sha for name, sha in outputs.items() if name not in lower},
        preserved_pcb_gerber_sha256=preserved, evidence_sha256=evidence,
        documents_sha256={name: digest(root / name) for name in (
            "hardware/MODELS/README.md", "hardware/MODELS/PRINT-flat-central-housings.md",
            "docs/reports/flat-central-seam-20260914/README.md", "order.md")},
        source_sha256={name: digest(root / name) for name in code},
        central_join=dict(mechanical_interlocks=0, flat_noncontact_seam=True,
                          removed_guide_y_mm=[95.0, 117.0]),
        magnets=dict(existing_pairs_y_mm=[103.0, 111.0], controller_side_pair_added=False,
                     outcome="not added: safe material reserve and attraction gap cannot both be met without wall expansion",
                     pocket_diameter_mm=2.4, pocket_depth_mm=1.2),
        verify_command="python -B -m tools.publish_kc2_flat_central_housings --verify hardware/MODELS/kc2_flat_central_housing_manifest.json",
        physical_qualified=False,
    )


def publish(root=ROOT):
    root = Path(root).resolve(); manifest = build_manifest(root)
    for target, source in {**lower_inventory(), **evidence_inventory()}.items():
        destination = root / target; destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".publishing")
        shutil.copy2(root / source, temporary); os.replace(temporary, destination)
    path = root / MANIFEST; temporary = path.with_name(path.name + ".publishing")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(temporary, path)
    verify(root, path)
    return manifest


def verify(root=ROOT, manifest_path=None):
    root = Path(root).resolve(); path = Path(manifest_path or root / MANIFEST)
    if not path.is_absolute(): path = root / path
    manifest = json.loads(path.read_text())
    if (manifest.get("status") != "digitally_verified_physical_pending" or
            manifest.get("physical_qualified") is not False or
            len(manifest.get("outputs", {})) != 35 or
            set(manifest.get("requirement_ids", [])) != {"CON-ARCH-006", "CON-ARCH-007", "OPS-ARCH-006"}):
        raise ValueError("Invalid current flat-seam manifest")
    for field in ("outputs", "preserved_pcb_gerber_sha256", "evidence_sha256", "source_sha256", "documents_sha256"):
        for name, expected in manifest.get(field, {}).items():
            if digest(root / name) != expected: raise ValueError("Published byte differs: " + name)
    if manifest.get("magnets", {}).get("controller_side_pair_added") is not False:
        raise ValueError("Unexpected controller magnet pair")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--publish", action="store_true"); group.add_argument("--verify")
    arguments = parser.parse_args()
    result = publish() if arguments.publish else verify(ROOT, arguments.verify)
    print(json.dumps({"status": result["status"], "outputs": len(result["outputs"]),
                      "controller_magnet_pair_added": result["magnets"]["controller_side_pair_added"]}))
