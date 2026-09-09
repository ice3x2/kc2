"""CON-ARCH-006: source-bound actual STEP sections and nominal enclosure fit.

Physical printer, exact keycap/supplied-part fit and magnetic force remain open.
"""
import argparse
import json
import math
from pathlib import Path
import cadquery as cq
from shapely import wkt
from shapely.geometry import Polygon
from shapely.ops import unary_union
from tools import generate_kc2_enclosed_housings as gen
from tools import generate_kc2_x3_v2_housings as lower


def section_plan(shape,z):
    faces=cq.Workplane(obj=shape).section(z).faces().vals()
    def coords(wire):return [(p.x,p.y) for p in wire.sample(.0001)[0]]
    return unary_union([Polygon(coords(f.outerWire()),[coords(w) for w in f.innerWires()]) for f in faces])


def coverage(actual,expected):
    return {'missing_area_mm2':expected.difference(actual.buffer(.002)).area,
            'extra_area_mm2':actual.difference(expected.buffer(.002)).area,
            'section_curve_deflection_mm':.0001,'comparison_allowance_mm':.002}


def magnet_backing(q):
    return cq.Solid.makeCylinder(1.2,.6,
        cq.Vector(q['x']+q['sign']*1.2,q['y'],q['z']),cq.Vector(q['sign'],0,0))


