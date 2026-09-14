"""CON-ARCH-006 controller-side magnet search; no geometry is written."""
from pathlib import Path
import hashlib
import json
import math

from shapely.geometry import LineString

from tools.generate_kc2_magnetic_housings import load_plans, safe_pocket
from tools.kc2_flat_central_revision import (
    CONTROLLER_MAX_Y, MAX_MAGNET_FACE_GAP, choose_controller_magnet,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".codex-tmp/flat-central-revision/controller-magnet-feasibility.json"
STEP = .1


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(row):
    errors = []
    if row.get("errors") != [] or row.get("physical_qualified") is not False:
        errors.append("Wrong status fields")
    status = row.get("status")
    if status == "pass_no_safe_candidate":
        if row.get("selected") is not None or row.get("safely_aligned_candidates") != []:
            errors.append("Safe candidate contradiction")
        near = row.get("actual_near_misses")
        if not isinstance(near, list) or len(near) < 2:
            errors.append("Actual near-miss evidence absent")
        elif any(not isinstance(v.get("reserve_missing_left_mm3"), (int, float)) or
                 not isinstance(v.get("reserve_missing_right_mm3"), (int, float)) or
                 max(v["reserve_missing_left_mm3"], v["reserve_missing_right_mm3"]) <= 0
                 for v in near):
            errors.append("Near miss does not prove missing reserve")
        if row.get("wall_expansion_required") is not True or row.get("added_pair") is not False:
            errors.append("Unsafe fallback was not retained")
    elif status == "pass_safe_candidate":
        if (not isinstance(row.get("selected"), dict) or row.get("added_pair") is not True or
                row.get("wall_expansion_required") is not False or
                row["selected"] not in row.get("safely_aligned_candidates", [])):
            errors.append("Selected safe candidate was not implemented")
    else:
        errors.append("Unknown feasibility status")
    return errors


def _reserve(shape, side, y):
    import cadquery as cq
    # Radius 1.70 = bore radius 1.20 + required 0.50 radial web.
    # Axial 1.80 = pocket depth 1.20 + required 0.60 back wall.
    x, sign = (.1, 1) if side == "left" else (149.3, -1)
    tool = cq.Solid.makeCylinder(1.7, 1.8, cq.Vector(x, y, .75), cq.Vector(sign, 0, 0))
    return tool.cut(shape).Volume(), tool.Volume()


def review():
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import DIAMETER, DEPTH, BACK_WALL
    plans, old_candidates, transform = load_plans()
    aligned = []
    rejected = []
    forbidden = {}
    from tools import generate_kc2_x3_v2_housings as base
    shp = base.legacy_geometry.require_shapely()
    for side, p in plans.items():
        forbidden[side] = (p["mounting_land_geometry"].union(base._support_plan_union(shp, p["support_posts"]))
                           .union(p["reset_local_support_geometry"]))
    for index in range(int((CONTROLLER_MAX_Y - 31.0) / STEP) + 1):
        y = round(31.0 + index * STEP, 10)
        candidate = dict(y=y)
        for side, sign in (("left", 1), ("right", -1)):
            p = plans[side]
            section = p["housing_outline"].intersection(LineString([(-10, y), (220, y)]))
            if section.is_empty:
                break
            x = section.bounds[0 if side == "left" else 2]
            if not safe_pocket(p["support_surface"], forbidden[side], x, y, sign):
                break
            candidate[side] = dict(x=x, y=y, sign=sign)
        if "left" in candidate and "right" in candidate:
            gap = (plans["right"]["raw_bounds"][2] - candidate["right"]["x"] + transform["dx"]
                   - plans["left"]["raw_bounds"][2] + candidate["left"]["x"])
            candidate["face_gap_mm"] = gap + 2 * (DEPTH - 1.0)
            measurements = dict(y=y, face_gap_mm=candidate["face_gap_mm"],
                reserve_missing_left_mm3=0.0, reserve_missing_right_mm3=0.0,
                forbidden_left_mm2=0.0, forbidden_right_mm2=0.0)
            if choose_controller_magnet([measurements]) is not None:
                aligned.append(measurements)
            else:
                rejected.append(candidate)
    shapes = {side: cq.importers.importStep(str(ROOT/f"hardware/MODELS/kc2_{side}_lower_housing.step")).val()
              for side in ("left", "right")}
    near = []
    for y in (92.0, CONTROLLER_MAX_Y):
        lm, lv = _reserve(shapes["left"], "left", y)
        rm, rv = _reserve(shapes["right"], "right", y)
        near.append(dict(y=y, reserve_missing_left_mm3=lm,
                         reserve_missing_right_mm3=rm,
                         reserve_volume_left_mm3=lv,
                         reserve_volume_right_mm3=rv))
    selected = choose_controller_magnet(aligned)
    remote = [dict(y=c["y"], face_gap_mm=c["gap"] + 2*(DEPTH-1.0))
              for c in old_candidates if c["y"] <= 28.0]
    sources = [Path(__file__), ROOT/"tools/test_review_kc2_controller_magnet_feasibility.py",
               ROOT/"tools/kc2_flat_central_revision.py",
               ROOT/"tools/test_kc2_flat_central_revision.py",
               ROOT/"tools/generate_kc2_magnetic_housings.py",
               ROOT/"hardware/MODELS/kc2_left_lower_housing.step",
               ROOT/"hardware/MODELS/kc2_right_lower_housing.step",
               ROOT/"hardware/PCB/kc2_left/kc2_left.kicad_pcb",
               ROOT/"hardware/PCB/kc2_right/kc2_right.kicad_pcb"]
    result = dict(status="pass_safe_candidate" if selected else "pass_no_safe_candidate",
                  errors=[], requirements=["CON-ARCH-006", "CON-ARCH-007"],
                  selected=selected, controller_y_range_mm=[31.0, CONTROLLER_MAX_Y],
                  search_step_mm=STEP, safely_aligned_candidates=aligned,
                  rejected_aligned_candidates=rejected, remote_candidates=remote,
                  actual_near_misses=near, wall_expansion_required=selected is None,
                  added_pair=selected is not None, diameter_mm=DIAMETER,
                  depth_mm=DEPTH, radial_web_reserve_mm=.5,
                  back_wall_reserve_mm=BACK_WALL, center_z_mm=.75,
                  source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in sources},
                  physical_qualified=False,
                  conclusion=("one controller-side pair is safe" if selected else
                              "no pair added: safe reserve and attraction gap cannot both be met without geometry expansion"))
    result["errors"] = validate(result)
    result["status"] = ("fail" if result["errors"] else result["status"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({k: result[k] for k in ("status", "errors", "selected", "conclusion")}))
    return result


if __name__ == "__main__":
    outcome = review()
    raise SystemExit(outcome["status"] == "fail")
