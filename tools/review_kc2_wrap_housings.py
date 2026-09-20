"""CON-ARCH-006 fresh STL-section review, separate from CAD generation.

This is digital geometry evidence, not physical qualification. The native and
whole-CAD preservation gates are additional publication requirements.
"""
from pathlib import Path
import json
import trimesh
from shapely import wkt, affinity
from tools.kc2_pcb_seating import horizontal_section, digest

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT/'.codex-tmp/wrap-housing-20260920-r1'


def check_bindings(root, bindings):
    for name, expected in bindings.items():
        path = root/name
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Changed or missing review input: '+name)


def clearance_section(mesh, z, protected, minimum):
    actual = horizontal_section(mesh, z)
    overlap = actual.intersection(protected).area
    gap = None if actual.is_empty or protected.is_empty else actual.distance(protected)
    return dict(z_mm=z, overlap_mm2=overlap, gap_mm=gap,
                **{'pass': overlap < .005 and (gap is None or gap >= minimum-.0001)})


def required_section(mesh, z, required):
    actual = horizontal_section(mesh, z)
    missing = required.difference(actual).area
    return dict(z_mm=z, required_mm2=required.area, missing_mm2=missing, **{'pass':missing < .005})


def world(g, side):
    return affinity.translate(affinity.scale(g, xfact=-1, yfact=1, origin=(0, 0)),
                              xoff=170.1125 if side == 'left' else 323.3125)


def review():
    plan = json.loads((STAGE/'plan.json').read_text())
    bindings = dict(plan['source_sha256'])
    check_bindings(ROOT, bindings)
    bindings[(STAGE/'plan.json').relative_to(ROOT).as_posix()] = digest(STAGE/'plan.json')
    envelope_path = STAGE/'board-envelopes.json'
    envelopes = json.loads(envelope_path.read_text())
    check_bindings(ROOT, envelopes['source_sha256'])
    bindings.update(envelopes['source_sha256'])
    bindings[envelope_path.relative_to(ROOT).as_posix()] = digest(envelope_path)
    rows, meshes, errors = {}, {}, []
    for side in ('left', 'right'):
        p = plan['sides'][side]
        for kind in ('normal', 'magnetic', 'choc_v1', 'deep_sea', 'mx'):
            label = side+':'+kind
            lower = kind in ('normal', 'magnetic')
            folder = STAGE/('lower' if lower else 'upper')/(side+'-'+kind)
            path = folder/'generation.json'
            generation = json.loads(path.read_text())
            check_bindings(ROOT, generation['source_sha256'])
            bindings.update(generation['source_sha256'])
            if generation['status'] != 'generated_pending_independent_review' or generation['errors']:
                raise ValueError('Incomplete generation: '+label)
            for name, sha in generation['outputs'].items():
                if digest(folder/name) != sha:
                    raise ValueError('Changed generated file: '+name)
                bindings[(folder/name).relative_to(ROOT).as_posix()] = sha
            bindings[path.relative_to(ROOT).as_posix()] = digest(path)
            paths = [folder/name for name in generation['outputs'] if name.endswith('.stl')]
            part_meshes, sections = [], []
            for i, path in enumerate(paths):
                mesh = trimesh.load(path, force='mesh')
                if not mesh.is_watertight or len(mesh.split()) != 1 or max(mesh.extents[:2]) > 150:
                    errors.append(label+': invalid mesh or print envelope')
                part_meshes.append(mesh)
                if lower:
                    wall = wkt.loads(p['wall_parts_wkt'][i]); floor = wkt.loads(p['floor_parts_wkt'][i])
                    part_rows = [required_section(mesh, -1.6, floor)]
                    part_rows += [required_section(mesh, z, wall) for z in (-.5, 2.49, 2.51, 4.09, 4.41, 5.01, 5.59)]
                    if abs(mesh.bounds[1, 2]-5.6) > .001:
                        errors.append(label+': wrong actual wall height')
                else:
                    rim = wkt.loads(p['upper_rim_parts_wkt'][kind][i])
                    top = {'mx':9.3, 'choc_v1':6.5, 'deep_sea':6.25}[kind]
                    part_rows = [required_section(mesh, z, rim) for z in (4.41, 5.3, 6.2, top-.01)]
                if any(not r['pass'] for r in part_rows):
                    errors.append(label+': missing required sleeve/rim/floor')
                sections.append(part_rows)
            meshes[label] = trimesh.util.concatenate(part_meshes)
            rows[label] = dict(sections=sections)
            if lower:
                caps = wkt.loads(p['keycaps_wkt'])
                cap_checks = [clearance_section(meshes[label], z, caps, .3)
                              for z in (5.025, 5.15, 5.35, 5.55)]
                rows[label]['nominal_cap_sections'] = cap_checks
                if any(not item['pass'] for item in cap_checks):
                    errors.append(label+': nominal cap clearance failure')
                board = wkt.loads(envelopes['sides'][side]['board_wkt'])
                board_checks = [clearance_section(meshes[label], z, board, .3)
                                for z in (2.51, 3.3, 4.09)]
                rows[label]['pcb_sections'] = board_checks
                if any(not item['pass'] for item in board_checks):
                    errors.append(label+': PCB seating clearance failure')
            print('fresh mesh sections', label, 'errors so far:', errors, flush=True)
    assembly = []
    for side in ('left', 'right'):
        for kind in ('mx', 'choc_v1', 'deep_sea'):
            for lower_kind in ('normal', 'magnetic'):
                for z in (4.25, 4.55, 4.9, 5.025, 5.15, 5.35, 5.55):
                    upper = horizontal_section(meshes[side+':'+kind], z)
                    lower = horizontal_section(meshes[side+':'+lower_kind], z)
                    overlap = upper.intersection(lower).area
                    gap = upper.distance(lower) if not lower.is_empty and not upper.is_empty else None
                    row = dict(side=side, kind=kind, lower_kind=lower_kind, z_mm=z,
                               overlap_mm2=overlap, gap_mm=gap)
                    assembly.append(row)
                    if overlap > .005:
                        errors.append('Actual upper/lower interference: '+str(row))
    joins = []
    for kind in ('normal', 'magnetic'):
        for z in (-1.6, -.5, 2.49, 3.3, 4.55, 5.35, 5.55):
            left = world(horizontal_section(meshes['left:'+kind], z), 'left')
            right = world(horizontal_section(meshes['right:'+kind], z), 'right')
            overlap = left.intersection(right).area
            gap = left.distance(right)
            joins.append(dict(kind=kind, z_mm=z, overlap_mm2=overlap, gap_mm=gap))
            if overlap > .005 or gap < .3999:
                errors.append('New center collision/clearance failure')
    for name in ('tools/review_kc2_wrap_housings.py', 'tools/test_review_kc2_wrap_housings.py'):
        bindings[name] = digest(ROOT/name)
    check_bindings(ROOT, bindings)
    result = dict(status='pass' if not errors else 'failed', errors=errors, rows=rows,
                  assembly=assembly, joins=joins, source_sha256=bindings, physical_qualified=False,
                  scope='Fresh STL manifold, wall/floor/rim sections, sampled assembled and joined clearance; not native or full continuous motion proof.')
    (STAGE/'mesh-review.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(result['status'], errors, flush=True)
    return result


if __name__ == '__main__':
    raise SystemExit(bool(review()['errors']))
