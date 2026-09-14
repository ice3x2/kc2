"""CON-ARCH-006 / OPS-ARCH-006 release gate and portable byte verifier.

The writer cannot start while any checker adapter/evidence is pending.
--preflight and --verify never write. Transaction tests use temporary repos.
Historical canonical sources require the pinned Git object database offline.
Direct development JSON inputs are provenance bytes, never recursive approval.
"""
import argparse
import json
from pathlib import Path
import subprocess
import os
import math
import shutil
import tempfile
import re
from tools.kc2_registered_release_gate import (
    BASELINE,STAGE,inventory,jobs,stem,job_names,finite,passed,safe_relative,
    sha_bytes,resolve_binding,evidence_destination,check_job_report,
    check_native_links,check_inventory,check_sections)

REPORT='docs/reports/registered-housing-fit-20260913'
OLD_MANIFEST='hardware/MODELS/kc2_filled_plate_manifest.json'
NEW_MANIFEST='hardware/MODELS/kc2_registered_housing_manifest.json'
NEW_GUIDE='hardware/MODELS/PRINT-registered-housings.md'
OLD_GUIDE='hardware/MODELS/PRINT-filled-plates.md'
PUBLICATION_DOCS={NEW_GUIDE:STAGE+'/publication/PRINT-registered-housings.md',
                  'hardware/README.md':STAGE+'/publication/hardware-README.md',
                  'hardware/MODELS/README.md':STAGE+'/publication/models-README.md'}
VERIFY_COMMAND='python -B -m tools.publish_kc2_registered_housings --verify hardware/MODELS/kc2_registered_housing_manifest.json'
CENTRAL_ZERO=('required_left_missing_mm3','required_right_missing_mm3','free_obstruction_mm3',
 'overhead_obstruction_mm3','unintended_overlap_mm3','missing_contact_mm3','rigid_insertion_obstruction_mm3')
MAGNET_ZERO=('external_corridor_obstruction_mm3','original_pocket_obstruction_mm3','back_web_missing_mm3',
 'original_back_web_missing_mm3','original_surround_missing_mm3')
LOWER_VOID_ZERO=('component_obstruction_mm3','new_material_nominal_clearance_obstruction_mm3','pilot_obstruction_mm3',
 'required_missing_mm3','ordinary_wall_upper_gap_obstruction_mm3','canonical_baseline_removed_outside_relief_mm3')
COMPONENT_CLASSES={'choc_socket_body_fillets','switch_mechanical_pins','mx_pins_pads_fillets','diode_body_pads_fillets',
 'controller_socket','battery_termination','power_switch_leads','battery_slot'}

def report_paths():
    result={}
    for family,side,kind in jobs():
        folder=f'{STAGE}/{family}/{side}-{kind}'
        roles=['generation','native-generation','native-review']
        if family=='upper':roles+=['brep-review','mesh-review']
        else:
            roles+=['floor-review','floor-native-review']
            if side=='right':roles+=['floor-capture-review','floor-capture-native-review']
        if family=='upper' and side=='right':roles+=['split-review']
        for role in roles:result[f'{family}:{side}:{kind}:{role}']=folder+'/'+role+'.json'
    for side in ('left','right'):
        for native in ('','-native'):
            result[f'{side}:void{native}']=f'{STAGE}/lower/{side}{native}-void-review.json'
    result['right:void']=f'{STAGE}/lower/right-receiver-strata-transfer.json'
    for side in ('left','right'):
        result[f'{side}:stack']=f'{STAGE}/{side}-stack-review.json'
        for native in ('','-native'):
            result[f'{side}:magnetic-entry{native}']=f'{STAGE}/lower/{side}-magnetic-entry{native}-review.json'
    result.update(central=f'{STAGE}/central/integrated-review.json',
      joined=f'{STAGE}/joined-sweep-plan-review.json',envelopes=f'{STAGE}/actual-envelope-review.json',
      tests=f'{STAGE}/test-execution.json')
    return result

def destination(source):
    safe_relative(source)
    reverse={v:k for k,v in inventory().items()}
    if source in reverse:return reverse[source]
    docreverse={v:k for k,v in PUBLICATION_DOCS.items()}
    if source in docreverse:return docreverse[source]
    if source=='.codex-tmp/perimeter-wall-plans.json':return REPORT+'/evidence/perimeter-wall-plans.json'
    if source.startswith(STAGE+'/'):return evidence_destination(source)
    if source.startswith('.codex-tmp/'):raise ValueError('Unmapped temporary provenance: '+source)
    return source

def close(value,wanted,tol=1e-6):
    if abs(finite(value)-wanted)>tol:raise ValueError('Numerical identity differs')

def zero_fields(row,fields,tol):
    if any(not 0<=finite(row.get(k))<=tol for k in fields):raise ValueError('Actual material/void gate failed')

def check_required_bindings(record,wanted):
    if any(record.get('source_sha256',{}).get(name)!=sha for name,sha in wanted.items()):
        raise ValueError('Actual report does not bind the required current evidence bytes')

def check_guide(text):
    matches=re.findall(r'<!-- kc2-release-guide (.*?) -->',text,re.DOTALL)
    if len(matches)!=1:raise ValueError('Final guide release facts absent')
    facts=json.loads(matches[0]);body=text.replace('<!-- kc2-release-guide '+matches[0]+' -->','')
    expected=dict(status='final_release_payload',physical_qualified=False,silicone_feet='deferred_by_user',
      bridge_mm=5.7,low_profile_plate_support_required=True,scale_percent=100,solid_print_infill_percent=100,
      pcb_bottom_z_mm=2.5,pcb_top_z_mm=4.1,magnet_diameter_mm=2,magnet_thickness_mm=1,
      magnet_original_pocket_depth_mm=1.2,magnet_external_seat_depth_mm=2.8)
    if facts!=expected:raise ValueError('Wrong final guide safety facts')
    if VERIFY_COMMAND not in body or '5.70 mm' not in body or '100%' not in body:raise ValueError('Missing visible final instructions')
    if '초안' in body or re.search(r'\bdraft\b',body,re.IGNORECASE):raise ValueError('Draft cannot be published as current guide')
    for name in inventory():
        if name.endswith('.stl') and '('+name.split('/')[-1]+')' not in body:raise ValueError('Missing exact STL link')
    return facts

def check_central(record):
    passed(record)
    expected={f'{v}-y{y}' for v in ('normal','magnetic') for y in (95,117)}
    if set(record.get('rows',{}))!=expected:raise ValueError('Wrong central variant/contact inventory')
    for row in record['rows'].values():
        passed(row);zero_fields(row,CENTRAL_ZERO,1e-5)
        contact=finite(row.get('expected_contact_mm3'))
        if contact<=1e-5:raise ValueError('No designed contact')
        close(row.get('actual_contact_mm3'),contact,1e-5)

