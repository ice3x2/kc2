"""CON-ARCH-006 / OPS-ARCH-006 optional subtractive magnetic lower housings.

Run with the CadQuery Python: python -B -m tools.generate_kc2_magnetic_housings
Never exports to original model names or writes PCB/Gerber sources.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path

import cadquery as cq
import trimesh
from shapely.geometry import LineString, box
from tools import generate_kc2_x3_v2_housings as base

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'hardware/MODELS'
REPORT = ROOT / 'docs/reports/magnetic-20260908'
DIAMETER, DEPTH, CENTER_Z, BACK_WALL = 2.4, 1.2, .75, .6
MIN_PAIR_SPACING = 6.0


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def variant_path(path):
    path = Path(path)
    if '_magnetic' in path.stem:
        raise ValueError('Refuse to derive a variant from a magnetic file')
    return path.with_name(path.stem + '_magnetic' + path.suffix)


def pocket_cutter(x, y, sign, diameter=DIAMETER):
    if sign not in (-1, 1):
        raise ValueError('Pocket axis must point inward along +X or -X')
    return cq.Solid.makeCylinder(diameter / 2, DEPTH + .01,
                                cq.Vector(x - sign * .01, y, CENTER_Z), cq.Vector(sign, 0, 0))


def safe_pocket(surface, forbidden, x, y, sign):
    # Plan contains the complete bore plus 0.60 back wall and 0.05 Y reserve.
    xa, xb = x + sign * .001, x + sign * (DEPTH + BACK_WALL)
    reserve = box(min(xa, xb), y - DIAMETER/2 - .05,
                  max(xa, xb), y + DIAMETER/2 + .05)
    return bool(surface.buffer(1e-8).covers(reserve) and not forbidden.intersects(reserve))


def choose_pairs(candidates):
    pairs = [p for p in itertools.combinations(candidates, 2)
             if abs(p[0]['y'] - p[1]['y']) >= MIN_PAIR_SPACING]
    if pairs:
        # First reduce the worst air gap, then maximize spacing at equal gap.
        best = min(pairs, key=lambda p: (round(max(v['gap'] for v in p), 5),
                                        -abs(p[0]['y'] - p[1]['y']), p[0]['y']))
        return sorted(best, key=lambda v: v['y'])
    return [min(candidates, key=lambda p: (p['gap'], p['y']))] if candidates else []


def bounds(shape):
    b = shape.BoundingBox()
    return [b.xmin, b.ymin, b.zmin, b.xmax, b.ymax, b.zmax]


def audit_delta(before, after, pockets):
    """Inspect actual exported BRep: only the specified cylinders may disappear."""
    errors = []
    expected = len(pockets) * math.pi * (DIAMETER/2)**2 * DEPTH
    removed = before.cut(after)
    added = after.cut(before)
    cutters = [pocket_cutter(p['x'], p['y'], p['sign']) for p in pockets]
    unplanned = removed.cut(*cutters) if cutters and removed.Volume() > 1e-8 else removed
    missing_bore = sum(after.intersect(c).Volume() for c in cutters)
    actual = before.Volume() - after.Volume()
    if not after.isValid() or len(before.Solids()) != len(after.Solids()):
        errors.append('Invalid or disconnected solid')
    if max(abs(a-b) for a,b in zip(bounds(before), bounds(after))) > 1e-5:
        errors.append('Outer bounds changed')
    if abs(actual-expected) > .002:
        errors.append('Wrong removed volume')
    if added.Volume() > .002 or unplanned.Volume() > .002 or missing_bore > .002:
        errors.append('Added material, off-pocket removal or obstructed pocket')
    return {'errors': errors, 'expected_removed_mm3': expected, 'actual_removed_mm3': actual,
            'added_mm3': added.Volume(), 'off_pocket_removed_mm3': unplanned.Volume(),
            'obstructed_bore_mm3': missing_bore, 'bounds_before_mm': bounds(before),
            'bounds_after_mm': bounds(after), 'solids': len(after.Solids())}


def immutable_paths():
    # Include original models, adapters, all PCB files, and the ordered package.
    paths = [p for p in MODELS.rglob('*') if p.is_file() and '_magnetic' not in p.name
             and '백업' not in p.parts]
    for folder in ['hardware/PCB', 'hardware/GERBER']:
        paths += [p for p in (ROOT / folder).rglob('*') if p.is_file()]
    paths += [Path(base.__file__), ROOT / 'tools/fusion/KC2StepToF3D/KC2StepToF3D.py']
    return sorted(set(paths))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


def load_plans():
    shp = base.legacy_geometry.require_shapely()
    boards = base.run_extractor(Path('C:/Program Files/KiCad/10.0/bin/python.exe'))['boards']
    plans = {side: base.build_plan_geometry(shp, side, data) for side,data in boards.items()}
    forbidden = {s: p['mounting_land_geometry'].union(base._support_plan_union(shp, p['support_posts']))
                 .union(p['reset_local_support_geometry']) for s,p in plans.items()}
    # Read the existing joined renderer's transform from the live board files.
    import subprocess
    code = ("from pathlib import Path; from tools import render_kc2_x3_joined as r; import json; "
            "c=r.build_context(Path.cwd(),1.,5.,'key-pitch',variant='x3-v2'); "
            "print(json.dumps({'dx':c.right_dx,'dy':c.right_dy}))")
    result = subprocess.run(['C:/Program Files/KiCad/10.0/bin/python.exe', '-B', '-c', code],
                            cwd=ROOT, text=True, capture_output=True, check=True, timeout=120)
    transform = json.loads(result.stdout)
    if abs(transform['dy']) > 1e-8 or plans['left']['raw_bounds'][1] != plans['right']['raw_bounds'][1]:
        raise ValueError('Changed Y datum requires reviewed pocket alignment')
    candidates = []
    for y in range(3, 120):
        candidate = {'y': float(y)}
        for side, sign in [('left', 1), ('right', -1)]:
            p = plans[side]
            section = p['housing_outline'].intersection(LineString([(-10, y), (220, y)]))
            if section.is_empty:
                break
            x = section.bounds[0 if side == 'left' else 2]
            if not safe_pocket(p['support_surface'], forbidden[side], x, y, sign):
                break
            candidate[side] = {'x': x, 'y': float(y), 'sign': sign}
        if 'left' in candidate and 'right' in candidate:
            candidate['gap'] = (plans['right']['raw_bounds'][2] - candidate['right']['x'] + transform['dx']
                                - plans['left']['raw_bounds'][2] + candidate['left']['x'])
            if candidate['gap'] > 0:
                candidates.append(candidate)
    return plans, candidates, transform


def inspect_mesh(path, shape):
    mesh = trimesh.load_mesh(path, process=True)
    b = bounds(shape)
    mesh_bounds = mesh.bounds.flatten().tolist()
    error = abs(abs(mesh.volume) - shape.Volume())
    ok = (mesh.is_watertight and mesh.is_winding_consistent and len(mesh.split()) == 1
          and max(mesh.extents) <= 150.001
          and max(abs(a-b) for a,b in zip(b,mesh_bounds)) < .02
          and error < .05 * shape.Volume() / 100)
    if not ok:
        raise RuntimeError(f'Invalid STL {path.name}: watertight={mesh.is_watertight} volume_error={error}')
    return {'watertight': bool(mesh.is_watertight), 'winding_consistent': bool(mesh.is_winding_consistent),
            'shells': len(mesh.split()), 'bounds_mm': mesh_bounds, 'volume_mm3': float(mesh.volume),
            'brep_volume_mm3': shape.Volume(), 'volume_error_mm3': error, 'sha256': digest(path)}


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    protected = {str(p.relative_to(ROOT)).replace('\\','/'): digest(p) for p in immutable_paths()}
    write_json(REPORT / 'originals-before.json', protected)
    print('Loading component/support plans and joined transform', flush=True)
    plans, candidates, transform = load_plans()
    selected = choose_pairs(candidates)
    if not selected:
        raise RuntimeError('No safe magnet pair without thicker walls')
    result = {'requirements': ['CON-ARCH-006', 'OPS-ARCH-006'], 'physical_qualified': False,
              'diameter_mm': DIAMETER, 'depth_mm': DEPTH, 'center_z_mm': CENTER_Z,
              'minimum_back_wall_mm': BACK_WALL, 'web_top_bottom_rim_mm': .55,
              'pairs': selected, 'candidate_count': len(candidates), 'joined_transform': transform,
              'magnet_face_gap_mm': [c['gap'] + 2*(DEPTH-1) for c in selected],
              'fallback_reason': None if len(selected) == 2 else 'Only one safely separated aligned pair fits',
              'sides': {}, 'meshes': {}, 'pending': ['printed bore/bridge fit', 'adhesive retention',
              'magnet polarity and pull force', 'FDM strength', 'assembled physical and RF qualification']}
    print('Selected pairs: ' + json.dumps(selected), flush=True)
    for side in ['left', 'right']:
        source = MODELS / f'kc2_{side}_lower_housing.step'
        print(f'{side}: import and subtract pockets', flush=True)
        before = cq.importers.importStep(str(source)).val()
        pockets = [c[side] for c in selected]
        cutters = [pocket_cutter(p['x'],p['y'],p['sign']) for p in pockets]
        after = before.cut(*cutters)
        target = variant_path(source)
        cq.exporters.export(after, str(target))
        base.normalize_exported_text(target)
        print(f'{side}: reimport and audit actual STEP delta', flush=True)
        actual = cq.importers.importStep(str(target)).val()
        audit = audit_delta(before, actual, pockets)
        if audit['errors']:
            raise RuntimeError(f'{side}: {audit}')
        result['sides'][side] = {'source_sha256': digest(source), 'step_sha256': digest(target),
                                 'pockets': pockets, 'delta': audit,
                                 'protected_primary_supports': len(plans[side]['support_posts']),
                                 'protected_mounting_lands': len(plans[side]['mounting_holes'])}
        solids = sorted(actual.Solids(), key=lambda s: s.Center().x)
        if len(solids) != (1 if side == 'left' else 2):
            raise RuntimeError('Unexpected printable solid count')
        for i, solid in enumerate(solids):
            suffix = '' if side == 'left' else f'_part_{chr(97+i)}'
            stl = MODELS / f'kc2_{side}_lower_housing{suffix}_magnetic.stl'
            cq.exporters.export(solid, str(stl), tolerance=.005, angularTolerance=.08)
            result['meshes'][stl.name] = inspect_mesh(stl, solid)
        write_json(MODELS / 'kc2_housing_manifest_magnetic.json', result)
    # Same wall height, floor and horizontal bore orientation. Read diameters
    # left-to-right along +Y: 2.2, 2.3, 2.4, 2.5 mm; each hole is 1.2 deep.
    coupon = cq.Solid.makeBox(4, 24, 4.7, cq.Vector(0, 0, -2.2))
    for y, diameter in zip([4,9,14,19], [2.2,2.3,2.4,2.5]):
        coupon = coupon.cut(pocket_cutter(0, y, 1, diameter))
    coupon_path = MODELS / 'kc2_magnet_fit_coupon_magnetic.stl'
    cq.exporters.export(coupon, str(coupon_path), tolerance=.005, angularTolerance=.08)
    result['meshes'][coupon_path.name] = inspect_mesh(coupon_path, coupon)
    result['source_bindings'] = {str(p.relative_to(ROOT)).replace('\\','/'): digest(p) for p in
                               [Path(__file__), ROOT/'tools/test_kc2_magnetic_housing.py']}
    changed = [p for p,h in protected.items() if digest(ROOT/p) != h]
    if changed:
        raise RuntimeError('Protected original files changed: ' + repr(changed))
    result['original_files_preserved'] = len(protected)
    result['digital_delta_status'] = 'pass'
    write_json(MODELS / 'kc2_housing_manifest_magnetic.json', result)
    write_json(REPORT / 'cad-delta.json', result)
    write_json(REPORT / 'originals-preserved.json', {'count':len(protected), 'changed':changed, 'sha256':protected})
    print('PASS: CAD delta, STL meshes, original preservation. Fusion round trips still required.', flush=True)


if __name__ == '__main__':
    main()
