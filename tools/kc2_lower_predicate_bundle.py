"""CON-ARCH-006 separate predicate evidence; original failed V2 stays failed.

No canonical writes or publisher integration. Explicit CLI emission validates
all actual source evidence and writes only a separate immutable staged report.
"""
import math,json
from tools.kc2_registered_release_gate import finite,sha_bytes,safe_relative,STAGE,stem
VARIANTS=('normal','magnetic')
SCHEMA='right-lower-predicate-bundle-v1'
RETAINED_ZERO=('new_material_nominal_clearance_obstruction_mm3','pilot_obstruction_mm3',
 'required_missing_mm3','ordinary_wall_upper_gap_obstruction_mm3','canonical_baseline_removed_outside_relief_mm3')
MAGNET_ZERO=('missing_mm3','extra_mm3','blocked_mm3','entry_obstruction_mm3')
ORIGINAL=STAGE+'/lower/right-void-review.json'
DISTANCE=STAGE+'/lower/right-component-distance-review.json'
CERTIFICATE=STAGE+'/lower/right-d8-local-certificate.json'

def exact_zero(value):
    if finite(value)!=0.:raise ValueError('Retained predicate is not exact numeric zero')

def check_current_sources(records,read,required):
    combined={}
    for record in records:
        sources=record.get('source_sha256')
        if not isinstance(sources,dict) or not sources or any(sources.get(n)!=h for n,h in required.items()):raise ValueError('Proof does not bind the same current material')
        for name,sha in sources.items():
            safe_relative(name)
            if name in combined and combined[name]!=sha:raise ValueError('Conflicting original/current source identity')
            if sha_bytes(read(name))!=sha:raise ValueError('Changed current source '+name)
            combined[name]=sha
    return combined

def check_historical(old):
    errors=[v+': component_obstruction_mm3' for v in VARIANTS]
    if old.get('schema')!='lower-void-v2' or old.get('status')!='fail' or old.get('side')!='right' or old.get('native_readback') is not False or len(old.get('errors',[]))!=2 or set(old['errors'])!=set(errors):
        raise ValueError('Not the exact preserved component-only failed V2 scope')
    if set(old.get('variants',{}))!=set(VARIANTS):raise ValueError('Missing historical variant')
    for variant in VARIANTS:
        row=old['variants'][variant]
        if type(row.get('body_count')) is not int or row['body_count']!=2:raise ValueError('Wrong original body identity')
        if finite(row.get('component_obstruction_mm3'))<=0:raise ValueError('Original positive failure measurement missing')
        for key in RETAINED_ZERO:exact_zero(row.get(key))
    magnet=old.get('magnet',{})
    for key in MAGNET_ZERO:exact_zero(magnet.get(key))
    if finite(magnet.get('original_mm3'))<=0 or finite(magnet.get('revised_mm3'))<magnet['original_mm3']:raise ValueError('Missing original magnetic volume evidence')

def bounds(values):
    if not isinstance(values,list) or len(values)!=6:raise ValueError('Missing actual pair bounds')
    result=[finite(v) for v in values]
    if any(result[i]>=result[i+3] for i in range(3)):raise ValueError('Degenerate pair bounds')
    return result