def check_lower_split(record,magnetic,native):
    passed(record)
    if record.get('side')!='right' or record.get('magnetic') is not magnetic or record.get('native_readback') is not native:
        raise ValueError('Wrong lower variant/native identity')
    if finite(record.get('gap_mm'))<.39999:raise ValueError('Insufficient split gap')
    captures=record.get('captures',[])
    if len(captures)!=2 or {r.get('y_mm') for r in captures}!={73.25,86.25}:raise ValueError('Wrong two-key inventory')
    for row in captures:
        close(row.get('root_width_mm'),2);close(row.get('head_diameter_mm'),4.5)
        zero_fields(row,['root_missing_mm3','head_missing_mm3'],.002)
        close(row.get('actual_throat_mm'),2.80008,.005)
        close(row.get('minimum_shoulder_capture_mm'),(4.5-row['actual_throat_mm'])/2)
    motion=record.get('motions',[])
    if len(motion)!=4 or {(r.get('dx'),r.get('dy')) for r in motion}!={(1,0),(-1,0),(0,1),(0,-1)}:
        raise ValueError('Wrong capture motion poses')
    if any(finite(r.get('collision_mm3'))<=.001 for r in motion):raise ValueError('Lost capture')
    floor=record.get('floor',[])
    if len(floor)!=2 or {r.get('part') for r in floor}!={0,1}:raise ValueError('Missing part floor')
    for row in floor:
        close(row.get('section_z'),-1.6)
        if row.get('geometry_type')!='Polygon' or finite(row.get('area_mm2'))<=0:raise ValueError('Disconnected/missing floor')

def check_floor_capture_bindings(record,kind,read):
    folder=f'{STAGE}/lower/right-{kind}';name=stem('lower','right',kind)
    paths=[folder+'/generation.json',folder+'/'+name+'.step']
    paths+=['tools/'+n+'.py' for n in ('review_kc2_floor_receiver','test_review_kc2_floor_receiver',
        'kc2_floor_capture','test_kc2_floor_capture','review_kc2_local_covers','review_kc2_filled_plates')]
    check_required_bindings(record,{p:sha_bytes(read(p)) for p in paths})


def check_floor_capture(record,magnetic,native):
    passed(record)
    if (record.get('schema')!='right-floor-receiver-v1' or record.get('side')!='right'
        or record.get('magnetic') is not magnetic or record.get('native_readback') is not native
        or record.get('physical_qualified') is not False or type(record.get('body_count')) is not int
        or record['body_count']!=2 or record.get('floor_z_mm')!=[-2.2,-1]):raise ValueError('Wrong floor capture identity')
    if finite(record.get('gap_mm'))<.39999:raise ValueError('Insufficient actual split gap')
    zero_fields(record,['overlap_mm3'],1e-5)
    floors=record.get('floor',[])
    if len(floors)!=2 or any(type(r.get('part')) is not int for r in floors) or {r['part'] for r in floors}!={0,1}:
        raise ValueError('Missing actual floor bodies')
    for row in floors:
        if row.get('connected') is not True or row.get('errors')!=[]:raise ValueError('Unqualified constant floor')
        zero_fields(row,['constant_prism_missing_mm3','constant_prism_extra_mm3'],1e-5)
    rows=record.get('captures',[])
    if len(rows)!=2 or {finite(r.get('y_mm')) for r in rows}!={73.25,86.25}:raise ValueError('Missing two capture keys')
    for row in rows:
        y=row['y_mm'];close(row.get('ring_width_mm'),1.2,1e-9)
        close(row.get('ring_area_mm2'),19.649146609453318,1e-7)
        zero_fields(row,['ring_missing_mm3','root_missing_mm3','head_missing_mm3'],1e-5)
        throats=row.get('throats',[])
        if len(throats)!=2 or {finite(r.get('x_mm')) for r in throats}!={81.84375+.35,81.84375+.5}:raise ValueError('Missing actual throat sections')
        for throat in throats:
            close(throat.get('width_mm'),2.80008,.00002)
            close(throat.get('shoulder_mm'),(4.5-throat['width_mm'])/2,1e-9)
        if row.get('motion_roi_xy_mm')!=[78.84375,y-6,90.84375,y+6] or row.get('motion_z_mm')!=[-2.2,-1]:raise ValueError('Wrong complete floor motion ROI')
        motions=row.get('motions',[])
        if len(motions)!=4 or {(finite(m.get('dx_mm')),finite(m.get('dy_mm'))) for m in motions}!={(1,0),(-1,0),(0,1),(0,-1)}:
            raise ValueError('Missing actual capture directions')
        if any(m.get('method')!='actual cropped floor BRep translation/intersection' or finite(m.get('collision_mm3'))<=1e-5 for m in motions):
            raise ValueError('Unproved actual floor capture')


def check_floor(record,side,kind,native,outputs):
    passed(record);count=1 if side=='left' else 2
    if record.get('side')!=side or record.get('magnetic') is not (kind=='magnetic') or record.get('native_readback') is not native:
        raise ValueError('Wrong floor variant/native identity')
    rows=record.get('parts',[])
    if record.get('body_count')!=count or len(rows)!=count or {r.get('part') for r in rows}!=set(range(count)):
        raise ValueError('Wrong actual floor body inventory')
    names={n for n in job_names('lower',side,kind) if n.endswith('.stl')}
    if {r.get('mesh',{}).get('stl') for r in rows}!=names:raise ValueError('Wrong floor STL identity')
    for row in rows:
        if row.get('errors') or row.get('section_type')!='Polygon':raise ValueError('Disconnected/nonprismatic floor')
        if row.get('enclosed_floor_void_count')!=0:raise ValueError('Enclosed floor void remains')
        if row.get('floor_z_mm')!=[-2.2,-1]:raise ValueError('Wrong complete floor stratum')
        close(row.get('floor_thickness_mm'),1.2);close(row.get('section_z_mm'),-1.6)
        if finite(row.get('section_area_mm2'))<=0:raise ValueError('Empty floor')
        mesh=row['mesh']
        if mesh.get('sha256')!=outputs.get(mesh['stl']):raise ValueError('Wrong floor STL bytes')
        if mesh.get('watertight') is not True or mesh.get('winding_consistent') is not True or mesh.get('components')!=1:
            raise ValueError('Invalid actual lower mesh topology')
        volume=finite(mesh.get('volume_mm3'));extents=mesh.get('extents_mm',[])
        if volume<=0 or len(extents)!=3 or any(not 0<finite(v)<=150.001 for v in extents):raise ValueError('Invalid lower print envelope')
        zero_fields(mesh,['bounds_error_mm'],1e-4)
        zero_fields(mesh,['volume_error_mm3'],max(.02,volume*1.000001e-6))

