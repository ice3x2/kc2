"""CON-ARCH-006 independent numeric/section contract for all three plate types.

Does not call the filled-plate producer, its profile table or its fill engine.
Shares the established PCB coordinate extractor, original split and service
envelopes: these are retained interfaces, not independently measured parts.
Source-bound contract comparison is not actual CAD or physical qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
from shapely import affinity,wkt
from shapely.geometry import Point,box
from shapely.ops import unary_union
from tools import generate_kc2_mx_upper_housings as old
from tools.kc2_local_upper_covers import extended_split_masks
from tools.review_kc2_local_upper_covers import approach_geometries
from tools.kc2_solid_plate import Layer

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/solid-filled-plates'


def contract_plan(side,board,kind):
    # CON-ARCH-006 2026-09-13 numerical contract, independently transcribed.
    values={'mx':(7.8,9.3,14.,16.202,7.8,9.3,7.5),
            'choc_v1':(5.3,6.5,14.2,15.3,5.1,6.6,5.),
            'deep_sea':(5.05,6.25,14.2,15.3,5.1,6.6,5.)}[kind]
    bottom,top,aperture,width,bearing,boss_top,screw=values
    profile=dict(zip(['plate_bottom','plate_top','aperture','body_clear_width','bearing','boss_top','screw_length'],values))
    profile['exact_received_part_verified']=False
    geometry=old.lower.legacy_geometry.require_shapely()
    prior=old.upper_plan(geometry,board,old.stack_parameters(plate_top_above_pcb_mm=5.2,clip_thickness_mm=1.5,aperture_mm=14))
    originals=[prior['plate']] if side=='left' else old.split_upper_plan(geometry,board,prior)[0]
    extensions=[board['housing_outline'].buffer(5)] if side=='left' else extended_split_masks(board,prior)
    occupied=unary_union(originals)
    masks=[]
    for i,part in enumerate(originals):
        other=unary_union(originals[:i]+originals[i+1:])
        masks.append(part.union(extensions[i].difference(occupied).difference(other.buffer(.2))))
    raw_width=15.6 if kind=='mx' else 14.7
    allowance=.301 if kind=='mx' else .3
    bodies=[];holes=[]
    for switch in board['switches']:
        x,y=switch['center'];angle=switch['angle_deg']
        bodies.append(affinity.rotate(box(-raw_width/2,-raw_width/2,raw_width/2,raw_width/2).buffer(allowance,quad_segs=32),angle,origin=(0,0)))
        bodies[-1]=affinity.translate(bodies[-1],x,y)
        holes.append(affinity.translate(affinity.rotate(box(-aperture/2,-aperture/2,aperture/2,aperture/2),angle,origin=(0,0)),x,y))
    body=unary_union(bodies);openings=unary_union(holes)
    domain=board['housing_outline'].union(body.buffer(1.201,quad_segs=32))
    centers=[h['housing_center_mm'] for h in board['mounting_holes']]
    bores,pockets,bosses,lands=[unary_union([Point(*c).buffer(r,quad_segs=64) for c in centers]) for r in [.8,1.7,2.3,1.5]]
    routes=approach_geometries(side,board,board['housing_outline'])
    service=unary_union([prior['service']]+[g for name,(g,_,_) in routes.items() if not name.startswith('driver_')])
    levels=sorted({4.1,4.4,bottom,top,bearing,boss_top})
    parts=[]
    for mask in masks:
        rows=[]
        for z0,z1 in zip(levels,levels[1:]):
            z=(z0+z1)/2
            field=lands if z<4.4 else domain if z<top else bosses
            switch_space=body if z<bottom or z>top else openings
            forbidden=unary_union([switch_space,service,bores]+([pockets] if z>bearing else []))
            rows.append(Layer(z0,z1,field.intersection(mask).difference(forbidden)))
        parts.append(rows)
    return dict(side=side,kind=kind,profile=profile,domain=domain,body=body,openings=openings,
                service=service,bores=bores,pockets=pockets,bosses=bosses,lands=lands,
                masks=masks,parts=parts,mounting_centers=centers,switch_count=len(board['switches']))


def check_record(record,expected):
    errors=[]
    for key in ['side','kind','profile','switch_count']:
        if record.get(key)!=expected[key]:errors.append(key.replace('_',' ')+' mismatch')
    if record.get('mounting_centers')!=expected['mounting_centers']:errors.append('mounting centers mismatch')
    for key in ['domain','body','openings','service','bores','pockets','bosses','lands']:
        actual=wkt.loads(record['plan_wkt'][key])
        if actual.symmetric_difference(expected[key]).area>1e-6:errors.append(key+' mismatch')
    if len(record['masks_wkt'])!=len(expected['masks']):errors.append('mask count mismatch')
    for i,(actual,required) in enumerate(zip(record['masks_wkt'],expected['masks'])):
        if wkt.loads(actual).symmetric_difference(required).area>1e-6:errors.append(f'part {i} mask mismatch')
    if len(record['parts'])!=len(expected['parts']):errors.append('part count mismatch')
    for i,(part,required) in enumerate(zip(record['parts'],expected['parts'])):
        if part.get('index')!=i:errors.append(f'part {i} index mismatch')
        actual=[Layer(float(r['z0']),float(r['z1']),wkt.loads(r['wkt'])) for r in part['layers']]
        if any(not r.z0<r.z1 for r in actual):errors.append(f'part {i} invalid interval')
        levels=sorted({z for r in actual+required for z in (r.z0,r.z1)})
        for low,high in zip(levels,levels[1:]):
            z=(low+high)/2
            a=unary_union([r.geometry for r in actual if r.z0<z<r.z1])
            b=unary_union([r.geometry for r in required if r.z0<z<r.z1])
            if a.symmetric_difference(b).area>1e-6:errors.append(f'part {i} fill mismatch');break
    return sorted(set(errors))


def review(side,kind):
    from tools import generate_kc2_magnetic_housings as base
    path=STAGE/f'{side}-{kind}.json'
    record=json.loads(path.read_text(encoding='utf8'))
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    bindings=dict(record['source_sha256'])
    for p in [Path(__file__),ROOT/'tools/test_verify_kc2_filled_plate_contract.py',path]:
        bindings[p.relative_to(ROOT).as_posix()]=digest(p)
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed source: '+name)
    boards,_,_=base.load_plans()
    expected=contract_plan(side,boards[side],kind)
    errors=check_record(record,expected)
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Source changed during review: '+name)
    result=dict(requirements=['CON-ARCH-006','CON-ARCH-007'],status='failed' if errors else 'pass',
                side=side,kind=kind,errors=errors,source_sha256=bindings,
                scope='Independent numeric and complete sectional design contract; actual CAD/native gates separate',
                physical_qualified=False)
    (STAGE/f'{side}-{kind}-contract.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side',required=True,choices=['left','right'])
    parser.add_argument('--kind',required=True,choices=['mx','choc_v1','deep_sea'])
    args=parser.parse_args();result=review(args.side,args.kind)
    print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'}))
    raise SystemExit(0 if result['status']=='pass' else 1)
