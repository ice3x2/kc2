"""CON-ARCH-006 full BRep additions and static assembled-volume review.

Independent STEP imports, not sampled STL sections. Physical deviations and
assembly motion are not qualified by a static volume intersection.
"""
import json
import cadquery as cq
from shapely import wkt
from tools.review_kc2_wrap_housings import ROOT, STAGE, check_bindings
from tools.kc2_wrap_native import jobs, preflight
from tools.kc2_central_flexure import prism
from tools.kc2_pcb_seating import digest


def missing_volume(actual, expected):
    return sum(abs(piece.cut(actual).Volume()) for piece in expected)


def collision_volume(first, second):
    return sum(abs(a.intersect(b).Volume()) for a in first for b in second)


def world_solids(solids, side):
    offset = {'left':170.1125, 'right':323.3125}[side]
    return [s.mirror('YZ').translate((offset, 0, 0)) for s in solids]


def magnet_voids(side):
    from tools.kc2_magnetic_entry import entry_tools
    from tools.generate_kc2_magnetic_housings import pocket_cutter
    mouth, sign = {'left':(.1, 1), 'right':(149.3, -1)}[side]
    return entry_tools(side)+[pocket_cutter(mouth, y, sign) for y in (103., 111.)]


def reusable_checkpoint(record, bindings, body_count):
    return (record.get('status') == 'pass' and record.get('source_sha256') == bindings and
            len(record.get('row', {}).get('parts', [])) == body_count)


def review():
    plan_path = STAGE/'plan.json'
    plan = json.loads(plan_path.read_text())
    bindings = dict(plan['source_sha256'])
    bindings[plan_path.relative_to(ROOT).as_posix()] = digest(plan_path)
    check_bindings(ROOT, bindings)
    rows, shapes, errors = {}, {}, []
    for label in jobs():
        job = preflight(ROOT, label)
        generation = json.loads(job['generation_path'].read_text())
        bindings.update(generation['source_sha256'])
        for path in (job['source'], job['generation_path']):
            bindings[path.relative_to(ROOT).as_posix()] = digest(path)
        side, kind = label.split(':')
        p = plan['sides'][side]; d = p['dimensions']
        solids = sorted(cq.importers.importStep(str(job['source'])).solids().vals(), key=lambda s:s.Center().x)
        if len(solids) != job['body_count'] or any(not s.isValid() for s in solids):
            raise ValueError('Invalid actual BRep: '+label)
        checkpoint_path = STAGE/'cad-checkpoints'/(label.replace(':','-')+'.json')
        checkpoint_sources = {path.relative_to(ROOT).as_posix():digest(path) for path in
            (job['source'], job['generation_path'], plan_path, ROOT/'tools/review_kc2_wrap_cad.py',
             ROOT/'tools/kc2_central_flexure.py', ROOT/'tools/kc2_magnetic_entry.py',
             ROOT/'tools/generate_kc2_magnetic_housings.py')}
        if checkpoint_path.is_file():
            cached = json.loads(checkpoint_path.read_text())
            if reusable_checkpoint(cached, checkpoint_sources, job['body_count']):
                rows[label] = cached['row']
                shapes[label] = solids
                print('source-identical full-volume checkpoint', label, flush=True)
                continue
        previous_errors = len(errors)
        parts = []
        for i, solid in enumerate(solids):
            if kind in ('normal', 'magnetic'):
                expected = [prism(wkt.loads(p['wall_parts_wkt'][i]), d['floor_top'], d['wall_top']),
                            prism(wkt.loads(p['floor_parts_wkt'][i]), d['floor_bottom'], d['floor_top'])]
            else:
                top = {'mx':9.3, 'choc_v1':6.5, 'deep_sea':6.25}[kind]
                expected = [prism(wkt.loads(p['upper_rim_parts_wkt'][kind][i]), 4.4, top)]
            missing = missing_volume(solid, expected)
            if missing > .002:
                errors.append(label+': missing expected material')
            proof = generation['parts'][i]['preservation']
            if proof['errors'] or proof['removed_baseline_mm3'] > .002 or proof['unplanned_added_mm3'] > .002:
                errors.append(label+': failed source-bound preservation')
            parts.append(dict(missing_required_mm3=missing, preservation=proof))
            print('full-volume additions', label, i, missing, flush=True)
        ab = collision_volume(solids[:1], solids[1:]) if len(solids) > 1 else 0.
        if ab > .002:
            errors.append(label+': A/B overlap')
        rows[label] = dict(parts=parts, ab_overlap_mm3=ab)
        if kind == 'magnetic':
            obstructed = collision_volume(solids, magnet_voids(side))
            rows[label]['magnet_access_and_pocket_obstruction_mm3'] = obstructed
            if obstructed > .002:
                errors.append(label+': magnet access/pocket obstructed')
        shapes[label] = solids
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(json.dumps(dict(status='pass' if len(errors) == previous_errors else 'failed',
            source_sha256=checkpoint_sources, row=rows[label]), indent=2)+'\n', encoding='utf-8')
    assemblies = []
    for side in ('left', 'right'):
        for lower in ('normal', 'magnetic'):
            for upper in ('mx', 'choc_v1', 'deep_sea'):
                volume = collision_volume(shapes[side+':'+lower], shapes[side+':'+upper])
                assemblies.append(dict(side=side, lower=lower, upper=upper, overlap_mm3=volume))
                if volume > .002:
                    errors.append(side+':'+lower+':'+upper+': static assembly collision')
                print('full-volume assembly', side, lower, upper, volume, flush=True)
    joins = []
    for lower in ('normal', 'magnetic'):
        for upper in ('mx', 'choc_v1', 'deep_sea'):
            left = world_solids(shapes['left:'+lower]+shapes['left:'+upper], 'left')
            right = world_solids(shapes['right:'+lower]+shapes['right:'+upper], 'right')
            volume = collision_volume(left, right)
            joins.append(dict(lower=lower, upper=upper, overlap_mm3=volume))
            if volume > .002:
                errors.append(lower+':'+upper+': complete left/right collision')
            print('full-volume joined halves', lower, upper, volume, flush=True)
    for name in ('tools/review_kc2_wrap_cad.py', 'tools/test_review_kc2_wrap_cad.py',
                 'tools/kc2_central_flexure.py', 'tools/kc2_wrap_native.py',
                 'tools/kc2_magnetic_entry.py', 'tools/generate_kc2_magnetic_housings.py'):
        bindings[name] = digest(ROOT/name)
    check_bindings(ROOT, bindings)
    result = dict(requirements=['CON-ARCH-006'], status='pass' if not errors else 'failed',
                  rows=rows, assemblies=assemblies, joins=joins, errors=errors, source_sha256=bindings,
                  physical_qualified=False, scope='Full required added material, A/B, static lower/upper and complete joined halves; no physical or motion qualification.')
    (STAGE/'cad-review.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    raise SystemExit(review()['status'] != 'pass')