def check_magnetic_entry(record,side,native):
    passed(record)
    if record.get('side')!=side or record.get('native') is not native:raise ValueError('Wrong magnetic access identity')
    if set(record.get('rows',{}))!={'y103','y111'}:raise ValueError('Both actual magnet entries required')
    for row in record['rows'].values():
        zero_fields(row,MAGNET_ZERO,.002)
        close(row.get('corridor_volume_mm3'),math.pi*1.2**2*2.9,1e-5)
        close(row.get('back_web_required_mm3'),math.pi*1.2**2*.6,1e-5)
        if finite(row.get('entry_expected_removed_mm3'))<=.002:raise ValueError('No actual new-wall entry removal')
    delta=record.get('delta',{})
    zero_fields(delta,['expected_vs_actual_missing_mm3','expected_vs_actual_extra_mm3','magnetic_extra_material_mm3'],.002)
    original=finite(delta.get('original_void_mm3'));expected=finite(delta.get('expected_void_mm3'))
    if original<=0 or expected<=original:raise ValueError('Missing original pocket/new entry void')
    close(delta.get('actual_void_mm3'),expected,.004)

def check_lower_void(record,side,native):
    passed(record)
    if record.get('schema')!='lower-void-v2' or record.get('side')!=side or record.get('native_readback') is not native:
        raise ValueError('Wrong current lower void schema/identity')
    if set(record.get('variants',{}))!={'normal','magnetic'}:raise ValueError('Missing lower void variant')
    for row in record['variants'].values():
        if row.get('body_count')!=(1 if side=='left' else 2):raise ValueError('Wrong lower void actual bodies')
        zero_fields(row,LOWER_VOID_ZERO,.002)
    magnet=record.get('magnet',{})
    zero_fields(magnet,['missing_mm3','extra_mm3','blocked_mm3','entry_obstruction_mm3'],.002)
    if finite(magnet.get('original_mm3'))<=0 or finite(magnet.get('revised_mm3'))<magnet['original_mm3']-.002:
        raise ValueError('Original blind magnet voids missing')
    envelope=record.get('component_envelope',{})
    close(envelope.get('required_clearance_mm'),.3);close(envelope.get('conservative_offset_mm'),.301)
    if envelope.get('quad_segs')!=4 or envelope.get('z_mm')!=[-.4,2.5]:raise ValueError('Wrong conservative clearance envelope')
    close(envelope.get('circumscribed_buffer_radius_mm'),.301/math.cos(math.pi/16),1e-8)
    raw=envelope.get('raw_classes_wkt',{})
    if set(raw)!=COMPONENT_CLASSES or any(not isinstance(v,str) or not v for v in raw.values()):
        raise ValueError('Missing actual component class envelope')
    required=envelope.get('required_union_wkt')
    if not isinstance(required,str) or not required or 'EMPTY' in required:raise ValueError('Missing full required envelope')

def check_print_mesh(row):
    if row.get('watertight') is not True or row.get('winding_consistent') is not True or row.get('shells')!=1:
        raise ValueError('Invalid printable topology')
    if finite(row.get('volume_mm3'))<=0:raise ValueError('Nonpositive printable volume')
    bounds=row.get('bounds_mm',[])
    if len(bounds)!=6:raise ValueError('Missing print envelope')
    spans=[finite(bounds[i+3])-finite(bounds[i]) for i in range(3)]
    if min(spans)<=0 or max(spans)>150.001:raise ValueError('Invalid 150 mm print envelope')

def check_expected_levels(record,generation):
    if len(record.get('parts',[]))!=len(generation.get('parts',[])):raise ValueError('Wrong section part count')
    for row,part in zip(record['parts'],generation['parts']):
        expected=sorted({finite(layer[k]) for layer in part['layers'] for k in ('z0','z1')})
        if row.get('levels_mm')!=expected:raise ValueError('Sections omit actual declared height transitions')

def check_supplemental(record,diagnostic,diagnostic_sha):
    passed(record)
    if record.get('schema')!='right-upper-mask-contract-v1':raise ValueError('Unknown supplemental contract schema')
    allowed={'missing structure is not between both split parts','unfilled area wider than nominal split'}
    errors=set(diagnostic.get('errors',[]))
    if diagnostic.get('status')!='failed' or not errors or not errors.issubset(allowed):raise ValueError('Unapproved diagnostic failure')
    if record.get('diagnostic_sha256')!=diagnostic_sha or record.get('diagnostic_errors')!=diagnostic['errors']:
        raise ValueError('Supplemental diagnostic identity differs')
    if record.get('parts')!=diagnostic.get('parts') or len(record.get('parts',[]))!=2:
        raise ValueError('Actual audited parts were replaced')
    if record.get('independent_features')!=diagnostic.get('independent_features') or any(r.get('errors') for r in diagnostic.get('independent_features',[])):
        raise ValueError('Functional failure hidden by supplementation')
    rows=record.get('mask_contract',[])
    if len(rows)!=2 or [r.get('part') for r in rows]!=[0,1]:raise ValueError('Missing perpart supplemental material proof')
    for part,mask in zip(record['parts'],rows):
        check_sections(part);levels=part['levels_mm'];sections=mask.get('sections',[])
        if len(sections)!=len(levels)-1:raise ValueError('Missing supplemental actual stratum')
        for lo,hi,actual,row in zip(levels,levels[1:],part['sections'],sections):
            close(row.get('z0_mm'),lo);close(row.get('z1_mm'),hi);close(row.get('z_mm'),(lo+hi)/2)
            if row.get('errors'):raise ValueError('Supplemental material proof failed')
            for direction in ('missing','extra'):
                observed=finite(actual[direction+'_mm2']);reported=finite(row.get('actual_section_'+direction+'_mm2'))
                close(reported,observed,1e-12)
                contract=finite(row.get('contract_'+direction+'_mm2'));combined=finite(row.get('combined_'+direction+'_bound_mm2'))
                if contract<0 or not 0<=combined<=.001:raise ValueError('Supplemental actual+contract material budget exceeded')
                close(combined,reported+contract,1e-12)