def check_tool_inventory(polygons,certificate):
    from shapely import wkt,get_coordinates
    from shapely.errors import GEOSException
    from shapely.ops import unary_union
    if len(polygons)!=153 or type(certificate.get('actual_tool_count')) is not int or certificate['actual_tool_count']!=153 or certificate.get('required_z_mm')!=[-.4,2.5]:raise ValueError('Wrong complete tool inventory/Z')
    required=wkt.loads(certificate['required_tool_union_wkt'])
    if required.symmetric_difference(unary_union(polygons)).area>1e-9:raise ValueError('Full required XY coverage changed')
    rows=certificate.get('tool_inventory',[])
    if len(rows)!=153:raise ValueError('Missing actual tool geometry inventory')
    for i,(polygon,row) in enumerate(zip(polygons,rows)):
        if type(row.get('tool')) is not int or row['tool']!=i:raise ValueError('Tool order/identity differs')
        text=row.get('expected_wkt')
        if not isinstance(text,str) or sha_bytes(text.encode())!=row.get('expected_sha256'):raise ValueError('Tool WKT identity missing')
        if wkt.loads(text).symmetric_difference(polygon).area>1e-9:raise ValueError('Per-tool geometry differs')
        if any(row.get(k) is not True for k in ('valid','closed','axis_prismatic')) or row.get('vertex_z_mm')!=[-.4,2.5]:raise ValueError('Tool actual prism proof missing')
        actual=bounds(row.get('actual_bounds_mm'));x0,y0,x1,y1=polygon.bounds
        if max(abs(a-b) for a,b in zip(actual,[x0,y0,-.4,x1,y1,2.5]))>1e-6:raise ValueError('Actual tool bounds differ from identified polygon')
        if abs(finite(row.get('actual_volume_mm3'))-polygon.area*2.9)>.002:raise ValueError('Actual tool volume differs')
        section_text=row.get('actual_section_wkt')
        if not isinstance(section_text,str):raise ValueError('Actual tool section geometry missing')
        try:section=wkt.loads(section_text)
        except GEOSException as exc:raise ValueError('Invalid actual tool section WKT') from exc
        if section.geom_type!='Polygon' or section.is_empty or any(not math.isfinite(v) for xy in get_coordinates(section) for v in xy) or not section.is_valid:
            raise ValueError('Actual tool section is not a finite nonempty valid polygon')
        measured={'actual_section_missing_mm2':polygon.difference(section).area,'actual_section_extra_mm2':section.difference(polygon).area}
        for key,computed in measured.items():
            value=finite(row.get(key))
            if not 0<=value<=1e-8 or not 0<=finite(computed)<=1e-8 or abs(value-computed)>1e-10:raise ValueError('Actual tool cross-section geometry/numeric evidence differs')
    return rows

def required_polygons(old):
    from shapely import wkt
    from tools.kc2_required_lower_clearance import required_envelope
    envelope=old['component_envelope']
    wanted={'choc_socket_body_fillets','switch_mechanical_pins','mx_pins_pads_fillets','diode_body_pads_fillets',
      'controller_socket','battery_termination','power_switch_leads','battery_slot'}
    raw=envelope['raw_classes_wkt']
    if set(raw)!=wanted or envelope.get('z_mm')!=[-.4,2.5] or type(envelope.get('quad_segs')) is not int or envelope['quad_segs']!=4:raise ValueError('Wrong component inventory/envelope')
    for field,value in [('required_clearance_mm',.3),('conservative_offset_mm',.301),('circumscribed_buffer_radius_mm',.301/math.cos(math.pi/16))]:
        if abs(finite(envelope.get(field))-value)>1e-10:raise ValueError('Wrong required clearance construction')
    original=wkt.loads(envelope['required_union_wkt']);rebuilt=required_envelope({k:wkt.loads(v) for k,v in raw.items()})
    if not original.is_valid or original.symmetric_difference(rebuilt).area>1e-9:raise ValueError('Full component union mismatch')
    polygons=list(getattr(original,'geoms',[original]))
    if len(polygons)!=153 or any(g.geom_type!='Polygon' or not g.is_valid or g.area<=0 for g in polygons):raise ValueError('Wrong153 required connected tools')
    return polygons

