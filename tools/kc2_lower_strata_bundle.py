"""CON-ARCH-006 complete conservative normal strata + actual magnetic subset.

Preserves failed original V2 measurements; never claims a 612-pair completion.
"""
import json
import math
from shapely import wkt,get_coordinates
from shapely.geometry import box,Point
from shapely.ops import unary_union
from tools.kc2_registered_release_gate import finite,sha_bytes,safe_relative,STAGE,stem
from tools.kc2_lower_predicate_bundle import check_historical,check_current_sources,required_polygons,RETAINED_ZERO
from tools.kc2_magnetic_subset import validate_metrics

SCHEMA='right-lower-strata-predicate-bundle-v1'
ORIGINAL=STAGE+'/lower/right-void-review.json'
STRATA=STAGE+'/lower/right-normal-strata-review.json'
SUBSET=STAGE+'/lower/right-magnetic-subset-review.json'
OUTPUT=STAGE+'/lower/right-strata-predicate-bundle.json'
LEVELS=(-.4,-.3,.8,.9,1.,1.1,1.2,1.3,1.4,1.5,1.8,2.5)
VARIANTS=('normal','magnetic')
MOUNTS='docs/reports/solid-filled-plates-20260913/right-mx.json'

def geometry(text):
    p=wkt.loads(text)
    if p.geom_type not in ('Polygon','MultiPolygon') or p.is_empty or not p.is_valid or finite(p.area)<=0:
        raise ValueError('Invalid positive material geometry')
    for xy in get_coordinates(p):
        for value in xy:finite(float(value))
    return p

def pilot_inventory(rows,points,with_part=False,masks=None):
    if len(rows)!=len(points):raise ValueError('Missing/extra pilot identity')
    seen=set()
    for row in rows:
        center=row.get('center_mm',[])
        if len(center)!=2:raise ValueError('Missing pilot center')
        center=tuple(finite(v) for v in center)
        matches=[i for i,p in enumerate(points) if math.dist(center,p)<1e-7]
        if len(matches)!=1 or matches[0] in seen or finite(row.get('radius_mm'))!=.55:
            raise ValueError('Wrong/duplicate pilot')
        seen.add(matches[0])
        if with_part:
            part=row.get('part')
            if type(part) is not int or part not in (0,1) or row.get('z_bounds_mm')!=[-.3,2.5]:
                raise ValueError('Wrong pilot ownership/trim')
            if masks is not None and not masks[part].covers(Point(center)):raise ValueError('Pilot not inside declared part')

def measure(row,required):
    material=geometry(row['material_superset_wkt']);gap=finite(material.distance(required));overlap=finite(material.intersection(required).area)
    observed=finite(row.get('clearance_mm'));observed_overlap=finite(row.get('overlap_mm2'))
    if gap<.0001 or overlap!=0 or observed_overlap!=0 or abs(gap-observed)>1e-9:
        raise ValueError('Actual section clearance/geometry differs or conflicts')
    return material,gap

