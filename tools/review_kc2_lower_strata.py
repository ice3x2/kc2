"""CON-ARCH-006 new normal-only complete strata diagnostic; no old report edits."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/registered-housing-fit/lower'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_sources(root,sources):
    if not isinstance(sources,dict) or not sources:raise ValueError('Empty source closure')
    for name,sha in sources.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or digest(path)!=sha:
            raise ValueError('Invalid/changed source '+name)

def validate_import(shape):
    solids=shape.Solids()
    if (not shape.isValid() or not math.isfinite(shape.Volume()) or shape.Volume()<=0 or len(solids)!=2
        or any(not s.isValid() or not math.isfinite(s.Volume()) or s.Volume()<=0 or not s.Shells()
               or any(not sh.Closed() for sh in s.Shells()) for s in solids)):
        raise ValueError('Whole imported shape must contain exactly two valid closed positive solids')
    for kind in ('Faces','Edges','Vertices'):
        whole=list(getattr(shape,kind)());owned=[p for s in solids for p in getattr(s,kind)()]
        if len(whole)!=len(owned):raise ValueError('Extraneous or shared imported topology: '+kind)
        buckets={}
        for p in owned:buckets.setdefault(hash(p),[]).append(p)
        for p in whole:
            candidates=buckets.get(hash(p),[])
            match=next((i for i,q in enumerate(candidates) if p.isSame(q)),None)
            if match is None:raise ValueError('Unowned imported topology: '+kind)
            candidates.pop(match)
        if any(buckets.values()):raise ValueError('Missing imported topology: '+kind)
    return solids

def review():
    import cadquery as cq
    from shapely.ops import unary_union
    from tools.kc2_lower_predicate_bundle import required_polygons
    from tools.kc2_lower_strata import audit_normal
    frozen={}
    def bind(path,expected=None):
        sha=digest(path);key=path.relative_to(ROOT).as_posix()
        if expected is not None and sha!=expected:raise ValueError('Changed source '+key)
        if key in frozen and frozen[key]!=sha:raise ValueError('Source changed during diagnostic '+key)
        frozen[key]=sha;return path
    def read(path):return json.loads(bind(path).read_text())
    original_path=STAGE/'right-void-review.json';original=read(original_path)
    if original.get('schema')!='lower-void-v2' or original.get('side')!='right' or original.get('native_readback') is not False:
        raise ValueError('Wrong original complete component evidence')
    verify_sources(ROOT,original['source_sha256'])
    for name,sha in original['source_sha256'].items():bind(ROOT/name,sha)
    folder=STAGE/'right-normal';gp=folder/'generation.json';generation=read(gp)
    if (generation.get('status')!='generated_pending_independent_review' or generation.get('side')!='right'
        or generation.get('magnetic') is not False or type(generation.get('body_count')) is not int or generation['body_count']!=2):
        raise ValueError('Wrong normal source identity')
    verify_sources(ROOT,generation['source_sha256'])
    for name,sha in generation['source_sha256'].items():bind(ROOT/name,sha)
    step=bind(folder/'kc2_right_lower_housing.step',generation['outputs']['kc2_right_lower_housing.step'])
    for path in (gp,step):
        if original['source_sha256'].get(path.relative_to(ROOT).as_posix())!=digest(path):
            raise ValueError('Original component evidence binds different material')
    mounts_path=ROOT/'docs/reports/solid-filled-plates-20260913/right-mx.json'
    mounts=read(mounts_path)['mounting_centers']
    if len(mounts)!=9 or len({tuple(p) for p in mounts})!=9:raise ValueError('Wrong9 pilot inventory')
    if original['source_sha256'].get(mounts_path.relative_to(ROOT).as_posix())!=digest(mounts_path):
        raise ValueError('Pilot-center source differs from original complete evidence')
    polygons=required_polygons(original)
    if len(polygons)!=153:raise ValueError('Incomplete required component union')
    for name in ('review_kc2_lower_strata.py','kc2_lower_strata.py','test_kc2_lower_strata.py',
                 'kc2_lower_predicate_bundle.py','test_kc2_lower_predicate_bundle.py',
                 'kc2_required_lower_clearance.py','kc2_registered_release_gate.py','kc2_component_local_certificate.py'):
        bind(ROOT/'tools'/name)
    print('Import exact source normal STEP; original distance jobs/reports unchanged',flush=True)
    imported=cq.importers.importStep(str(step)).val();solids=validate_import(imported)
    result=audit_normal(solids,unary_union(polygons),mounts,progress=lambda message:print(message,flush=True))
    verify_sources(ROOT,frozen)
    result.update(requirements=['CON-ARCH-006'],schema='right-lower-normal-strata-v1',
        status='fail' if result['errors'] else 'pass',side='right',variant='normal',native_readback=False,
        required_tool_count=153,required_z_mm=[-.4,2.5],minimum_required_xy_gap_mm=.0001,
        whole_import_valid=True,whole_import_positive_volume_mm3=imported.Volume(),
        whole_import_topology_covered_by_two_solids=True,
        required_tool_union_wkt=unary_union(polygons).wkt,
        original_v2_report=original_path.relative_to(ROOT).as_posix(),original_v2_sha256=digest(original_path),
        original_v2_status=original['status'],original_v2_errors=original['errors'],
        original_component_obstruction_mm3=original['variants']['normal']['component_obstruction_mm3'],
        computed_boolean_common_volume_mm3=None,full_v2_boolean_rerun=False,
        source_sha256=frozen,
        limitations=['Normal only; no magnetic subset proof yet','No old failed numeric measurement overwritten',
                     'Qualified inner pilot holes conservatively filled; not pilot-hole fidelity',
                     'Only exact blind-bottom disk caps admit outward-AABB closure','Physical fit, native and STL fidelity remain separate'])
    output=STAGE/'right-normal-strata-review.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result['errors'],flush=True)
    return result

if __name__=='__main__':raise SystemExit(bool(review()['errors']))