def check_complete_component(distance,certificate,polygons,generations,required):
    from shapely import wkt
    from shapely.geometry import Point
    from tools.kc2_component_local_certificate import validate_certificate
    validate_certificate(certificate);inventory=check_tool_inventory(polygons,certificate)
    if distance.get('schema')!='lower-component-distance-v1' or distance.get('side')!='right' or distance.get('original_boolean_status')!='fail' or distance.get('original_boolean_failure_retained') is not True:raise ValueError('Wrong original full distance evidence')
    if distance.get('bound_padding_mm')!=1e-5 or distance.get('positive_margin_mm')!=1e-4 or set(distance.get('variants',{}))!=set(VARIANTS):raise ValueError('Wrong distance inventory/engineering margin')
    tool=distance['tool'];area=sum(g.area for g in polygons)
    if tool.get('valid') is not True or type(tool.get('solid_count')) is not int or tool['solid_count']!=153 or tool.get('z_mm')!=[-.4,2.5]:raise ValueError('Incomplete distance tool inventory')
    for k,value,tol in [('plan_area_mm2',area,1e-8),('expected_volume_mm3',area*2.9,1e-7),('actual_volume_mm3',area*2.9,.002),('required_clearance_mm',.3,1e-10),('conservative_offset_mm',.301,1e-10),('circumscribed_radius_mm',.301/math.cos(math.pi/16),1e-10)]:
        if abs(finite(tool.get(k))-value)>tol:raise ValueError('Distance tool geometry/volume differs')
    if max(abs(a-b) for a,b in zip(polygons[2].bounds,[15.393103061379296,31.918103061379306,18.156896938620715,38.131896938620706]))>1e-6:raise ValueError('Fallback is not exact documented D8 geometry')
    cases=certificate['cases'];case_map={r['variant']:r for r in cases}
    if len(cases)!=2 or set(case_map)!=set(VARIANTS):raise ValueError('Missing/duplicate local variant proof')
    summaries={};raw_errors=[]
    for variant in VARIANTS:
        case=case_map[variant]
        if type(case.get('part')) is not int or case['part']!=0 or type(case.get('tool')) is not int or case['tool']!=2:raise ValueError('Wrong local pair identity')
        for path_key,sha_key in [('step_path','step_sha256'),('generation_path','generation_sha256')]:
            path=case.get(path_key)
            if path not in required or f'/right-{variant}/' not in path or required[path]!=case.get(sha_key):raise ValueError('Local case not bound to same current variant')
        local=case['local'];roi=local['roi'];seed=local['seed'];xyz=[finite(v) for v in seed['xyz']];point=Point(*xyz[:2])
        actual=wkt.loads(roi['section_wkt']);footprint=wkt.loads(roi['footprint_wkt'])
        if not actual.is_valid or actual.is_empty or actual.area<=0 or not footprint.is_valid or footprint.is_empty or not polygons[2].contains(point) or actual.covers(point) or not -.4<xyz[2]<2.5 or abs(finite(roi['section_z_mm'])-xyz[2])>1e-8:raise ValueError('Actual outside-seed/section identity differs')
        for observed,computed,tol in [(roi['section_area_mm2'],actual.area,1e-8),(roi['tool_overlap_mm2'],actual.intersection(polygons[2]).area,1e-9),(roi['tool_outside_roi_mm2'],polygons[2].difference(footprint).area,1e-10),(seed['section_distance_mm'],actual.distance(point),1e-8)]:
            if abs(finite(observed)-finite(computed))>tol:raise ValueError('Local geometry does not reproduce its numeric evidence')
        if actual.intersection(polygons[2]).area>1e-8 or polygons[2].difference(footprint).area>1e-10:raise ValueError('Local tool overlap or uncovered required XY')
        row=distance['variants'][variant]
        for key,value in [('body_count',2),('tool_count',153),('pair_count',306)]:
            if type(row.get(key)) is not int or row[key]!=value:raise ValueError('Wrong complete pair count')
        result=check_pair_rows(row['pairs'],{(0,2):True});summaries[variant]=result
        if row.get('all_clear') is not (not result['certificate_pairs']) or abs(finite(row['minimum_distance_lower_bound_mm'])-result['raw_minimum_mm'])>1e-10:raise ValueError('Raw status/minimum misrepresented')
        if result['certificate_pairs']:raw_errors.append(variant+' required component clearance not proved')
        parts=generations[variant]['parts']
        if len(parts)!=2:raise ValueError('Missing generation part bounds')
        for pair in row['pairs']:
            for observed,source in [(pair['b_bounds_mm'],inventory[pair['tool']]['actual_bounds_mm']),(pair['a_bounds_mm'],parts[pair['part']]['bounds_mm'])]:
                padded=[finite(v)+(-1e-5 if i<3 else 1e-5) for i,v in enumerate(source)]
                if max(abs(a-b) for a,b in zip(bounds(observed),bounds(padded)))>1e-6:raise ValueError('Actual pair geometry/order differs')
        ab=bounds(parts[0]['bounds_mm']);tb=bounds(inventory[2]['actual_bounds_mm'])
        if not any(ab[i+3]-ab[i]>tb[i+3]-tb[i]+1e-4 for i in range(3)):raise ValueError('Reverse containment not independently excluded')
    if distance.get('errors')!=raw_errors or distance.get('status')!=('fail' if raw_errors else 'pass'):raise ValueError('Original raw distance failures were changed')
    return summaries

