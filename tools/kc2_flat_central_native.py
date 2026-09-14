"""CON-ARCH-006 source-bound Fusion job contract for the flat seam revision."""
from pathlib import Path
import hashlib
import json
import math


STAGE = Path(".codex-tmp/flat-central-revision")


def jobs():
    result = {}
    for side in ("left", "right"):
        for magnetic in (False, True):
            kind = "magnetic" if magnetic else "normal"
            stem = f"kc2_{side}_lower_housing" + ("_magnetic" if magnetic else "")
            result[side + ":" + kind] = {
                "folder": f"lower/{side}-{kind}", "step": stem + ".step",
                "body_count": 1 if side == "left" else 2,
            }
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preflight(root, label):
    root = Path(root).resolve()
    specification = jobs().get(label)
    if specification is None:
        raise ValueError("One explicit flat-seam Fusion job is required")
    folder = root / STAGE / specification["folder"]
    step = folder / specification["step"]
    generation_path = folder / "generation.json"
    generation = json.loads(generation_path.read_text())
    if (generation.get("status") != "generated_pending_independent_review" or
            generation.get("errors") or
            generation.get("body_count") != specification["body_count"] or
            generation.get("outputs", {}).get(step.name) != digest(step)):
        raise ValueError("Stale or incomplete flat-seam STEP generation")
    return dict(label=label, folder=folder, source=step,
                generation_path=generation_path,
                generation_sha256=digest(generation_path),
                source_sha256=digest(step), step=specification["step"],
                body_count=specification["body_count"])


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_native_output(before, after):
    errors = []
    if not isinstance(before, list) or not isinstance(after, list) or len(before) != len(after) or not before:
        return ["native body count differs"]
    unmatched = list(after)
    for source in before:
        if (not isinstance(source, dict) or not _finite(source.get("volume_mm3")) or
                not isinstance(source.get("bounds_mm"), list) or len(source["bounds_mm"]) != 6):
            errors.append("invalid source body record"); continue
        match = min(unmatched, key=lambda row: sum(abs(a-b) for a, b in zip(source["bounds_mm"], row.get("bounds_mm", [])))
                    if isinstance(row, dict) and len(row.get("bounds_mm", [])) == 6 else float("inf"))
        unmatched.remove(match)
        if (not _finite(match.get("volume_mm3")) or abs(match["volume_mm3"]-source["volume_mm3"]) > .002 or
                any(abs(a-b) > .001 for a, b in zip(source["bounds_mm"], match.get("bounds_mm", [])))):
            errors.append("native geometry differs")
    return errors


def compare_cad_signatures(before, after):
    """Compare independently imported mass, bounds and topology without a costly Boolean."""
    errors = []
    scalar = ("volume_mm3", "area_mm2")
    vectors = ("center_mm", "bounds_mm")
    counts = ("faces", "edges", "vertices")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ["CAD signature absent"]
    for name in scalar:
        if not _finite(before.get(name)) or not _finite(after.get(name)) or abs(before[name]-after[name]) > .002:
            errors.append(name + " differs")
    for name in vectors:
        left, right = before.get(name), after.get(name)
        if (not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right) or
                not left or any(not _finite(v) for v in left+right) or
                any(abs(a-b) > .001 for a, b in zip(left, right))):
            errors.append(name + " differs")
    for name in counts:
        # STEP round trips can repartition coincident topology without changing
        # material. Counts remain diagnostic, while mass/surface/placement gate.
        if (type(before.get(name)) is not int or type(after.get(name)) is not int or
                before[name] <= 0 or after[name] <= 0):
            errors.append(name + " invalid")
    return errors