def check_direct_contract(record):
    passed(record)
    if record.get('schema')!='right-upper-direct-mask-contract-v1' or record.get('actual_CAD_reimported') is not True:
        raise ValueError('Direct actual import/contract proof absent')
    parts=record.get('parts',[]);contracts=record.get('independent_contract',[])
    if len(parts)!=2 or len(contracts)!=2 or [r.get('part') for r in contracts]!=[0,1]:raise ValueError('Wrong direct part inventory')
    for actual,contract in zip(parts,contracts):
        check_sections(actual)
        if contract.get('levels_mm')!=actual['levels_mm'] or len(contract.get('sections',[]))!=len(actual['sections']):raise ValueError('Missing independent actual stratum')
        for observed,wanted in zip(actual['sections'],contract['sections']):
            close(wanted.get('z_mm'),observed['z_mm'])
            zero_fields(wanted,['declared_missing_mm2','declared_extra_mm2'],1e-7)
            required=finite(wanted.get('required_area_mm2'))
            if required<0:raise ValueError('Invalid required area')
            close(observed['actual_area_mm2']-required,observed['extra_mm2']-observed['missing_mm2'],1e-6)

def check_stack(record,side):
    passed(record)
    if record.get('side')!=side or set(record.get('variants',{}))!={'normal','magnetic'}:raise ValueError('Wrong stack identity')
    for row in record['variants'].values():
        levels=row.get('levels_mm',[])
        if len(levels)<2 or levels!=sorted(set(levels)):raise ValueError('Missing stack levels')
        if not {2.5,4.1,4.35,4.4,5,5.2}.issubset(set(levels)) or levels[0]!=2.5:
            raise ValueError('Missing actual PCB/registration stack extent')
        if levels!=record['variants']['normal'].get('levels_mm'):raise ValueError('Variant stack heights differ')
        expected={(kind,(finite(lo)+finite(hi))/2) for lo,hi in zip(levels,levels[1:]) if (lo+hi)/2>=4.1
                  for kind in ('mx','choc_v1','deep_sea')}
        checks=row.get('checks',[])
        actual={(c.get('kind'),c.get('z_mm')) for c in checks}
        if actual!=expected or len(checks)!=len(expected):raise ValueError('Missing profile/height stack evidence')
        for c in checks:
            zero_fields(c,['overlap_mm2'],.001)
            if c.get('gap_mm') is not None and finite(c['gap_mm'])<0:raise ValueError('Negative stack gap')

def check_profile(record,kind,generation):
    passed(record)
    if record.get('kind')!=kind or record.get('feature_count')!=2:raise ValueError('Wrong actual upper split identity')
    for key,value in [('clip_ring_nominal_mm',.6),('neck_width_mm',2),('head_diameter_mm',4)]:close(record.get(key),value)
    if finite(record.get('actual_full_projection_gap_mm'))<.39999:raise ValueError('Insufficient actual upper gap')
    bottom,top,bearing,boss={'mx':(7.8,9.3,7.8,9.3),'choc_v1':(5.3,6.5,5.1,6.6),'deep_sea':(5.05,6.25,5.1,6.6)}[kind]
    required={4.1,4.4,bottom,top,bearing,boss}|{finite(layer[k]) for part in generation['parts'] for layer in part['layers'] for k in ('z0','z1')}
    rows=record.get('sections',[])
    if not rows:raise ValueError('Missing whole-height split sections')
    levels=[rows[0].get('z0_mm')]+[r.get('z1_mm') for r in rows]
    if levels!=sorted(set(levels)) or not required.issubset(set(levels)):raise ValueError('Incomplete split height transitions')
    if levels[0]!=min(required) or levels[-1]!=max(required):raise ValueError('Wrong actual split height extent')
    for lo,hi,row in zip(levels,levels[1:],rows):
        close(row.get('z0_mm'),lo);close(row.get('z1_mm'),hi)
        if row.get('errors'):raise ValueError('Actual clip/root/boss/slot section failed')
        areas=row.get('actual_area_mm2',[])
        if len(areas)!=2 or any(finite(v)<0 for v in areas):raise ValueError('Wrong actual split section parts')
        capture=bottom<(lo+hi)/2<top
        if row.get('capture_required') is not capture:raise ValueError('Wrong actual capture height')
        motions=row.get('one_mm_motion_collision_area_mm2',{})
        wanted={'positive_x','negative_x','positive_y','negative_y'} if capture else set()
        if set(motions)!=wanted or any(finite(v)<=1e-6 for v in motions.values()):raise ValueError('Missing actual four-direction capture')

def check_envelopes(record):
    passed(record)
    if record.get('actual_envelope_verified') is not True or record.get('central_contact_audited_separately') is not True:
        raise ValueError('Missing actual envelope/central separation')
    expected={':'.join(job) for job in jobs()}
    if set(record.get('jobs',{}))!=expected:raise ValueError('Wrong ten-job actual envelope inventory')
    for family,side,kind in jobs():
        rows=record['jobs'][':'.join((family,side,kind))]
        names={n for n in job_names(family,side,kind) if n.endswith('.stl')}
        if len(rows)!=len(names) or {r.get('stl') for r in rows}!=names:raise ValueError('Wrong actual STL envelope identity')
        for row in rows:
            passed(row)
            if type(row.get('triangles')) is not int or row['triangles']<=0:raise ValueError('Missing actual triangles')
            zero_fields(row,['outside_projection_area_sum_mm2'],1e-9)
            if row.get('outside_triangle_count')!=0:raise ValueError('Actual triangles outside envelope')
            close(row.get('envelope_allowance_mm'),.005)
    sweep=record.get('expanded_envelope_sweep',{})
    if sweep.get('errors'):raise ValueError('Actual envelope sweep failed')
    wanted=set()
    for kind in ('mx','choc_v1','deep_sea'):
        levels=[-2.2,-1,1.5,1.8,2.5,4.1,5,9.3 if kind=='mx' else 6.6]
        wanted|={(kind,a,b) for a,b in zip(levels,levels[1:])}
    rows=sweep.get('rows',[])
    if len(rows)!=len(wanted) or {(r.get('kind'),*r.get('z',[])) for r in rows}!=wanted:
        raise ValueError('Incomplete actual joined height bands')
    for row in rows:
        zero_fields(row,['outside_central_clearance_violation_mm2'],1e-8)
        if row.get('minimum_gap_mm') is not None and finite(row['minimum_gap_mm'])<0:raise ValueError('Invalid joined gap')