def audit(side):
    folder=gen.STAGING
    manifest=json.loads((folder/f'{side}-generation.json').read_text(encoding='utf8'))
    if manifest['status']!='generated_not_independently_verified':raise ValueError('Incomplete generation')
    errors=[];report={'requirements':['CON-ARCH-006','OPS-ARCH-006'],'side':side,'errors':errors,
                      'physical_qualified':False,'sections':{},'magnetic':{},'source_sha256':{}}
    for path,sha in manifest['source_sha256'].items():
        if gen.digest(gen.ROOT/path)!=sha:errors.append('Generation source changed: '+path)
    plans,enclosures,transform=gen.design_plans()
    p=plans[side];e=enclosures[side]
    if transform!=manifest['transform']:errors.append('Joined transform changed')
    masks=[wkt.loads(v) for v in manifest['lower_masks_wkt']]
    floor=unary_union(masks)
    ring=unary_union([e['wall'].intersection(m) for m in masks])
    shapes={k:cq.importers.importStep(str(folder/f'kc2_{side}_{k}_housing.step')).val()
            for k in ['lower','mx_upper']}
    magnetic=cq.importers.importStep(str(folder/f'kc2_{side}_lower_housing_magnetic.step')).val()
    for key,shape in [*shapes.items(),('lower_magnetic',magnetic)]:
        print(side,key,'actual validity/sections',flush=True)
        if not shape.isValid() or len(shape.Solids())!=(1 if side=='left' else 2):errors.append(key+': invalid solids')
        report['sections'][key]={}
        for z in ([-1.6,-.6,2.,3.3,4.05] if key!='mx_upper' else [4.15,5.,7.7,8.5]):
            actual=section_plan(shape,z)
            if key=='mx_upper':
                expected=unary_union([wkt.loads(s['wall_wkt']) for s in manifest['wall_seats']])
            else:expected=floor if z< -1 else ring
            result=coverage(actual,expected)
            result['outside_declared_enclosure_mm2']=actual.difference(e['outer'].buffer(.002)).area
            if result['outside_declared_enclosure_mm2']>.01:errors.append(key+': exceeds joined-clearance outline')
            # Below the PCB, internal supports are expected extra material.
            if result['missing_area_mm2']>.01:errors.append(f'{key}: missing wall/floor at{z}')
            if 2.5<z<4.1:
                pcb_collision=actual.intersection(p['board'].buffer(.299)).area
                result['pcb_clearance_collision_mm2']=pcb_collision
                if pcb_collision>.001:errors.append(key+': PCB shell clearance')
            if -.4<z<2.5:
                collision={name:actual.intersection(raw.buffer(.299,quad_segs=4)).area
                           for name,raw in p['component_geometries'].items() if not raw.is_empty}
                result['bottom_component_intersections_mm2']=collision
                if any(v>.005 for v in collision.values()):errors.append(key+': underside component section')
            if key=='mx_upper' and z<7.8:
                services={'switch_body':p['switch_service_body_geometry'],
                          'controller_socket':p['feature_geometries']['controller_socket'].convex_hull,
                          **p['mounting_service_geometries'],'reset':p['reset_actuator_geometry']}
                result['top_component_intersections_mm2']={name:actual.intersection(raw).area
                                            for name,raw in services.items() if not raw.is_empty}
                if any(v>.005 for v in result['top_component_intersections_mm2'].values()):
                    errors.append(f'{key}: top component at{z}')
            report['sections'][key][str(z)]=result
    expected_removed=2*math.pi*1.2**2*1.2
    removed=shapes['lower'].Volume()-magnetic.Volume()
    report['magnetic']['removed_mm3']=removed
    if abs(removed-expected_removed)>.005:errors.append('Magnet cut not two complete blind cylinders')
    for q in manifest['pockets']:
        obstruction=magnetic.intersect(gen.magnet.pocket_cutter(q['x'],q['y'],q['sign'])).Volume()
        backing=magnet_backing(q)
        missing_backing=backing.cut(magnetic).Volume()
        report['magnetic'][str(q['y'])]={'obstruction_mm3':obstruction,
            'full_disk_0_6_mm_backing_missing_mm3':missing_backing}
        if obstruction>.001:errors.append('Obstructed magnet hole')
        if missing_backing>.001:errors.append('Incomplete magnet blind backing')
    print(side,'service corridors and wall seating',flush=True)
    usb=gen.usb_access_plan(side,p,e['outer'])
    usb_collision=shapes['mx_upper'].intersect(gen.prism(usb,4.1,9.3)).Volume()
    report['usb_corridor_intersection_mm3']=usb_collision
    if usb_collision>.001:errors.append('USB cable corridor obstructed')
    ports=gen.service_access_plans(side,p,e['outer'])
    report['explicit_service_access_mm3']={}
    for name,plan in ports.items():
        collision=shapes['mx_upper'].intersect(gen.prism(plan,4.1,9.3)).Volume()
        report['explicit_service_access_mm3'][name]=collision
        if collision>.001:errors.append('Explicit service corridor blocked: '+name)
    service={**p['mounting_service_geometries'],'reset':p['reset_actuator_geometry']}
    report['vertical_service_access_mm3']={}
    for name,plan in service.items():
        v=shapes['mx_upper'].intersect(gen.prism(plan,4.1,9.3)).Volume()
        report['vertical_service_access_mm3'][name]=v
        if v>.001:errors.append('Vertical service access blocked: '+name)
    below=section_plan(shapes['lower'],4.099)
    above=section_plan(shapes['mx_upper'],4.101)
    report['actual_wall_seats']=[]
    for seat in manifest['wall_seats']:
        wall=wkt.loads(seat['wall_wkt'])
        nominal=wall.intersection(ring)
        actual=below.intersection(above).intersection(wall)
        missing=nominal.difference(actual.buffer(.002)).area
        report['actual_wall_seats'].append({'part':seat['part'],'contact_area_mm2':actual.area,
                                           'missing_expected_contact_mm2':missing})
        if actual.area<10 or missing>.01:errors.append('Missing actual perimeter wall seat')
    report['source_sha256'].update(manifest['source_sha256'])
    for path in [Path(__file__),folder/f'{side}-generation.json',
                 *[folder/o['step'] for o in manifest['outputs'].values()]]:
        report['source_sha256'][path.relative_to(gen.ROOT).as_posix()]=gen.digest(path)
    report['status']='pass' if not errors else 'failed'
    report['scope']='Actual STEP validity and section coverage, nominal component/PCB slices, pocket volume/access; native and full interface/reviewer audit separate.'
    gen.write_json(folder/f'{side}-audit.json',report)
    print(json.dumps({'side':side,'errors':errors}),flush=True)
    return bool(errors)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--side',choices=['left','right'],required=True)
    raise SystemExit(audit(parser.parse_args().side))
