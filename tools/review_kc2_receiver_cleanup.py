"""CON-ARCH-006 independent reimported STEP cleanup delta, not physical proof."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from shapely import wkt
from shapely.geometry import box
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/registered-housing-fit'
PARENT_ORIGINAL='.codex-tmp/registered-housing-fit/lower/right-void-review.json'
PARENT_BUNDLE='.codex-tmp/registered-housing-fit/lower/right-predicate-bundle.json'
PARENT_STRATA='.codex-tmp/registered-housing-fit/lower/right-strata-predicate-bundle.json'
ZERO_FIELDS=('added_mm3','off_cutter_removed_mm3','part_a_missing_mm3','part_a_extra_mm3',
             'expected_removal_missing_mm3','expected_removal_extra_mm3','required_stock_removed_mm3',
             'floor_removed_mm3','floor_added_mm3','protected_roles_removed_mm3',
             'pocket_entry_protected_material_removed_mm3','remaining_candidate_mm3')
V2_FIELDS=('component_obstruction_mm3','new_material_nominal_clearance_obstruction_mm3',
           'pilot_obstruction_mm3','required_missing_mm3','ordinary_wall_upper_gap_obstruction_mm3',
           'canonical_baseline_removed_outside_relief_mm3')
ROLE_NAMES={'support_posts','rail','mounting_lands','reset_local_support',
            'existing_reinforced_socket_covers','new_perimeter_wall',
            'registrar_top_a','registrar_top_b','registrar_outer'}

def numeric(value):return type(value) in (int,float) and math.isfinite(value)
def exact_zero(value):return numeric(value) and value==0
def validate_roles(roles):
    if set(roles)!=ROLE_NAMES:raise ValueError('Missing or unknown protected roles')

def individual_metrics_valid(row,strict=False):
    details=row.get('required_stock_details_mm3')
    count=row.get('required_stock_count')
    roles=row.get('protected_role_details_mm3')
    if type(count) is not int or count<1 or not isinstance(details,list) or len(details)!=count:return False
    if not isinstance(roles,dict) or set(roles)!=ROLE_NAMES:return False
    values=details+list(roles.values())
    return all(exact_zero(v) if strict else numeric(v) and 0<=v<=.002 for v in values)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def subtract(a,b):
    import cadquery as cq
    if not a.Solids() or not b.Solids():return a
    pieces=[subject.cut(*b.Solids()) for subject in a.Solids()]
    return cq.Compound.makeCompound([s for p in pieces for s in p.Solids()])

def intersection(a,b):
    import cadquery as cq
    if not a.Solids() or not b.Solids():return cq.Compound.makeCompound([])
    pieces=[subject.intersect(tool) for subject in a.Solids() for tool in b.Solids()]
    return cq.Compound.makeCompound([s for p in pieces for s in p.Solids()])

def audit_variant(before,after,cutter,floor,protected,required,pocket_region):
    if len(before)!=2 or len(after)!=2 or any(not p.isValid() or len(p.Solids())!=1 for p in before+after):
        raise ValueError('Expected two valid matched solids')
    before=sorted(before,key=lambda p:p.Center().x);after=sorted(after,key=lambda p:p.Center().x)
    if any(abs(a.Center().x-b.Center().x)>1 for a,b in zip(before,after)):
        raise ValueError('Ambiguous spatial body matching')
    olda,oldb=before;newa,newb=after
    removed=subtract(oldb,newb);expected=intersection(oldb,cutter)
    protected_metrics={k:intersection(removed,v).Volume() for k,v in protected.items()}
    required_metrics=[intersection(removed,r).Volume() for r in required]
    row=dict(body_count=2,matched_body_count=2,valid_solids=True,removed_mm3=removed.Volume(),
        added_mm3=subtract(newb,oldb).Volume(),off_cutter_removed_mm3=subtract(removed,cutter).Volume(),
        part_a_missing_mm3=subtract(olda,newa).Volume(),part_a_extra_mm3=subtract(newa,olda).Volume(),
        expected_removal_missing_mm3=subtract(expected,removed).Volume(),
        expected_removal_extra_mm3=subtract(removed,expected).Volume(),
        required_stock_removed_mm3=sum(required_metrics),required_stock_details_mm3=required_metrics,
        required_stock_count=len(required_metrics),
        floor_removed_mm3=intersection(removed,floor).Volume(),
        floor_added_mm3=intersection(subtract(newb,oldb),floor).Volume(),
        protected_roles_removed_mm3=sum(protected_metrics.values()),protected_role_details_mm3=protected_metrics,
        pocket_entry_protected_material_removed_mm3=0 if pocket_region is None else intersection(removed,pocket_region).Volume(),
        remaining_candidate_mm3=intersection(newb,cutter).Volume())
    return row,removed

def transfer_eligible(variants,paired,parent_predicates_qualified):
    if parent_predicates_qualified is not True or set(variants)!={'normal','magnetic'}:return False
    for row in variants.values():
        if any(type(row.get(k)) is not int or row[k]!=2 for k in ('body_count','matched_body_count')) or row.get('valid_solids') is not True:return False
        if not numeric(row.get('removed_mm3')) or row['removed_mm3']<=0:return False
        if any(not exact_zero(row.get(k)) for k in ZERO_FIELDS):return False
        if not individual_metrics_valid(row,strict=True):return False
    return all(exact_zero(paired.get(k)) for k in ('normal_minus_magnetic_mm3','magnetic_minus_normal_mm3'))

def resolve_historical(root,snapshot,name,expected):
    if snapshot.get('historical_original_sha256',{}).get(name)!=expected:
        raise ValueError('Historical identity not in immutable snapshot: '+name)
    target=name
    for prefix,replacement in sorted(snapshot['path_mapping'].items(),key=lambda x:-len(x[0])):
        if name==prefix or name.startswith(prefix+'/'):
            target=replacement+name[len(prefix):];break
    path=(root/target).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Unsafe snapshot alias')
    if snapshot['source_sha256'].get(target)!=expected or digest(path)!=expected:
        raise ValueError('Snapshot bytes changed: '+target)
    return path

def historical_reader(root,snapshot,bind=None):
    """Read original logical identities solely through the sealed hash closure."""
    def read(name):
        expected=snapshot.get('historical_original_sha256',{}).get(name)
        if not isinstance(expected,str):raise ValueError('Unlisted historical source '+name)
        path=resolve_historical(root,snapshot,name,expected)
        if bind is not None:bind(path,expected)
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Historical read changed '+name)
        return data
    return read

def qualify_parent(root,snapshot,bind=None):
    kind=snapshot.get('parent_proof_kind')
    logical={'direct_v2':PARENT_ORIGINAL,'predicate_bundle':PARENT_BUNDLE,
             'strata_bundle':PARENT_STRATA}.get(kind)
    if logical is None or snapshot.get('parent_proof_path')!=logical:
        raise ValueError('Missing or inconsistent explicit parent selector')
    read=historical_reader(root,snapshot,bind)
    data=read(logical);sha=hashlib.sha256(data).hexdigest()
    if snapshot.get('parent_proof_sha256')!=sha:raise ValueError('Parent selector hash differs')
    old_data=read(PARENT_ORIGINAL);old=json.loads(old_data)
    if old.get('schema')!='lower-void-v2' or old.get('side')!='right' or old.get('native_readback') is not False:
        raise ValueError('Wrong original V2 identity')
    for name,expected in old['source_sha256'].items():
        if hashlib.sha256(read(name)).hexdigest()!=expected:raise ValueError('Original source closure mismatch')
    exact=all(exact_zero(old.get('variants',{}).get(v,{}).get(k)) for v in ('normal','magnetic') for k in V2_FIELDS)
    exact=exact and all(type(old.get('variants',{}).get(v,{}).get('body_count')) is int and old['variants'][v]['body_count']==2 for v in ('normal','magnetic'))
    if kind=='direct_v2':
        if old.get('status')!='pass' or old.get('errors')!=[] or not exact:
            raise ValueError('Direct V2 parent did not pass with exact zeros')
        for key in ('missing_mm3','extra_mm3','blocked_mm3','entry_obstruction_mm3'):
            if not exact_zero(old.get('magnet',{}).get(key)):raise ValueError('Direct V2 magnetic predicate nonzero')
        method='direct_v2_actual_boolean';common=0
    else:
        import importlib
        module_names=('kc2_lower_predicate_bundle','kc2_registered_release_gate',
                      'kc2_required_lower_clearance')
        if kind=='strata_bundle':
            module_names+=('kc2_lower_strata_bundle','kc2_lower_strata','kc2_magnetic_subset')
        else:
            module_names+=('kc2_component_local_certificate',)
        bundle=importlib.import_module('tools.'+('kc2_lower_strata_bundle' if kind=='strata_bundle' else 'kc2_lower_predicate_bundle'))
        # Execute exactly the archived qualifier revision, not a silently newer
        # helper over historical records. The helper itself is never rewritten.
        for module_name in module_names:
            module=importlib.import_module('tools.'+module_name)
            loaded=Path(module.__file__).resolve();helper_data=read('tools/'+module_name+'.py')
            if loaded.read_bytes()!=helper_data:raise ValueError('Loaded bundle qualifier differs from archived revision')
            if bind is not None:bind(loaded,hashlib.sha256(helper_data).hexdigest())
        record=json.loads(data)
        if old.get('status')!='fail' or exact or record.get('original_v2_status')!='fail':
            raise ValueError('Original component failure must remain failed')
        if record.get('component_clearance',{}).get('computed_common_volume_mm3','missing') is not None:
            raise ValueError('Bundle must not invent a Boolean common-volume zero')
        if kind=='strata_bundle' and (record.get('component_clearance',{}).get('method')!='complete_normal_strata_with_actual_magnetic_subset'
                or record.get('component_clearance',{}).get('disjointness_proved') is not True):
            raise ValueError('Wrong explicit strata component method')
        if bundle.validate_bundle(record,read) is not True:raise ValueError('Full predicate bundle not independently qualified')
        method=('whole_normal_z_strata_plus_actual_magnetic_subset' if kind=='strata_bundle'
                else 'complete_pair_inventory_and_local_prism_certificate');common=None
    archived=resolve_historical(root,snapshot,logical,sha).relative_to(root).as_posix()
    return dict(kind=kind,logical_report=logical,archived_report=archived,sha256=sha,
        original_v2_status=old['status'],original_v2_sha256=hashlib.sha256(old_data).hexdigest(),
        old_v2_exact_zero=exact,predicates_qualified=True,component_method=method,
        component_common_volume_mm3=common,
        original_component_obstruction_mm3={v:old['variants'][v]['component_obstruction_mm3'] for v in ('normal','magnetic')})

def review():
    import cadquery as cq
    from tools.review_kc2_local_covers import prism
    from tools.kc2_lower_central_relief import wall_bands,floor_relief
    from tools.kc2_magnetic_entry import entry_tools
    cache=STAGE/'lower-development/receiver-cleanup-inputs';frozen={}
    def bind(path,expected=None):
        sha=digest(path);key=path.relative_to(ROOT).as_posix()
        if expected is not None and sha!=expected:raise ValueError('Changed binding '+key)
        if key in frozen and frozen[key]!=sha:raise ValueError('Changed during review '+key)
        frozen[key]=sha;return path
    def read(path):return json.loads(bind(path).read_text())
    snapshot=read(cache/'snapshot-map.json')
    if snapshot.get('status')!='verified_historical_snapshot':raise ValueError('Missing immutable archive')
    for name,sha in snapshot['historical_original_sha256'].items():bind(resolve_historical(ROOT,snapshot,name,sha),sha)
    parent=qualify_parent(ROOT,snapshot,bind)
    oldvoid=read(cache/'right-void-review.json')
    if digest(cache/'right-void-review.json')!=parent['original_v2_sha256']:
        raise ValueError('Archived geometry report differs from qualified parent original')
    for name,sha in oldvoid['source_sha256'].items():bind(resolve_historical(ROOT,snapshot,name,sha),sha)
    plan=read(cache/'right-normal/receiver-cleanup-plan.json')
    candidate=read(cache/'right-normal/receiver-cleanup-candidate.json')
    supports=read(cache/'right-normal/receiver-supports-plan.json')
    validate_roles(supports['roles_wkt'])
    if plan.get('cut_z_mm')!=[-1.,2.5] or {r['y_mm'] for r in plan['rows']}!={73.25,86.25}:
        raise ValueError('Wrong cleanup dimensions')
    candidates={r['y_mm']:wkt.loads(r['cut_wkt']) for r in candidate['rows']}
    cuts=[]
    for r in plan['rows']:
        expected=candidates[r['y_mm']].buffer(.002,quad_segs=8);actual=wkt.loads(r['cutter_wkt'])
        if expected.symmetric_difference(actual).area>1e-10:raise ValueError('Cutter differs from fixed .002 offset')
        cuts.append(actual)
    footprint=unary_union(cuts)
    roles={k:wkt.loads(v) for k,v in supports['roles_wkt'].items()}
    if any(footprint.intersects(v) for v in roles.values()):raise ValueError('Plan touches protected role')
    cutter=prism(footprint,-1,2.5)
    protected={k:prism(v,-1,5) for k,v in roles.items()}
    pername='.codex-tmp/perimeter-wall-plans.json'
    per=read(resolve_historical(ROOT,snapshot,pername,oldvoid['source_sha256'][pername]))['sides']['right']
    for name in ('review_kc2_receiver_cleanup.py','test_review_kc2_receiver_cleanup.py',
                 'review_kc2_local_covers.py','kc2_lower_central_relief.py','kc2_magnetic_entry.py'):
        path=ROOT/'tools'/name;bind(path)
        historical='tools/'+name
        if historical in oldvoid['source_sha256'] and digest(path)!=oldvoid['source_sha256'][historical]:
            raise ValueError('Historical geometry helper changed')
    rows={};removed={}
    for variant in ('normal','magnetic'):
        print('Reimport archived and final STEP',variant,flush=True)
        oldfolder=cache/('right-'+variant);newfolder=STAGE/'lower'/('right-'+variant)
        oldgen=read(oldfolder/'generation.json');newgen=read(newfolder/'generation.json')
        stem='kc2_right_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step'
        for gen,folder,archived in ((oldgen,oldfolder,True),(newgen,newfolder,False)):
            if type(gen.get('body_count')) is not int or gen['body_count']!=2 or gen.get('side')!='right' or gen.get('magnetic') is not (variant=='magnetic') or gen.get('status')!='generated_pending_independent_review':raise ValueError('Wrong generation identity')
            for name,sha in gen['source_sha256'].items():
                bind(resolve_historical(ROOT,snapshot,name,sha) if archived else ROOT/name,sha)
            bind(folder/stem,gen['outputs'][stem])
        before=cq.importers.importStep(str(oldfolder/stem)).solids().vals()
        after=cq.importers.importStep(str(newfolder/stem)).solids().vals()
        mask=unary_union([wkt.loads(p['mask_wkt']) for p in oldgen['parts']]);masktool=prism(mask,-2.3,5.1)
        required=[prism(g,a,b) for a,b,g in wall_bands(wkt.loads(per['wall_wkt']))]
        required.append(prism(floor_relief(wkt.loads(per['floor_addition_wkt'])),-2.2,-1))
        for r in oldgen['registrars'].values():
            required.extend([prism(wkt.loads(r['wall']),-1,5),prism(wkt.loads(r['floor_addition']),-2.2,-1)])
        required=[intersection(r,masktool) for r in required]
        if variant=='magnetic':
            for entry in entry_tools('right'):required=[subtract(r,entry) for r in required]
        floor=prism(box(-10,-10,210,150),-2.2,-1)
        pocket=prism(box(147,100,153,114),-2.2,5.1)
        rows[variant],removed[variant]=audit_variant(before,after,cutter,floor,protected,required,pocket)
    paired=dict(normal_minus_magnetic_mm3=subtract(removed['normal'],removed['magnetic']).Volume(),
                magnetic_minus_normal_mm3=subtract(removed['magnetic'],removed['normal']).Volume())
    errors=[v+': '+k for v,r in rows.items() for k in ZERO_FIELDS if not math.isfinite(r[k]) or r[k]>.002 or r[k]<0]
    errors += [v+': individual required/role metrics invalid' for v,r in rows.items() if not individual_metrics_valid(r)]
    errors += [v+': no removal' for v,r in rows.items() if r['removed_mm3']<=0]
    errors += [k for k,v in paired.items() if not math.isfinite(v) or v>.002 or v<0]
    for name,sha in frozen.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed during actual audit '+name)
    result=dict(requirements=['CON-ARCH-006'],schema='right-receiver-cleanup-delta-v2',
        status='fail' if errors else 'pass',errors=errors,side='right',native_readback=False,
        actual_exported_STEP_reimported=True,variants=rows,paired_removal=paired,
        cut_z_mm=[-1,2.5],ys_mm=[73.25,86.25],old_v2_exact_zero=parent['old_v2_exact_zero'],
        parent_evidence=parent,parent_predicates_qualified=parent['predicates_qualified'],
        strict_transfer_eligible=transfer_eligible(rows,paired,parent['predicates_qualified']),source_sha256=frozen,
        physical_qualified=False,scope='Independent exported STEP delta only; fresh floor/split/magnetic-entry/native/assembly reviews remain separate.')
    output=STAGE/'lower/right-receiver-cleanup-review.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'}),flush=True)
    return result

if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    raise SystemExit(bool(review()['errors']))