def joined_pairs(kind):
    bands=dict(pcb=(2.5,4.1),old_lower=(-2.2,2.5),perimeter_floor=(-2.2,-1),
      perimeter_wall=(-1,4.1),registrar_floor=(-2.2,-1),registrar_wall=(-1,5),central=(-2.2,1.5),
      upper=(4.1,9.3 if kind=='mx' else 6.6))
    return {(a,b,max(x0,y0),min(x1,y1)) for a,(x0,x1) in bands.items() for b,(y0,y1) in bands.items()
            if max(x0,y0)<min(x1,y1)}

def check_joined(record):
    passed(record)
    if record.get('approach_world_x_mm')!=[-7.8,0] or record.get('central_actual_audit_required') is not True:
        raise ValueError('Wrong full joined approach pose/central gate')
    close(record.get('minimum_clearance_mm'),.3)
    if set(record.get('profiles',{}))!={'mx','choc_v1','deep_sea'}:raise ValueError('Missing joined profile')
    for kind,rows in record['profiles'].items():
        expected=joined_pairs(kind)
        if len(rows)!=len(expected) or {(r.get('left'),r.get('right'),*r.get('z',[])) for r in rows}!=expected:
            raise ValueError('Missing component pairs/full approach bands')
        for row in rows:
            zero_fields(row,['outside_exception_clearance_violation_mm2'],1e-8)
            gap=finite(row.get('minimum_xy_gap_mm'))
            if gap<0:raise ValueError('Invalid joined pair gap')
            exception=row.get('central_exception_applied')
            if type(exception) is not bool:raise ValueError('Missing central exception state')
            eligible=row['z'][1]<=1.8 and row['left'] not in ('pcb','upper') and row['right'] not in ('pcb','upper')
            if exception and not eligible:raise ValueError('Central exception leaked into upper/PCB height')
            if gap<.3-1e-8 and not exception:raise ValueError('Unexcepted joined clearance deficit')

def git_blob(root,name):
    return subprocess.check_output(['git','show',BASELINE+':'+name],cwd=root)

def baseline_inventory(root):
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'hardware/PCB','hardware/GERBER'],cwd=root,text=True).splitlines()
    if len(names)!=16:raise ValueError('Pinned PCB/Gerber inventory must be exactly 16')
    return {name:sha_bytes(git_blob(root,name)) for name in names}

def check_baseline_bytes(root):
    preserved=baseline_inventory(root)
    original={name:sha_bytes(git_blob(root,name)) for name in inventory()}
    for name,sha in (preserved|original).items():
        if sha_bytes((Path(root)/name).read_bytes())!=sha:raise ValueError('Canonical baseline changed before publication: '+name)
    return original,preserved

def publication_eligibility(errors,records,outputs,documents,original,preserved):
    """Aggregate only AFTER all real semantic/source checks have run.

    Not a replacement for preflight validation and not a separate permission
    request: the user already authorized publication. No CLI bypass exists.
    """
    if errors or set(records)!=set(report_paths()) or set(outputs)!=set(inventory()):return False
    if set(documents)!=set(PUBLICATION_DOCS) or set(original)!=set(inventory()) or len(preserved)!=16:return False
    for label,row in records.items():
        expected='generated_pending_independent_review' if label.endswith(':generation') else 'pass'
        if row.get('status')!=expected or row.get('errors') or not row.get('source_sha256'):return False
    return True

def freeze_errors(bindings,read):
    errors=[]
    for name,row in bindings.items():
        try:
            if sha_bytes(read(name))!=row['sha256']:errors.append('Source changed during preflight: '+name)
        except (OSError,ValueError,KeyError,TypeError) as exc:errors.append('Source freeze: '+name+': '+str(exc))
    return errors

def check_void_proof(record,side,native,read):
    if record.get('schema')=='right-receiver-strata-predicate-transfer-v1':
        if side!='right' or native is not False:
            raise ValueError('Strata transfer is right SOURCE proof only')
        from tools.kc2_receiver_bundle_transfer import validate
        if validate(record,read,kind='strata_bundle') is not True:
            raise ValueError('Complete source/subtraction proof did not qualify')
    else:
        check_lower_void(record,side,native)


def check_transfer_source(record,spec,read):
    """Qualify the actual SOURCE predicate before emitting any derived pass."""
    feature,side,kind=spec['feature'],spec['side'],spec['kind']
    if feature=='floor':
        gen=json.loads(read(f'{STAGE}/lower/{side}-{kind}/generation.json'))
        check_floor(record,side,kind,False,gen['outputs'])
    elif feature=='split':check_lower_split(record,kind=='magnetic',False)
    elif feature=='floor-capture':
        if side!='right':raise ValueError('Floor capture belongs to right lower')
        check_floor_capture(record,kind=='magnetic',False)
        check_floor_capture_bindings(record,kind,read)
    elif feature=='void':check_void_proof(record,side,False,read)
    elif feature=='magnetic-entry':check_magnetic_entry(record,side,False)
    else:raise ValueError('Unknown source predicate')

def feature_proof(record,feature,side,kind,native,read):
    """Return source predicate only after explicit exact-native transfer validation.

    False in the return value deliberately preserves SOURCE checker semantics;
    it does not relabel source measurements as a repeated native operation.
    """
    from tools.kc2_lower_native_transfer import SCHEMA,recipe,validate
    if record.get('schema')!=SCHEMA:return record,native
    if not native:raise ValueError('Source actual feature audit cannot be derived')
    return validate(record,recipe(feature,side,kind),read),False