def validate_strata(record,required,points,masks=None):
    if (record.get('schema')!='right-lower-normal-strata-v1' or record.get('status')!='pass' or record.get('errors')!=[]
        or record.get('side')!='right' or record.get('variant')!='normal' or record.get('native_readback') is not False
        or record.get('physical_qualified') is not False or record.get('magnetic_covered') is not False
        or record.get('whole_import_valid') is not True or record.get('whole_import_topology_covered_by_two_solids') is not True
        or finite(record.get('whole_import_positive_volume_mm3'))<=0
        or record.get('computed_boolean_common_volume_mm3','missing') is not None or record.get('full_v2_boolean_rerun') is not False):
        raise ValueError('Unqualified actual normal strata import/scope')
    if type(record.get('required_tool_count')) is not int or record['required_tool_count']!=153 or record.get('required_z_mm')!=[-.4,2.5] or finite(record.get('minimum_required_xy_gap_mm'))!=.0001:
        raise ValueError('Different complete required component scope')
    if geometry(record['required_tool_union_wkt']).symmetric_difference(required).area>1e-9:
        raise ValueError('Required union differs')
    if record.get('levels_mm')!=list(LEVELS) or any(type(v) not in (int,float) for v in record['levels_mm']):
        raise ValueError('Missing/altered actual critical level inventory')
    counts=record.get('face_counts',{})
    if set(counts)!={'PLANE','CYLINDER'} or any(type(v) is not int for v in counts.values()) or counts['PLANE']<=0 or counts['CYLINDER']!=9:
        raise ValueError('Unsupported or incomplete actual boundary topology')
    if len(points)!=9 or len(set(map(tuple,points)))!=9:raise ValueError('Wrong original nine pilot centers')
    pilot_inventory(record['cylinders'],points,True,masks)
    intervals=record.get('intervals',[]);closures=record.get('critical_closures',[])
    if len(intervals)!=11 or len(closures)!=12:raise ValueError('Incomplete interval/closure coverage')
    plans=[];gaps=[]
    for i,row in enumerate(intervals):
        lo,hi=LEVELS[i:i+2]
        if row.get('z_interval_mm')!=[lo,hi] or finite(row.get('z_mm'))!=(lo+hi)/2:raise ValueError('Wrong/duplicate stratum')
        pilot_inventory(row.get('filled_inner_pilots',[]),[] if hi<=-.3 else points)
        material,gap=measure(row,required);plans.append(material);gaps.append(gap)
        if hi>-.3:
            for point in points:
                if not material.covers(Point(point)):raise ValueError('Declared filled pilot missing from material superset')
    allowed={'line_face_with_qualified_inner_pilots_filled','qualified_blind_pilot_cap_outward_aabb'}
    for i,row in enumerate(closures):
        z=LEVELS[i]
        if finite(row.get('z_mm'))!=z:raise ValueError('Missing/duplicate critical closure')
        material,gap=measure(row,required);gaps.append(gap)
        adjacent=unary_union(plans[max(0,i-1):min(len(plans),i+1)])
        if adjacent.difference(material).area>1e-8:raise ValueError('Critical closure loses adjacent actual material')
        methods=row.get('actual_face_methods')
        if not isinstance(methods,list) or any(m not in allowed for m in methods):raise ValueError('Unqualified critical face method')
        caps=methods.count('qualified_blind_pilot_cap_outward_aabb')
        if caps!=(9 if z==-.3 else 0):raise ValueError('Missing/wrong-height blind pilot caps')
        if z==-.3:
            for x,y in points:
                if box(x-.55001,y-.55001,x+.55001,y+.55001).difference(material).area>1e-8:
                    raise ValueError('Qualified cap conservative rectangle missing')
    return dict(interval_count=11,critical_closure_count=12,minimum_xy_gap_mm=min(gaps),
                normal_import_volume_mm3=record['whole_import_positive_volume_mm3'])

