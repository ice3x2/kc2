"""CON-ARCH-006 seal both left originals, then subtract new central stock only."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGE='.codex-tmp/registered-housing-fit'
CACHE=STAGE+'/lower-development/left-central-inputs'
MAPPING={**{STAGE+'/lower/left-'+v:CACHE+'/left-'+v for v in ('normal','magnetic')},
         STAGE+'/central/integrated-review.json':CACHE+'/integrated-review-failed.json',
         STAGE+'/central/overlap-localization.json':CACHE+'/overlap-localization.json'}
CODE=('stage_kc2_left_central_relief','test_stage_kc2_left_central_relief',
      'kc2_left_central_relief','test_kc2_left_central_relief','kc2_central_flexure',
      'stage_kc2_receiver_cleanup','kc2_receiver_cleanup','kc2_registered_release_gate',
      'kc2_magnetic_subset','kc2_component_local_certificate',
      'generate_kc2_magnetic_housings','kc2_stl_zero_area_filter','test_kc2_stl_zero_area_filter',
      'kc2_lower_floor','test_kc2_lower_floor','review_kc2_filled_plates')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root,sources):
    from tools.kc2_registered_release_gate import safe_relative
    if not sources:raise ValueError('Empty source closure')
    for name,sha in sources.items():
        safe_relative(name);path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path)!=sha:raise ValueError('Stale source '+name)


def seal_snapshot(root,sources,mapping,path):
    from tools.stage_kc2_receiver_cleanup import snapshot_sources,resolve_alias
    root=root.resolve()
    if not path.resolve().is_relative_to(root):raise ValueError('Unsafe snapshot path')
    expected={resolve_alias(n,mapping):sha for n,sha in sources.items()}
    if len(expected)!=len(sources):raise ValueError('Snapshot aliases collide')
    if path.exists():
        report=json.loads(path.read_text())
        if (report.get('schema')!='left-central-originals-v1' or report.get('path_mapping')!=mapping
            or report.get('historical_original_sha256')!=sources or report.get('source_sha256')!=expected
            or report.get('status')!='verified_historical_snapshot'):
            raise ValueError('Conflicting immutable snapshot')
        verify(root,expected);return report
    copied=snapshot_sources(root,sources,mapping)
    verify(root,copied)
    report=dict(requirements=['CON-ARCH-006'],schema='left-central-originals-v1',
                status='verified_historical_snapshot',path_mapping=mapping,
                historical_original_sha256=sources,source_sha256=copied,
                note='Both left variants and historical central failure are immutable inputs, not fresh approval.')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8') as handle:handle.write(json.dumps(report,indent=2)+'\n')
    return report


def validate_original(record,variant):
    stem='kc2_left_lower_housing'+('_magnetic' if variant=='magnetic' else '')
    if (variant not in ('normal','magnetic') or record.get('status')!='generated_pending_independent_review'
        or record.get('side')!='left' or record.get('magnetic') is not (variant=='magnetic')
        or type(record.get('body_count')) is not int or record['body_count']!=1
        or record.get('ordinary_wall_top_mm')!=4.1 or record.get('registrar_top_mm')!=5.
        or not record.get('source_sha256') or set(record.get('outputs',{}))!={stem+'.step',stem+'.stl'}
        or 'left_central_relief' in record):raise ValueError('Wrong original left generation')


def prepare(root=ROOT):
    root=Path(root).resolve();manifest=root/CACHE/'snapshot-map.json'
    if manifest.exists():
        snapshot=json.loads(manifest.read_text())
        sources=collect_original_sources(root,MAPPING)
        return seal_snapshot(root,sources,MAPPING,manifest)
    sources=collect_original_sources(root,{})
    return seal_snapshot(root,sources,MAPPING,manifest)


def collect_original_sources(root,mapping):
    """Reconstruct mandatory closure from actual original or archived bytes."""
    from tools.stage_kc2_receiver_cleanup import merge_sources,resolve_alias
    sources={}
    def add(path,expected=None):
        name=path.relative_to(root).as_posix();sha=digest(root/resolve_alias(name,mapping))
        if expected is not None and sha!=expected:raise ValueError('Changed input '+name)
        merge_sources(sources,{name:sha})
    def report(path):
        add(path);data=json.loads((root/resolve_alias(path.relative_to(root).as_posix(),mapping)).read_text())
        merge_sources(sources,data.get('source_sha256',{}));return data
    for variant in ('normal','magnetic'):
        folder=root/STAGE/'lower'/('left-'+variant)
        data=report(folder/'generation.json');validate_original(data,variant)
        for name,sha in data['outputs'].items():add(folder/name,sha)
        # Preserve the live registrar bytes as well as earlier development
        # snapshots already included in the original generation closure.
        report(folder/'registrar-snapshot.json')
    failed=report(root/STAGE/'central/integrated-review.json')
    local=report(root/STAGE/'central/overlap-localization.json')
    if failed.get('status')!='failed' or set(failed.get('rows',{}))!={f'{v}-y{y}' for v in ('normal','magnetic') for y in (95,117)}:
        raise ValueError('Wrong historical central failure')
    if local.get('status')!='diagnosed_not_accepted' or {r.get('y') for r in local.get('rows',[])}!={95,117}:
        raise ValueError('Missing two-contact actual localization')
    for row in local['rows']:
        if any(type(row.get(k)) not in (float,int) or row[k]!=0 for k in ('unexpected_in_old_left_mm3','unexpected_in_isolated_left_mm3')):
            raise ValueError('Localization implicates protected left stock')
    report(root/'.codex-tmp/perimeter-wall-plans.json')
    verify(root,{resolve_alias(n,mapping):sha for n,sha in sources.items()})
    return sources


def single(shape):
    if (not shape.isValid() or len(shape.Solids())!=1 or not math.isfinite(shape.Volume()) or shape.Volume()<=0
        or not shape.Shells() or any(not s.Closed() for s in shape.Shells())):
        raise ValueError('One valid closed positive solid required')
    solid=shape.Solids()[0]
    for method in ('Faces','Edges','Vertices'):
        whole=list(getattr(shape,method)());owned=list(getattr(solid,method)())
        if len(whole)!=len(owned):raise ValueError('Extraneous/shared '+method)
        buckets={}
        for item in owned:buckets.setdefault(hash(item),[]).append(item)
        for item in whole:
            candidates=buckets.get(hash(item),[])
            match=next((i for i,parent in enumerate(candidates) if item.isSame(parent)),None)
            if match is None:raise ValueError('Unowned '+method)
            candidates.pop(match)
        if any(buckets.values()):raise ValueError('Missing '+method)


def load_protected_males(root,sources):
    """Use the actual component-trimmed isolated roots, never a full XY prism."""
    import cadquery as cq
    folder=Path(root)/STAGE/'central';path=folder/'central-features.json'
    def checked(p,expected=None):
        key=p.relative_to(root).as_posix();sha=digest(p)
        if key not in sources or sources[key]!=sha or (expected is not None and expected!=sha):
            raise ValueError('Unbound or changed isolated male '+key)
    checked(path);record=json.loads(path.read_text())
    if record.get('status')!='feature_geometry_pass_integration_pending':raise ValueError('Wrong isolated feature record')
    for name,sha in record.get('source_sha256',{}).items():checked(Path(root)/name,sha)
    result={}
    for y in (95,117):
        path=folder/f'left-central-y{y}.step'
        expected=record.get('outputs',{}).get(path.name)
        if not expected:raise ValueError('Missing isolated output identity')
        checked(path,expected)
        result[y]=cq.importers.importStep(str(path)).val();single(result[y])
    return result


def apply_relief(before,cutters,baseline,male):
    from tools.kc2_magnetic_subset import nd_cut
    from tools.kc2_component_local_certificate import _non_destructive_common as common
    single(before);single(baseline)
    if not isinstance(male,dict) or set(male)!={95,117}:raise ValueError('Both actual isolated males required')
    for shape in male.values():single(shape)
    male_before={str(y):nd_cut(shape,before).Volume() for y,shape in male.items()}
    if any(not math.isfinite(v) or v!=0 for v in male_before.values()):
        raise ValueError('Original actual male missing '+str(male_before))
    if not cutters or any(not t.isValid() or not t.Solids() or t.Volume()<=0 for t in cutters):
        raise ValueError('Positive valid relief tools required')
    after=before
    for tool in cutters:after=nd_cut(after,tool)
    single(after)
    removed=nd_cut(before,after);outside=removed
    for tool in cutters:outside=nd_cut(outside,tool)
    residuals=[common(after,t).Volume() for t in cutters]
    if any(not math.isfinite(v) or v!=0 for v in residuals):raise ValueError('Individual remaining relief '+str(residuals))
    male_after={str(y):nd_cut(shape,after).Volume() for y,shape in male.items()}
    if any(not math.isfinite(v) or v!=0 for v in male_after.values()):
        raise ValueError('Revised actual male missing '+str(male_after))
    audit=dict(removed_mm3=removed.Volume(),added_mm3=nd_cut(after,before).Volume(),
        off_cutter_removed_mm3=outside.Volume(),remaining_cut_mm3=sum(residuals),
        baseline_missing_before_mm3=nd_cut(baseline,before).Volume(),baseline_missing_after_mm3=nd_cut(baseline,after).Volume(),
        male_missing_before_mm3=sum(male_before.values()),male_missing_after_mm3=sum(male_after.values()))
    if (not math.isfinite(audit['removed_mm3']) or audit['removed_mm3']<=0
        or any(not math.isfinite(v) or v!=0 for k,v in audit.items() if k!='removed_mm3')):
        raise ValueError('Exact protected subtraction failed '+str(audit))
    audit['remaining_cut_per_tool_mm3']=residuals
    audit['male_missing_before_per_y_mm3']=male_before
    audit['male_missing_after_per_y_mm3']=male_after
    return after,audit


def generate(magnetic=False,root=ROOT):
    import cadquery as cq
    from shapely import wkt
    from tools.kc2_left_central_relief import relief_plan
    from tools.kc2_central_flexure import prism
    from tools.generate_kc2_magnetic_housings import bounds,inspect_mesh
    from tools.kc2_stl_zero_area_filter import normalize
    from tools.kc2_lower_floor import inspect_floor
    root=Path(root).resolve();snapshot=prepare(root);variant='magnetic' if magnetic else 'normal'
    stem='kc2_left_lower_housing'+('_magnetic' if magnetic else '')
    cache=root/CACHE/('left-'+variant);folder=root/STAGE/'lower'/('left-'+variant)
    original_path=cache/'generation.json';old=json.loads(original_path.read_text());validate_original(old,variant)
    frozen=dict(snapshot['source_sha256'])
    for path in [root/CACHE/'snapshot-map.json',*[root/'tools'/(n+'.py') for n in CODE]]:
        name=path.relative_to(root).as_posix();sha=digest(path)
        if name in frozen and frozen[name]!=sha:raise ValueError('Executed helper conflicts with original closure')
        frozen[name]=sha
    verify(root,frozen)
    per=json.loads((root/'.codex-tmp/perimeter-wall-plans.json').read_text())['sides']['left']
    plan=relief_plan(wkt.loads(per['wall_wkt']),wkt.loads(per['floor_addition_wkt']))
    cutters=[prism(xy,lo,hi) for lo,hi,xy in plan['cuts']]
    male=load_protected_males(root,frozen)
    print('import immutable left source and full canonical baseline',variant,flush=True)
    before=cq.importers.importStep(str(cache/(stem+'.step'))).val()
    baseline_path=root/'hardware/MODELS'/(stem+'.step')
    if baseline_path.relative_to(root).as_posix() not in frozen:raise ValueError('Unbound canonical baseline')
    baseline=cq.importers.importStep(str(baseline_path)).val()
    print('exact new-only subtraction and protected baseline/male audit',variant,flush=True)
    after,audit=apply_relief(before,cutters,baseline,male)
    floor=inspect_floor(after)
    if floor['errors']:raise ValueError('Floor lost constant connected 1.2 mm stratum '+str(floor))
    verify(root,frozen)
    print('export STEP and verify roundtrip',variant,flush=True)
    step=folder/(stem+'.step');cq.exporters.export(after,str(step))
    reopened=cq.importers.importStep(str(step)).val();single(reopened)
    if abs(reopened.Volume()-after.Volume())>.002 or max(abs(x-y) for x,y in zip(bounds(reopened),bounds(after)))>1e-6:
        raise ValueError('STEP roundtrip mass/bounds differ')
    stl=folder/(stem+'.stl');cq.exporters.export(after,str(stl),tolerance=.005,angularTolerance=.08)
    binary=stl.read_bytes();normalized,normalization=normalize(binary)
    if stl.read_bytes()!=binary:raise ValueError('Exported STL changed before normalization')
    if normalized!=binary:stl.write_bytes(normalized)
    if digest(stl)!=normalization['output_sha256']:raise ValueError('STL normalization bytes differ')
    mesh=inspect_mesh(stl,after);verify(root,frozen)
    marker=dict(wall_z_mm=[-1,1.5,1.8,4.1],floor_z_mm=[-2.2,-1],ys_mm=[95,117])
    record=dict(requirements=['CON-ARCH-006'],side='left',magnetic=magnetic,body_count=1,
        status='generated_pending_independent_review',source_sha256=frozen,
        ordinary_wall_top_mm=4.1,registrar_top_mm=5.,left_central_relief=marker,
        central_relief_audit=audit,producer_floor_audit=floor,
        relief_tools=[dict(z_mm=[lo,hi],wkt=xy.wkt) for lo,hi,xy in plan['cuts']],
        outputs={step.name:digest(step),stl.name:digest(stl)},mesh=mesh,
        bounds_mm=bounds(after),volume_mm3=after.Volume(),stl_exact_zero_area_normalization=normalization,
        development_provenance=original_path.relative_to(root).as_posix(),physical_qualified=False,canonical_changed=False)
    (folder/'generation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(record['status'],variant,audit,flush=True);return record


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--magnetic',action='store_true')
    parser.add_argument('--snapshot-only',action='store_true');args=parser.parse_args()
    prepare() if args.snapshot_only else generate(args.magnetic)