def check_pair_rows(rows,certified):
    """Validate raw measurements without changing zero-distance failures.

    `certified` is supplied ONLY after separately validating the actual local
    certificate and its source chain. Only the exact D8 part/tool pair is legal.
    """
    if not isinstance(certified,dict) or any(k!=(0,2) or v is not True for k,v in certified.items()):raise ValueError('Unapproved fallback pair')
    if not isinstance(rows,list) or len(rows)!=306:raise ValueError('Missing/duplicate pair inventory')
    seen=set();measurements=[];fallbacks=[]
    for row in rows:
        if type(row.get('part')) is not int or type(row.get('tool')) is not int:raise ValueError('Noninteger pair identity')
        key=(row['part'],row['tool'])
        if key in seen or key not in {(i,j) for i in range(2) for j in range(153)}:raise ValueError('Wrong/duplicate pair identity')
        seen.add(key);aa=bounds(row.get('a_bounds_mm'));bb=bounds(row.get('b_bounds_mm'))
        if row.get('method')=='outward_padded_aabb':
            measured=max([bb[i]-aa[i+3] for i in range(3)]+[aa[i]-bb[i+3] for i in range(3)])
            if abs(finite(row.get('distance_lower_bound_mm'))-measured)>1e-10 or measured<=1e-4 or row.get('clear') is not True:
                raise ValueError('Invalid conservative AABB separation')
        elif row.get('method')=='solid_solid_extrema':
            measured=finite(row.get('distance_mm'))
            if measured<0 or row.get('is_done') is not True:raise ValueError('Incomplete/invalid solid distance')
            expected=measured>1e-4
            if row.get('clear') is not expected:raise ValueError('Distance status not measurement-derived')
            if not expected:
                if measured!=0. or key not in certified:raise ValueError('Unresolved component distance pair')
                fallbacks.append(key)
        else:raise ValueError('Unknown distance method')
        measurements.append(measured)
    return dict(pair_count=len(seen),raw_minimum_mm=min(measurements),certificate_pairs=fallbacks)