def preflight(root,*,_manifest=None):
    """Collect exact direct-source mappings; deliberately fail closed on absent adapters."""
    root=Path(root);errors=[];records={};bindings={};paths=report_paths()
    def read(name):
        return portable_read(root,_manifest,name) if _manifest is not None else contained(root.resolve(),name).read_bytes()
    for label,name in paths.items():
        try:
            data=read(name);record=json.loads(data);records[label]=record
            if label.endswith(':generation'):
                if record.get('status')!='generated_pending_independent_review':raise ValueError('Generation unfinished')
            else:passed(record)
            bindings[name]=dict(kind='workspace',path=name,sha256=sha_bytes(data),destination=destination(name))
            sources=record.get('source_sha256')
            if not isinstance(sources,dict) or not sources:raise ValueError('Missing source bytes')
            for source,sha in sources.items():
                if _manifest is None:descriptor=resolve_binding(root,source,sha)
                else:
                    if sha_bytes(read(source))!=sha:raise ValueError('Changed portable report source')
                    descriptor=dict(_manifest['bindings'].get(source,dict(kind='workspace',path=source,sha256=sha)))
                if descriptor['kind']=='workspace':descriptor['destination']=destination(source)
                if source in bindings and bindings[source]['sha256']!=sha:raise ValueError('Conflicting source bytes')
                bindings[source]=descriptor
        except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as exc:errors.append(label+': '+str(exc))
    try:
        if _manifest is None:old,preserved=check_baseline_bytes(root)
        else:
            old={name:sha_bytes(git_blob(root,name)) for name in inventory()};preserved=baseline_inventory(root)
            if old!=_manifest.get('original_canonical_sha256') or preserved!=_manifest.get('preserved_pcb_gerber_sha256'):
                raise ValueError('Portable pinned baseline identities differ')
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        errors.append('baseline: '+str(exc));old={};preserved={}
    for family,side,kind in jobs():
        label=f'{family}:{side}:{kind}';folder=f'{STAGE}/{family}/{side}-{kind}';name=stem(family,side,kind)
        try:
            gen=records[label+':generation'];genpath=folder+'/generation.json';step=folder+'/'+name+'.step'
            context=dict(family=family,side=side,kind=kind,label=label,stem=name,count=1 if side=='left' else 2,
              generation=genpath,step=step,generation_sha256=sha_bytes(read(genpath)),step_sha256=sha_bytes(read(step)))
            required={genpath:context['generation_sha256'],step:context['step_sha256']}
            for rid,report in records.items():
                if rid.startswith(label+':') and rid!=label+':generation':check_required_bindings(report,required)
            global_ids=['envelopes',side+':stack']
            if family=='lower':global_ids+=['central',side+':void',side+':void-native',side+':magnetic-entry',side+':magnetic-entry-native']
            for rid in global_ids:
                if rid in records:check_required_bindings(records[rid],required)
            roles={'generation':'generation','native-generation':'native_generation','native-review':'native_review'}
            if family=='upper':roles.update({'brep-review':'brep','mesh-review':'mesh'})
            for role,adapter in roles.items():
                check_job_report(adapter,records[label+':'+role],context)
                if family=='upper' and adapter in ('brep','mesh','native_review'):
                    check_expected_levels(records[label+':'+role],gen)
            if family=='upper' and side=='right':
                brep=records[label+':brep-review']
                if brep.get('schema')=='right-upper-mask-contract-v1':
                    diagnostic_path=folder+'/brep-review-seam-diagnostic.json';raw=read(diagnostic_path);diagnostic=json.loads(raw)
                    check_supplemental(brep,diagnostic,sha_bytes(raw))
                    check_expected_levels(diagnostic,gen)
                    required_diagnostic={**required,**{folder+'/'+n:sha for n,sha in gen['outputs'].items()}}
                    check_required_bindings(diagnostic,required_diagnostic)
                    check_required_bindings(brep,{diagnostic_path:sha_bytes(raw),folder+'/split-review.json':sha_bytes(read(folder+'/split-review.json'))})
                elif brep.get('schema')=='right-upper-direct-mask-contract-v1':
                    check_direct_contract(brep)
                    check_required_bindings(brep,{folder+'/split-review.json':sha_bytes(read(folder+'/split-review.json'))})
            for output,sha in gen['outputs'].items():
                if sha_bytes(read(folder+'/'+output))!=sha:raise ValueError('Generation output bytes changed')
            for part in gen.get('parts',[gen]):check_print_mesh(part['mesh'])
            context['native_generation_sha256']=sha_bytes(read(folder+'/native-generation.json'))
            ng=records[label+':native-generation'];check_native_links(ng,records[label+':native-review'],context)
            if family=='lower':
                native_labels=[label+':floor-native-review',side+':void-native',side+':magnetic-entry-native']
                if side=='right':native_labels.append(label+':floor-capture-native-review')
                for rid in native_labels:
                    if rid in records:check_native_links(ng,records[rid],context)
            for key in ('f3d','readback'):
                output=ng['outputs'][label];file=output['f3d' if key=='f3d' else 'readback_step']
                if sha_bytes(read(folder+'/'+file))!=output[key+'_sha256']:raise ValueError('Native bytes changed')
            if family=='lower' and side=='right':
                for native in (False,True):
                    proof,direct_native=feature_proof(records[label+(':floor-capture-native-review' if native else ':floor-capture-review')],'floor-capture',side,kind,native,read)
                    check_floor_capture(proof,kind=='magnetic',direct_native)
                    check_floor_capture_bindings(proof,kind,read)
            if family=='lower':
                for native in (False,True):
                    proof,direct_native=feature_proof(records[label+(':floor-native-review' if native else ':floor-review')],'floor',side,kind,native,read)
                    check_floor(proof,side,kind,direct_native,gen['outputs'])
            if family=='upper' and side=='right':check_profile(records[label+':split-review'],kind,gen)
        except (OSError,ValueError,KeyError,TypeError) as exc:errors.append(label+': '+str(exc))
    if 'central' in records:
        try:check_central(records['central'])
        except (ValueError,KeyError,TypeError) as exc:errors.append('central: '+str(exc))
    if 'envelopes' in records:
        try:check_envelopes(records['envelopes'])
        except (ValueError,KeyError,TypeError) as exc:errors.append('envelopes: '+str(exc))
    if 'joined' in records:
        try:check_joined(records['joined'])
        except (ValueError,KeyError,TypeError) as exc:errors.append('joined: '+str(exc))
    for side in ('left','right'):
        if side+':stack' in records:
            try:check_stack(records[side+':stack'],side)
            except (ValueError,KeyError,TypeError) as exc:errors.append(side+':stack: '+str(exc))
        for native in (False,True):
            label=side+':magnetic-entry'+('-native' if native else '')
            if label in records:
                try:
                    proof,direct_native=feature_proof(records[label],'magnetic-entry',side,None,native,read)
                    check_magnetic_entry(proof,side,direct_native)
                except (ValueError,KeyError,TypeError) as exc:errors.append(label+': '+str(exc))
            label=side+':void'+('-native' if native else '')
            if label in records:
                try:
                    proof,direct_native=feature_proof(records[label],'void',side,None,native,read)
                    check_void_proof(proof,side,direct_native,read)
                except (ValueError,KeyError,TypeError) as exc:errors.append(label+': '+str(exc))
    document_hashes={}
    for target,source in PUBLICATION_DOCS.items():
        try:
            data=read(source);text=data.decode('utf-8')
            if target==NEW_GUIDE:check_guide(text)
            elif target=='hardware/MODELS/README.md':
                if '(PRINT-registered-housings.md)' not in text or VERIFY_COMMAND not in text or '하판 받침' not in text or '외벽' not in text:
                    raise ValueError('Models entry point lacks current guide/verify/PCB support contract')
            elif '(MODELS/PRINT-registered-housings.md)' not in text:raise ValueError('Hardware entry point lacks current guide link')
            document_hashes[target]=sha_bytes(data)
            bindings[source]=dict(kind='workspace',path=source,sha256=sha_bytes(data),destination=target)
        except (OSError,ValueError,KeyError,TypeError) as exc:errors.append('guide: '+str(exc))
    if 'tests' in records:
        try:
            from tools.kc2_registered_test_evidence import check_evidence,selected_modules
            current={label:record for label,record in records.items() if label!='tests'}
            report_hashes={name:sha_bytes(read(name)) for label,name in paths.items() if label!='tests'}
            check_evidence(records['tests'],selected_modules(current),report_hashes)
        except (OSError,ValueError,KeyError,TypeError) as exc:errors.append('tests: '+str(exc))
    # Never promote a status-only report while its real schema is unimplemented.
    pending=[]
    errors.extend('semantic adapter pending: '+x for x in pending)
    expected_outputs={}
    for family,side,kind in jobs():
        label=f'{family}:{side}:{kind}'
        gen=records.get(label+':generation',{})
        for name,sha in gen.get('outputs',{}).items():
            if 'hardware/MODELS/'+name in inventory():expected_outputs['hardware/MODELS/'+name]=sha
        native=records.get(label+':native-generation',{}).get('outputs',{}).get(label,{})
        if native.get('f3d'):expected_outputs['hardware/MODELS/'+native['f3d']]=native.get('f3d_sha256')
    errors.extend(freeze_errors(bindings,read))
    eligible=publication_eligibility(errors,records,expected_outputs,document_hashes,old,preserved)
    if not eligible and not errors:errors.append('Incomplete exact publication evidence inventory')
    return dict(status='blocked' if errors else 'pass',publication_authorized=eligible,errors=errors,
      report_paths=paths,bindings=bindings,original_canonical_sha256=old,preserved_pcb_gerber_sha256=preserved,
      inventory=inventory(),staged_output_sha256=expected_outputs,document_sha256=document_hashes,physical_qualified=False,silicone_feet='deferred_by_user',
      print_disclosures=['5.7 mm bridge requires printer validation','Low-profile plates require print support; not support-free'])

