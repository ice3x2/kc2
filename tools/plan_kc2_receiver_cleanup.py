"""CON-ARCH-006 source-bound rounded-tip cutter and support exclusion evidence."""
import hashlib
import json
from pathlib import Path
from shapely import wkt
from tools.kc2_receiver_cleanup import plan_cutters, OUTWARD_TOLERANCE_MM, CUT_Z_MM

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    folder = ROOT / '.codex-tmp/registered-housing-fit/lower/right-normal'
    candidate_path = folder / 'receiver-cleanup-candidate.json'
    supports_path = folder / 'receiver-supports-plan.json'
    candidate = json.loads(candidate_path.read_text())
    supports = json.loads(supports_path.read_text())
    paths = [Path(__file__), candidate_path, supports_path,
             ROOT / 'tools/kc2_receiver_cleanup.py', ROOT / 'tools/test_kc2_receiver_cleanup.py']
    for report in (candidate, supports):
        for name, expected in report['source_sha256'].items():
            path = ROOT / name
            if digest(path) != expected:
                raise ValueError('Stale cleanup plan source ' + name)
            paths.append(path)
    frozen = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    roles = {name: wkt.loads(value) for name, value in supports['roles_wkt'].items()}
    rows = []
    for row in candidate['rows']:
        if row['radius_mm'] != .6 or row['cut_z_mm'] != list(CUT_Z_MM):
            raise ValueError('Unexpected candidate contract')
        original = wkt.loads(row['cut_wkt'])
        cutter = plan_cutters([original], roles)
        rows.append(dict(y_mm=row['y_mm'], candidate_wkt=original.wkt, cutter_wkt=cutter.wkt,
                         candidate_area_mm2=original.area, cutter_area_mm2=cutter.area,
                         protected_role_overlap_mm2={name: cutter.intersection(g).area for name, g in roles.items()},
                         protected_role_distance_mm={name: cutter.distance(g) for name, g in roles.items()}))
    if {r['y_mm'] for r in rows} != {73.25, 86.25}:
        raise ValueError('Unexpected receiver identities')
    if frozen != {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}:
        raise ValueError('Plan source changed')
    result = dict(requirements=['CON-ARCH-006'], status='plan_pass_actual_cleanup_pending',
                  source_sha256=frozen, radius_mm=.6, outward_tolerance_mm=OUTWARD_TOLERANCE_MM,
                  cut_z_mm=list(CUT_Z_MM), floor_engagement_z_mm=[-2.2, -1.], rows=rows,
                  physical_qualified=False)
    (folder / 'receiver-cleanup-plan.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
    return result


if __name__ == '__main__':
    run()