def assemble(read):
    """Validate all actual inputs and return an IN-MEMORY distinct bundle.

    No file writer/CLI is provided. Publication and receiver snapshot integration
    require a separate reviewed change; original reports are never edited.
    """
    payload={p:read(p) for p in (ORIGINAL,DISTANCE,CERTIFICATE)}
    old,distance,certificate=[json.loads(payload[p]) for p in (ORIGINAL,DISTANCE,CERTIFICATE)]
    check_historical(old);polygons=required_polygons(old)
    required={};generations={}
    for variant in VARIANTS:
        folder=f'{STAGE}/lower/right-{variant}';name=stem('lower','right',variant)
        gp=folder+'/generation.json';sp=folder+'/'+name+'.step';raw=read(gp);g=json.loads(raw);step_sha=sha_bytes(read(sp))
        if g.get('status')!='generated_pending_independent_review' or g.get('side')!='right' or g.get('magnetic') is not (variant=='magnetic') or type(g.get('body_count')) is not int or g['body_count']!=2 or g.get('outputs',{}).get(name+'.step')!=step_sha:raise ValueError('Wrong current generation or STEP identity')
        required.update({gp:sha_bytes(raw),sp:step_sha});generations[variant]=g
    combined=check_current_sources([old,distance,certificate],read,required)
    for g in generations.values():
        for name,sha in g.get('source_sha256',{}).items():
            safe_relative(name)
            if name in combined and combined[name]!=sha or sha_bytes(read(name))!=sha:raise ValueError('Conflicting/stale current generation source')
            combined[name]=sha
    # Each method must identify its actually executed implementation, not only
    # contain pass flags or bind the selected STEP.
    code_groups=[(old,['review_kc2_lower_voids_v2.py','test_review_kc2_lower_voids_v2.py']),
      (distance,['review_kc2_lower_component_distance.py','kc2_solid_clearance.py','test_kc2_solid_clearance.py','kc2_required_lower_clearance.py']),
      (certificate,['review_kc2_d8_local_certificate.py','kc2_component_local_certificate.py','test_kc2_component_local_certificate.py','kc2_actual_sections.py'])]
    for record,names in code_groups:
        for name in names:
            path='tools/'+name
            if record['source_sha256'].get(path)!=sha_bytes(read(path)):raise ValueError('Missing current executed checker binding')
    for record in (distance,certificate):
        if record['source_sha256'].get(ORIGINAL)!=sha_bytes(payload[ORIGINAL]):raise ValueError('Original failure identity differs')
    if certificate['source_sha256'].get(DISTANCE)!=sha_bytes(payload[DISTANCE]):raise ValueError('Local certificate does not bind full pair evidence')
    summaries=check_complete_component(distance,certificate,polygons,generations,required)
    combined.update({p:sha_bytes(data) for p,data in payload.items()})
    for path in ('tools/kc2_lower_predicate_bundle.py','tools/test_kc2_lower_predicate_bundle.py','tools/test_kc2_receiver_snapshot.py','tools/kc2_registered_release_gate.py'):
        combined[path]=sha_bytes(read(path))
    if any(sha_bytes(read(n))!=sha for n,sha in combined.items()):raise ValueError('Sources changed during bundle qualification')
    return dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],schema=SCHEMA,status='pass',errors=[],side='right',native_readback=False,
      original_v2_report=ORIGINAL,original_v2_sha256=sha_bytes(payload[ORIGINAL]),original_v2_status=old['status'],original_v2_errors=old['errors'],
      historical_actual_predicate_measurements=old['variants'],historical_actual_magnet_measurements=old['magnet'],
      retained_predicate_names=list(RETAINED_ZERO),component_envelope=old['component_envelope'],
      component_clearance=dict(method='complete_solid_pair_inventory_with_explicit_D8_closed_boundary_and_local_prism_certificate',
        disjointness_proved=True,pair_count=612,tool_count=153,distance_report=DISTANCE,distance_sha256=sha_bytes(payload[DISTANCE]),
        local_certificate=CERTIFICATE,local_certificate_sha256=sha_bytes(payload[CERTIFICATE]),variants=summaries,
        computed_common_volume_mm3=None),
      full_v2_boolean_rerun=False,physical_qualified=False,source_sha256=combined,
      limitations=['Original failed Boolean measurements remain unchanged','Only component predicate uses new disjointness proof; no fabricated Boolean zero','Receiver cleanup/floor/split/entry/native and physical qualification are separate'])

def validate_bundle(record,read):
    expected=assemble(read)
    if json.dumps(record,sort_keys=True)!=json.dumps(expected,sort_keys=True):raise ValueError('Bundle identities/measurements/semantics differ from actual evidence')
    return True


OUTPUT=STAGE+'/lower/right-predicate-bundle.json'


def emit(root=None):
    """Qualify all actual inputs before writing a distinct, immutable proof."""
    from pathlib import Path
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    def read(name):
        safe_relative(name)
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('Source escapes root')
        return path.read_bytes()
    record=assemble(read)
    data=(json.dumps(record,indent=2)+'\n').encode()
    if any(sha_bytes(read(n))!=sha for n,sha in record['source_sha256'].items()):
        raise ValueError('Sources changed before emission')
    output=root/OUTPUT
    if not output.resolve().is_relative_to(root.resolve()):raise ValueError('Output escapes root')
    if output.exists():
        if output.read_bytes()!=data:raise ValueError('Conflicting immutable predicate bundle')
        return record
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream:stream.write(data)
    return record


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Qualify actual evidence and emit separate predicate bundle')
    parser.parse_args()
    emit()