def verify_bytes(root,manifest):
    """Verify portable bytes, but never mislabel unfinished semantic proof complete."""
    root=Path(root);errors=[]
    try:
        if manifest.get('baseline_revision')!=BASELINE:raise ValueError('Wrong pinned baseline')
        if set(manifest.get('outputs',{}))!=set(inventory()):raise ValueError('Wrong 35 output inventory')
        preserved=baseline_inventory(root)
        if manifest.get('preserved_pcb_gerber_sha256')!=preserved:raise ValueError('Wrong preserved PCB inventory')
        for name,sha in (manifest['outputs']|preserved).items():
            safe_relative(name)
            if sha_bytes((root/name).read_bytes())!=sha:raise ValueError('Changed published bytes: '+name)
        documents=manifest.get('documents',{})
        if set(documents)!={*PUBLICATION_DOCS,OLD_GUIDE}:raise ValueError('Missing current guide/retirement/entry-point inventory')
        for name,sha in documents.items():
            if sha_bytes(contained(root.resolve(),name).read_bytes())!=sha:raise ValueError('Changed publication guide bytes')
        check_guide(contained(root.resolve(),NEW_GUIDE).read_text(encoding='utf-8'))
        oldmanifest=json.loads(contained(root.resolve(),OLD_MANIFEST).read_bytes())
        if oldmanifest!=dict(status='superseded',active_manifest=NEW_MANIFEST,historical_revision=BASELINE,
                             historical_path=OLD_MANIFEST,physical_qualified=False):
            raise ValueError('Old manifest still presents an active/stale approval')
        for logical,row in manifest.get('bindings',{}).items():
            safe_relative(logical)
            if row.get('kind')=='git_blob':
                if logical not in inventory() or row.get('revision')!=BASELINE or row.get('path')!=logical:raise ValueError('Wrong historical binding')
                data=git_blob(root,logical)
            else:
                if row.get('destination')!=destination(logical):raise ValueError('Wrong portable evidence mapping')
                data=(root/row['destination']).read_bytes()
            if sha_bytes(data)!=row.get('sha256'):raise ValueError('Changed source bytes: '+logical)
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as exc:errors.append(str(exc))
    return dict(status='blocked' if errors else 'pass',errors=errors,physical_qualified=False,
                scope='Portable bytes only; not independent semantic approval')

def verify(root,manifest):
    result=verify_bytes(root,manifest)
    if result['errors']:return result
    actual=preflight(root,_manifest=manifest)
    result['errors'].extend(actual['errors'])
    result['status']='blocked' if result['errors'] or actual['status']!='pass' else 'pass'
    result['scope']='Portable bytes plus same real report semantic gates; Git required for historical blobs'
    return result

def contained(root,name):
    safe_relative(name);path=root/name
    if not path.resolve().is_relative_to(root):raise ValueError('Target/source escapes repository: '+name)
    return path

def json_bytes(value):return (json.dumps(value,indent=2,sort_keys=True)+'\n').encode()

def portable_read(root,manifest,logical):
    """Resolve logical pre-publication identities without restoring old active CAD."""
    root=Path(root).resolve();safe_relative(logical)
    reverse={source:target for target,source in inventory().items()}
    if logical in reverse:
        target=reverse[logical];data=contained(root,target).read_bytes()
        expected=manifest.get('outputs',{}).get(target)
    else:
        row=manifest.get('bindings',{}).get(logical)
        if not isinstance(row,dict):raise ValueError('Missing portable source descriptor: '+logical)
        expected=row.get('sha256')
        if row.get('kind')=='git_blob':
            if logical not in inventory() or row.get('revision')!=BASELINE or row.get('path')!=logical:raise ValueError('Wrong historical source identity')
            data=git_blob(root,logical)
        elif row.get('kind')=='workspace':
            if row.get('path')!=logical or row.get('destination')!=destination(logical):raise ValueError('Wrong portable source destination')
            data=contained(root,row['destination']).read_bytes()
        else:raise ValueError('Unknown portable descriptor kind')
    if sha_bytes(data)!=expected:raise ValueError('Portable source bytes changed: '+logical)
    return data