def validate_subset(record,generations,required):
    if (record.get('schema')!='right-magnetic-material-subset-v1' or record.get('status')!='pass' or record.get('errors')!=[]
        or record.get('side')!='right' or record.get('native_readback') is not False or record.get('actual_exported_STEP_reimported') is not True
        or record.get('kernel_computed_subset_proved') is not True or record.get('component_qualified') is not False
        or record.get('physical_qualified') is not False or set(record.get('variants',{}))!=set(VARIANTS)):
        raise ValueError('Unqualified actual magnetic subset scope')
    metrics=record['actual_material_comparison'];validate_metrics(metrics)
    for variant in VARIANTS:
        row=record['variants'][variant];folder=STAGE+'/lower/right-'+variant
        gp=folder+'/generation.json';sp=folder+'/'+stem('lower','right',variant)+'.step'
        if (row.get('step_path')!=sp or row.get('generation_path')!=gp or row.get('step_sha256')!=required[sp]
            or row.get('generation_sha256')!=required[gp] or row.get('whole_import_topology_covered_by_two_solids') is not True):
            raise ValueError('Subset uses different actual material/import')
        volumes=[];generation=generations[variant]
        if len(generation.get('parts',[]))!=2:raise ValueError('Missing generation part identities')
        for i,(part,actual) in enumerate(zip(generation['parts'],metrics['parts'])):
            if type(part.get('index')) is not int or part['index']!=i:raise ValueError('Wrong generation part ordering')
            bb=part.get('bounds_mm',[]);actualbb=actual[variant+'_bounds_mm']
            if len(bb)!=6 or max(abs(finite(x)-finite(y)) for x,y in zip(bb,actualbb))>1e-6:
                raise ValueError('Subset actual bounds differ from generation')
            volume=finite(actual[variant+'_volume_mm3']);volumes.append(volume)
            if abs(finite(part.get('volume_mm3'))-volume)>.002:raise ValueError('Subset actual volume differs')
        if abs(finite(row.get('whole_import_positive_volume_mm3'))-sum(volumes))>.002:
            raise ValueError('Subset whole-import volume inconsistent')
    return dict(actual_subset_proved=True,removed_total_mm3=metrics['removed_total_mm3'],body_count=2)

