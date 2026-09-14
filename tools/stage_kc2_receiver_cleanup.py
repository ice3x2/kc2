"""CON-ARCH-006 immutable historical pair -> bounded internal-tip cleanup.

Only ignored staged files are written. Old reports retain their original source
paths as historical provenance; snapshot-map explicitly resolves those bytes.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from shapely import wkt
from shapely.ops import unary_union
from tools.kc2_receiver_cleanup import clean_receiver, CUT_Z_MM, validate_evidence, plan_cutters

ROOT = Path(__file__).resolve().parents[1]
STAGE = '.codex-tmp/registered-housing-fit'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_exported_stl(path):
    from tools.kc2_stl_zero_area_filter import normalize
    before=path.read_bytes();after,record=normalize(before)
    if path.read_bytes()!=before:raise ValueError('STL changed during exact facet normalization')
    if after!=before:path.write_bytes(after)
    if digest(path)!=record['output_sha256']:raise ValueError('Normalized STL write differs')
    return record


def merge_sources(target, incoming):
    if any(name in target and target[name] != value for name, value in incoming.items()):
        raise ValueError('Conflicting historical source bindings')
    target.update(incoming)


def snapshot_sources(root, sources, mapping):
    # Validate the complete input set before any snapshot is created.
    for name, expected in sources.items():
        resolve_alias(name,{})
        if not (root/name).resolve().is_relative_to(root.resolve()):
            raise ValueError('Source escapes root')
        if digest(root / name) != expected:
            raise ValueError('Stale original source ' + name)
    result = {}
    assignments = []
    for name, expected in sources.items():
        target_name = resolve_alias(name, mapping)
        source, target = root / name, root / target_name
        for path in (source, target):
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Snapshot path escapes root')
        if target_name in result:
            raise ValueError('Snapshot alias collision')
        if target.exists() and digest(target) != expected:
            raise ValueError('Conflicting immutable snapshot ' + target_name)
        result[target_name] = expected
        assignments.append((name, target_name, source, target))
    for name, target_name, source, target in assignments:
        expected = result[target_name]
        if target_name != name:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and digest(target) != expected:
                raise ValueError('Conflicting immutable snapshot ' + target_name)
            if not target.exists():
                shutil.copy2(source, target)
    return result


def resolve_alias(name, mapping):
    from tools.kc2_registered_release_gate import safe_relative
    safe_relative(name)
    matches=[(p,r) for p,r in mapping.items() if name==p or name.startswith(p+'/')]
    if len(matches)>1:raise ValueError('Ambiguous snapshot alias')
    target=matches[0][1]+name[len(matches[0][0]):] if matches else name
    safe_relative(target)
    return target


def parent_path(kind):
    names={'direct_v2':'right-void-review.json',
           'predicate_bundle':'right-predicate-bundle.json',
           'strata_bundle':'right-strata-predicate-bundle.json'}
    if kind not in names:raise ValueError('Unknown parent proof kind')
    return STAGE+'/lower/'+names[kind]


def validate_parent(kind, read):
    record=json.loads(read(parent_path(kind)))
    if kind=='strata_bundle':
        from tools.kc2_lower_strata_bundle import validate_bundle
        if validate_bundle(record,read) is not True:raise ValueError('Strata parent did not qualify')
    elif kind=='predicate_bundle':
        from tools.kc2_lower_predicate_bundle import validate_bundle
        validate_bundle(record,read)
    else:
        from tools.publish_kc2_registered_housings import check_lower_void, LOWER_VOID_ZERO
        from tools.kc2_lower_predicate_bundle import exact_zero, MAGNET_ZERO
        check_lower_void(record,'right',False)
        for row in record['variants'].values():
            if type(row['body_count']) is not int or row['body_count']!=2:raise ValueError('Wrong parent body count')
            for key in LOWER_VOID_ZERO:exact_zero(row[key])
        for key in MAGNET_ZERO:exact_zero(record['magnet'][key])
        for name,sha in record['source_sha256'].items():
            if hashlib.sha256(read(name)).hexdigest()!=sha:raise ValueError('Stale direct parent source')
    return record


def snapshot_mapping(parent_kind):
    parent_path(parent_kind)
    mapping = {f'{STAGE}/lower/right-{v}': f'{STAGE}/lower-development/receiver-cleanup-inputs/right-{v}'
               for v in ('normal', 'magnetic')}
    mapping[f'{STAGE}/lower/right-void-review.json'] = f'{STAGE}/lower-development/receiver-cleanup-inputs/right-void-review.json'
    mapping['.codex-tmp/receiver_cleanup_candidate.py'] = f'{STAGE}/lower-development/receiver-cleanup-inputs/provenance/receiver_cleanup_candidate.py'
    if parent_kind=='predicate_bundle':
        for name in ('right-component-distance-review.json','right-d8-local-certificate.json','right-predicate-bundle.json'):
            mapping[f'{STAGE}/lower/{name}']=f'{STAGE}/lower-development/receiver-cleanup-inputs/{name}'
    if parent_kind=='strata_bundle':
        for name in ('right-normal-strata-review.json','right-magnetic-subset-review.json','right-strata-predicate-bundle.json'):
            mapping[f'{STAGE}/lower/{name}']=f'{STAGE}/lower-development/receiver-cleanup-inputs/{name}'
    return mapping


def prepare(parent_kind='direct_v2'):
    cache = ROOT / STAGE / 'lower-development/receiver-cleanup-inputs'
    manifest_path = cache / 'snapshot-map.json'
    logical_parent=parent_path(parent_kind)
    sources = {}
    mapping = snapshot_mapping(parent_kind)
    if manifest_path.exists():
        report=json.loads(manifest_path.read_text())
        if report.get('status')!='verified_historical_snapshot' or report.get('parent_proof_kind')!=parent_kind or report.get('parent_proof_path')!=logical_parent or report.get('path_mapping')!=mapping:
            raise ValueError('Snapshot parent identity differs')
        historical=report['historical_original_sha256']
        remapped={resolve_alias(n,mapping):sha for n,sha in historical.items()}
        if len(remapped)!=len(historical) or remapped!=report['source_sha256']:raise ValueError('Snapshot closure differs')
        def archived_read(name):
            if name not in historical:raise ValueError('Source absent from historical closure')
            path=ROOT/resolve_alias(name,mapping)
            if not path.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Archive escapes root')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=historical[name]:raise ValueError('Snapshot changed '+name)
            return data
        for name in historical:archived_read(name)
        if historical.get(logical_parent)!=report.get('parent_proof_sha256'):raise ValueError('Parent SHA differs')
        validate_parent(parent_kind,archived_read)
        return report
    # Archive only source/evidence closure; unused native/STL candidates are not
    # new dependencies. Both source identities are resolved before either changes.
    for variant in ('normal', 'magnetic'):
        folder = ROOT / STAGE / 'lower' / ('right-' + variant)
        names = ['generation.json', 'kc2_right_lower_housing' + ('_magnetic' if variant == 'magnetic' else '') + '.step']
        if variant == 'normal':
            names += ['receiver-cleanup-plan.json', 'receiver-cleanup-candidate.json',
                      'receiver-supports-plan.json', 'receiver-floor-prism-diagnosis.json',
                      'throat-diagnosis.json', 'split-review.json']
        for name in names:
            path = folder / name
            merge_sources(sources, {path.relative_to(ROOT).as_posix(): digest(path)})
            if path.suffix == '.json':
                merge_sources(sources, json.loads(path.read_text()).get('source_sha256', {}))
        generation = json.loads((folder / 'generation.json').read_text())
        if generation['status'] != 'generated_pending_independent_review' or type(generation['body_count']) is not int or generation['body_count'] != 2:
            raise ValueError('Wrong pre-cleanup generation')
        for name, expected in generation['outputs'].items():
            if digest(folder / name) != expected:
                raise ValueError('Changed generation output')
        merge_sources(sources, generation['source_sha256'])
    def current_read(name):
        resolve_alias(name,{})
        path=ROOT/name
        if not path.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Source escapes root')
        return path.read_bytes()
    void_path = ROOT / logical_parent
    void = validate_parent(parent_kind,current_read)
    sources[void_path.relative_to(ROOT).as_posix()] = digest(void_path)
    merge_sources(sources, void['source_sha256'])
    for name in ('receiver-cleanup-plan.json', 'receiver-floor-prism-diagnosis.json'):
        path = ROOT / STAGE / 'lower/right-normal' / name
        report = json.loads(path.read_text())
        merge_sources(sources, report['source_sha256'])
    copied = snapshot_sources(ROOT, sources, mapping)
    report = dict(requirements=['CON-ARCH-006'], status='verified_historical_snapshot',
                  parent_proof_kind=parent_kind,parent_proof_path=logical_parent,parent_proof_sha256=sources[logical_parent],
                  source_sha256=copied, historical_original_sha256=sources, path_mapping=mapping,
                  note='Original paths in archived reports are historical, resolved by this explicit mapping; no old current-path hashes claimed current.')
    manifest_path.write_text(json.dumps(report, indent=2) + '\n')
    return report


def generate(magnetic=False, parent_kind='direct_v2'):
    import cadquery as cq
    from tools.kc2_central_flexure import prism
    from tools.generate_kc2_magnetic_housings import bounds, inspect_mesh
    from shapely.geometry import box
    prepare(parent_kind)
    cache = ROOT / STAGE / 'lower-development/receiver-cleanup-inputs'
    variant = 'magnetic' if magnetic else 'normal'
    old_folder = cache / ('right-' + variant)
    folder = ROOT / STAGE / 'lower' / ('right-' + variant)
    old_path = old_folder / 'generation.json'
    old = json.loads(old_path.read_text())
    stem = 'kc2_right_lower_housing' + ('_magnetic' if magnetic else '')
    source = old_folder / (stem + '.step')
    plan_path = cache / 'right-normal/receiver-cleanup-plan.json'
    plan = json.loads(plan_path.read_text())
    diagnosis = json.loads((cache / 'right-normal/receiver-floor-prism-diagnosis.json').read_text())
    if (plan['status'] != 'plan_pass_actual_cleanup_pending' or plan['cut_z_mm'] != list(CUT_Z_MM)
            or plan['radius_mm'] != .6 or plan['outward_tolerance_mm'] != .002):
        raise ValueError('Wrong cleanup plan')
    support_report = json.loads((cache / 'right-normal/receiver-supports-plan.json').read_text())
    roles = {k: wkt.loads(v) for k, v in support_report['roles_wkt'].items()}
    validate_evidence(diagnosis, roles)
    if len(plan['rows']) != 2 or {r['y_mm'] for r in plan['rows']} != {73.25, 86.25}:
        raise ValueError('Wrong plan receiver identities')
    for row in plan['rows']:
        expected = plan_cutters([wkt.loads(row['candidate_wkt'])], roles)
        if expected.symmetric_difference(wkt.loads(row['cutter_wkt'])).area > 1e-10:
            raise ValueError('Altered bounded cutter')
    frozen = dict(json.loads((cache / 'snapshot-map.json').read_text())['source_sha256'])
    for path in (Path(__file__), ROOT / 'tools/kc2_receiver_cleanup.py',
                 ROOT / 'tools/test_kc2_receiver_cleanup.py', ROOT / 'tools/test_kc2_receiver_snapshot.py',
                 ROOT / 'tools/kc2_stl_zero_area_filter.py', ROOT / 'tools/test_kc2_stl_zero_area_filter.py',
                 cache / 'snapshot-map.json'):
        frozen[path.relative_to(ROOT).as_posix()] = digest(path)
    footprint = unary_union([wkt.loads(r['cutter_wkt']) for r in plan['rows']])
    print('import immutable pre-cleanup pair', variant, flush=True)
    before = cq.importers.importStep(str(source)).val()
    old_a = sorted(before.Solids(), key=lambda s: s.Center().x)[0]
    cutter = prism(footprint, *CUT_Z_MM)
    if old_a.intersect(cutter).Volume() != 0:
        raise ValueError('Cleanup intersects donor A')
    print('bounded above-floor rounded-tip cut', flush=True)
    after = clean_receiver(before, footprint)
    removed = before.cut(after)
    bb = before.BoundingBox()
    floor = prism(box(bb.xmin-1, bb.ymin-1, bb.xmax+1, bb.ymax+1), -2.2, -1.)
    print('full actual delta/floor audit', flush=True)
    audit = dict(removed_mm3=removed.Volume(), added_mm3=after.cut(before).Volume(),
                 off_cutter_removed_mm3=removed.cut(*cutter.Solids()).Volume(),
                 floor_removed_mm3=removed.intersect(floor).Volume(),
                 remaining_candidate_mm3=after.intersect(cutter).Volume())
    if max(audit[k] for k in audit if k != 'removed_mm3') > .002:
        raise ValueError('Cleanup delta failed ' + str(audit))
    parts = sorted(after.Solids(), key=lambda s: s.Center().x)
    if len(parts) != 2 or not after.isValid():
        raise ValueError('Invalid cleaned pair')
    gap = parts[0].distance(parts[1])
    if gap < .39999:
        raise ValueError('Cleaned A/B gap below .40')
    step = folder / (stem + '.step')
    cq.exporters.export(after, str(step))
    reopened = cq.importers.importStep(str(step)).val()
    if not reopened.isValid() or len(reopened.Solids()) != 2 or abs(reopened.Volume()-after.Volume()) > .01:
        raise ValueError('Cleanup STEP roundtrip')
    outputs = {step.name: digest(step)}
    rows = []
    for i, part in enumerate(parts):
        stl = folder / ('kc2_right_lower_housing_part_' + 'ab'[i] + ('_magnetic' if magnetic else '') + '.stl')
        cq.exporters.export(part, str(stl), tolerance=.005, angularTolerance=.08)
        normalization=normalize_exported_stl(stl)
        row = {k: v for k, v in old['parts'][i].items() if k in ('index', 'cutter_wkt', 'mask_wkt')}
        row['historical_part_provenance'] = dict(report=old_path.relative_to(ROOT).as_posix(), index=i)
        row.update(volume_mm3=part.Volume(), bounds_mm=bounds(part), mesh=inspect_mesh(stl, part))
        row['stl_exact_zero_area_normalization']=normalization
        rows.append(row)
        outputs[stl.name] = digest(stl)
    for name, expected in frozen.items():
        if digest(ROOT / name) != expected:
            raise ValueError('Changed immutable cleanup input ' + name)
    result = dict(old)
    # Earlier numeric audits are explicitly historical, not rerun evidence.
    result = {k: v for k, v in result.items() if k in ('requirements', 'side', 'magnetic', 'body_count',
              'ordinary_wall_top_mm', 'registrar_top_mm', 'registrars', 'split_x_mm', 'capture_ys',
              'nominal_capture', 'central_wall_relief', 'transform')}
    result.update(status='generated_pending_independent_review', source_sha256=frozen, outputs=outputs,
                  parts=rows, volume_mm3=after.Volume(), bounds_mm=bounds(after),
                  actual_ab_gap_mm=gap, receiver_cleanup=audit,
                  cleanup_contract=dict(radius_mm=.6, outward_tolerance_mm=.002, cut_z_mm=list(CUT_Z_MM),
                                        floor_engagement_z_mm=[-2.2, -1.], cutter_wkt=footprint.wkt),
                  development_provenance=old_path.relative_to(ROOT).as_posix(),
                  physical_qualified=False, canonical_changed=False)
    (folder / 'generation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'], variant, audit, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--magnetic', action='store_true')
    parser.add_argument('--snapshot-only', action='store_true')
    parser.add_argument('--parent-proof', choices=('direct_v2','predicate_bundle','strata_bundle'), default='direct_v2')
    args = parser.parse_args()
    prepare(args.parent_proof) if args.snapshot_only else generate(args.magnetic,args.parent_proof)