def publish(root):
    """Rollback-capable exact-target transaction. No semantic bypass parameter.

    Missing/failing actual evidence blocks preflight. Tests mock it only inside
    TemporaryDirectory. A crashed process leaves its write-ahead journal
    and exact backups for recovery; no bulk cleanup occurs on rollback failure.
    """
    root=Path(root).resolve();gate=preflight(root)
    if gate.get('status')!='pass' or gate.get('errors') or gate.get('publication_authorized') is not True:
        raise ValueError('Publication preflight blocked')
    if gate.get('inventory')!=inventory():raise ValueError('Exact 35 canonical targets required')
    old,preserved=check_baseline_bytes(root)
    if old!=gate.get('original_canonical_sha256') or preserved!=gate.get('preserved_pcb_gerber_sha256'):
        raise ValueError('Preflight baseline bytes changed')
    payload={};bindings=gate['bindings'];outputs={}
    expected=gate.get('staged_output_sha256',{})
    if set(expected)!=set(inventory()):raise ValueError('Exact validated 35 output hashes required')
    for target,source in inventory().items():
        data=contained(root,source).read_bytes();outputs[target]=sha_bytes(data);payload[target]=data
        if outputs[target]!=expected[target]:raise ValueError('Staged output changed after preflight')
    for source,row in bindings.items():
        if row.get('kind')=='git_blob':continue
        dest=destination(source)
        if row.get('destination')!=dest:raise ValueError('Evidence destination differs')
        data=contained(root,source).read_bytes()
        if sha_bytes(data)!=row.get('sha256'):raise ValueError('Evidence bytes changed before staging')
        if dest in payload and payload[dest]!=data:raise ValueError('Conflicting mapped bytes')
        if dest!=source:payload[dest]=data
    manifest=dict(status='digitally_verified_physical_pending',baseline_revision=BASELINE,
      outputs=outputs,bindings=bindings,report_paths=gate['report_paths'],original_canonical_sha256=old,
      preserved_pcb_gerber_sha256=preserved,physical_qualified=False,new_fabrication_approval=False,
      silicone_feet='deferred_by_user',print_disclosures=gate.get('print_disclosures',[]))
    if set(gate.get('document_sha256',{}))!=set(PUBLICATION_DOCS):raise ValueError('Missing final guide preflight hashes')
    for target,source in PUBLICATION_DOCS.items():
        data=contained(root,source).read_bytes()
        if sha_bytes(data)!=gate['document_sha256'][target]:raise ValueError('Final staged guide changed')
        payload[target]=data
    check_guide(payload[NEW_GUIDE].decode('utf-8'))
    payload[OLD_GUIDE]=('# Superseded housing guide\n\nUse [the current registered-housing guide](PRINT-registered-housings.md).\n\n'
        'This guide is not current verification evidence. Historical content: Git '+BASELINE+':'+OLD_GUIDE+'.\n').encode()
    manifest['documents']={name:sha_bytes(payload[name]) for name in [*PUBLICATION_DOCS,OLD_GUIDE]}
    payload[OLD_MANIFEST]=json_bytes(dict(status='superseded',active_manifest=NEW_MANIFEST,
      historical_revision=BASELINE,historical_path=OLD_MANIFEST,physical_qualified=False))
    payload[NEW_MANIFEST]=json_bytes(manifest)
    for name,data in payload.items():
        path=contained(root,name)
        allowed=name in inventory() or name in (OLD_MANIFEST,NEW_MANIFEST,OLD_GUIDE) or name in PUBLICATION_DOCS or name.startswith(REPORT+'/evidence/')
        if not allowed:raise ValueError('Unapproved publication destination '+name)
        if name not in inventory() and name not in (OLD_MANIFEST,OLD_GUIDE,'hardware/README.md','hardware/MODELS/README.md') and path.exists() and path.read_bytes()!=data:
            raise ValueError('Refusing to overwrite unrelated existing publication evidence '+name)
    # No target changes before complete payload, containment and evidence checks.
    staging=Path(tempfile.mkdtemp(prefix='.kc2-publication-',dir=root))
    if not staging.resolve().is_relative_to(root):raise ValueError('Invalid transaction directory')
    journal=dict(status='prepared',targets=[],completed=[])
    try:
        for index,(name,data) in enumerate(payload.items()):
            target=contained(root,name);new=staging/f'{index}.new';backup=staging/f'{index}.old'
            new.write_bytes(data)
            previous=target.read_bytes() if target.exists() else None
            if previous is not None:backup.write_bytes(previous)
            journal['targets'].append(dict(path=name,new=new.name,backup=backup.name if previous is not None else None,
              original_sha256=sha_bytes(previous) if previous is not None else None,new_sha256=sha_bytes(data)))
        (staging/'journal.json').write_bytes(json_bytes(journal))
        # Revalidate all original targets immediately before the first replace.
        check_baseline_bytes(root)
        for row in journal['targets']:
            target=contained(root,row['path']);current=sha_bytes(target.read_bytes()) if target.exists() else None
            if current!=row['original_sha256']:raise ValueError('Publication target changed during staging')
        for row in journal['targets']:
            target=contained(root,row['path']);target.parent.mkdir(parents=True,exist_ok=True)
            journal['completed'].append(row['path'])
            (staging/'journal.json').write_bytes(json_bytes(journal))
            os.replace(staging/row['new'],target)
        result=verify(root,manifest)
        if result.get('status')!='pass' or result.get('errors'):raise ValueError('Post-publication verification failed: '+str(result))
        for name,sha in preserved.items():
            if sha_bytes(contained(root,name).read_bytes())!=sha:raise ValueError('PCB/Gerber bytes changed')
        journal['status']='committed';(staging/'journal.json').write_bytes(json_bytes(journal))
    except BaseException:
        failed=[]
        for row in reversed(journal['targets']):
            if row['path'] not in journal['completed']:continue
            try:
                target=contained(root,row['path'])
                if row['backup'] is not None:os.replace(staging/row['backup'],target)
                elif target.exists():target.unlink()
            except OSError:failed.append(row['path'])
        if failed:
            journal.update(status='rollback_incomplete',rollback_failed=failed)
            (staging/'journal.json').write_bytes(json_bytes(journal))
            raise RuntimeError('Exact-target rollback incomplete; retain journal '+str(staging))
        shutil.rmtree(staging)
        raise
    shutil.rmtree(staging)
    return dict(status='pass',manifest=NEW_MANIFEST,outputs=len(outputs),preserved_pcb_gerber=len(preserved))

if __name__=='__main__':
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true');mode.add_argument('--verify',type=Path)
    mode.add_argument('--publish',action='store_true')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
    result=preflight(args.root) if args.preflight else publish(args.root) if args.publish else verify(args.root,json.loads(args.verify.read_text()))
    print(json.dumps(result,indent=2));raise SystemExit(result['status']!='pass')