def assemble(read):
    payload={p:read(p) for p in (ORIGINAL,STRATA,SUBSET)}
    original,strata,subset=[json.loads(payload[p]) for p in (ORIGINAL,STRATA,SUBSET)]
    check_historical(original);polygons=required_polygons(original);required={};generations={}
    for variant in VARIANTS:
        folder=STAGE+'/lower/right-'+variant;name=stem('lower','right',variant)
        gp=folder+'/generation.json';sp=folder+'/'+name+'.step';raw=read(gp);g=json.loads(raw);sha=sha_bytes(read(sp))
        if (g.get('status')!='generated_pending_independent_review' or g.get('side')!='right' or g.get('magnetic') is not (variant=='magnetic')
            or type(g.get('body_count')) is not int or g['body_count']!=2 or g.get('outputs',{}).get(name+'.step')!=sha):
            raise ValueError('Wrong current material identity')
        required.update({gp:sha_bytes(raw),sp:sha});generations[variant]=g
    combined=check_current_sources([original,strata,subset],read,required)
    for generation in generations.values():
        sources=generation.get('source_sha256')
        if not isinstance(sources,dict) or not sources:raise ValueError('Missing generation source closure')
        for name,sha in sources.items():
            safe_relative(name)
            if name in combined and combined[name]!=sha or sha_bytes(read(name))!=sha:raise ValueError('Conflicting generation source')
            combined[name]=sha
    groups=[(original,('review_kc2_lower_voids_v2','test_review_kc2_lower_voids_v2')),
            (strata,('review_kc2_lower_strata','kc2_lower_strata','test_kc2_lower_strata','kc2_component_local_certificate','kc2_required_lower_clearance')),
            (subset,('review_kc2_magnetic_subset','kc2_magnetic_subset','test_kc2_magnetic_subset','review_kc2_lower_strata','test_kc2_lower_strata'))]
    for record,names in groups:
        for name in names:
            path='tools/'+name+'.py'
            if record['source_sha256'].get(path)!=sha_bytes(read(path)):raise ValueError('Missing actual executed checker binding')
    original_sha=sha_bytes(payload[ORIGINAL])
    for record in (strata,subset):
        if (record.get('original_v2_report')!=ORIGINAL or record.get('original_v2_sha256')!=original_sha
            or record.get('original_v2_status')!='fail' or record.get('original_v2_errors')!=original['errors']
            or record['source_sha256'].get(ORIGINAL)!=original_sha):raise ValueError('Original failure identity changed')
    if finite(strata.get('original_component_obstruction_mm3'))!=original['variants']['normal']['component_obstruction_mm3']:
        raise ValueError('Original normal failure measurement altered')
    for variant in VARIANTS:
        if finite(subset.get('original_component_obstruction_mm3',{}).get(variant))!=original['variants'][variant]['component_obstruction_mm3']:
            raise ValueError('Original magnetic/subset failure measurement altered')
    mountdata=read(MOUNTS);mountsha=sha_bytes(mountdata)
    if any(record['source_sha256'].get(MOUNTS)!=mountsha for record in (original,strata,subset)):
        raise ValueError('Pilot-center provenance differs')
    points=json.loads(mountdata)['mounting_centers'];masks=[wkt.loads(p['mask_wkt']) for p in generations['normal']['parts']]
    normal=validate_strata(strata,unary_union(polygons),points,masks)
    magnetic=validate_subset(subset,generations,required)
    if abs(normal['normal_import_volume_mm3']-subset['variants']['normal']['whole_import_positive_volume_mm3'])>.002:
        raise ValueError('Strata and subset normal imports differ')
    combined.update({p:sha_bytes(data) for p,data in payload.items()})
    for name in ('kc2_lower_strata_bundle','test_kc2_lower_strata_bundle','kc2_lower_predicate_bundle',
                 'kc2_registered_release_gate','kc2_required_lower_clearance','kc2_magnetic_subset'):
        path='tools/'+name+'.py';sha=sha_bytes(read(path))
        if path in combined and combined[path]!=sha:raise ValueError('Qualifier source conflict')
        combined[path]=sha
    if any(sha_bytes(read(n))!=sha for n,sha in combined.items()):raise ValueError('Source changed during assembly')
    return dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],schema=SCHEMA,status='pass',errors=[],side='right',native_readback=False,
        original_v2_report=ORIGINAL,original_v2_sha256=original_sha,original_v2_status='fail',original_v2_errors=original['errors'],
        historical_actual_predicate_measurements=original['variants'],historical_actual_magnet_measurements=original['magnet'],
        retained_predicate_names=list(RETAINED_ZERO),component_envelope=original['component_envelope'],
        component_clearance=dict(method='complete_normal_strata_with_actual_magnetic_subset',disjointness_proved=True,
            tool_count=153,required_z_mm=[-.4,2.5],normal_strata_report=STRATA,normal_strata_sha256=sha_bytes(payload[STRATA]),
            magnetic_subset_report=SUBSET,magnetic_subset_sha256=sha_bytes(payload[SUBSET]),normal=normal,magnetic=magnetic,
            computed_common_volume_mm3=None),full_v2_boolean_rerun=False,physical_qualified=False,source_sha256=combined,
        limitations=['Original failed Boolean measurements remain unchanged','No claim that 612-pair distance diagnostic completed',
                     'Normal conservative material superset plus independently proven actual magnetic subset',
                     'Receiver cleanup/floor/split/entry/native/STL/physical evidence remain separate'])

def validate_bundle(record,read):
    expected=assemble(read)
    if json.dumps(record,sort_keys=True)!=json.dumps(expected,sort_keys=True):raise ValueError('Strata bundle differs from independently reconstructed evidence')
    return True

def emit(root=None):
    from pathlib import Path
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    def read(name):
        safe_relative(name);path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('Source escapes root')
        return path.read_bytes()
    record=assemble(read);data=(json.dumps(record,indent=2)+'\n').encode()
    if any(sha_bytes(read(n))!=sha for n,sha in record['source_sha256'].items()):
        raise ValueError('Sources changed before immutable emission')
    output=root/OUTPUT
    if not output.resolve().is_relative_to(root.resolve()):raise ValueError('Output escapes root')
    if output.exists():
        if output.read_bytes()!=data:raise ValueError('Conflicting immutable strata bundle')
        return record
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as handle:handle.write(data)
    return record

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Qualify complete normal strata and actual magnetic subset evidence')
    parser.parse_args();emit()
