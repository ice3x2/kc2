"""CON-ARCH-006 / OPS-ARCH-006: staged continuous-wall CAD, no PCB writes.

Baseline r5 geometry is read from Git cc854a3, not a duplicate active model.
Staged outputs are NOT publication or fabrication approval. Independent
verification, native round trips and review must precede canonical promotion.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import cadquery as cq
from shapely import affinity
from shapely.geometry import box, LineString, Point
from shapely.ops import unary_union
from tools import generate_kc2_x3_v2_housings as lower
from tools import generate_kc2_mx_upper_housings as upper
from tools import generate_kc2_magnetic_housings as magnet
from tools import kc2_enclosure_plan as planning

ROOT=Path(__file__).resolve().parents[1]
STAGING=ROOT/'.codex-tmp/enclosure-build'
BASELINE='cc854a3e0e0f25ab3d63e2916cb4b99a487b6536'
EXTRA_JOIN_X=4.6
SEAT_Z=4.1


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8')


def prism(plan,z0,z1):
    if plan.is_empty or z1<=z0:raise ValueError('Empty or inverted extrusion')
    return lower._extrude_geometry(cq,plan,z1-z0,z0).val()


def from_git(name):
    path=STAGING/'baseline'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    data=subprocess.run(['git','show',f'{BASELINE}:hardware/MODELS/{name}'],cwd=ROOT,
                        capture_output=True,check=True).stdout
    if not path.exists() or path.read_bytes()!=data:path.write_bytes(data)
    return path


def local_shape(global_geometry,p,dx):
    return affinity.scale(affinity.translate(global_geometry,
            xoff=-p['raw_bounds'][2]-dx,yoff=-p['raw_bounds'][1]),xfact=-1,yfact=1,origin=(0,0))


def design_plans():
    plans,_,old_transform=magnet.load_plans()
    cavities={}
    for side,p in plans.items():
        components=unary_union([*p['component_geometries'].values(),p['switch_service_body_geometry'],
                 *p['mounting_service_geometries'].values(),
                 p['feature_geometries']['controller_socket'].convex_hull,p['reset_actuator_geometry']])
        cavities[side]=planning.wall_plan(p['board'],components,.4)
    dx=old_transform['dx']+EXTRA_JOIN_X
    left_global=planning.global_shape(cavities['left']['inner'],plans['left'])
    right_global=planning.global_shape(cavities['right']['inner'],plans['right'],dx)
    lo,ro=planning.allocate_outer_walls(left_global,right_global)
    outlines={'left':local_shape(lo,plans['left'],0),'right':local_shape(ro,plans['right'],dx)}
    enclosure={s:{'outer':outlines[s],'inner':cavities[s]['inner'],
                  'wall':outlines[s].difference(cavities[s]['inner'])} for s in plans}
    return plans,enclosure,{'right_dx_mm':dx,'right_dy_mm':0.,'extra_x_mm':EXTRA_JOIN_X,
            'nominal_cross_half_keycap_gap_mm':1.8+EXTRA_JOIN_X,
            'case_clearance':planning.join_review(lo,ro)}


def lower_masks(side,p,outer):
    if side=='left':return [outer]
    split=lower.build_right_split_plan(lower.legacy_geometry.require_shapely(),p)
    x=split['split_x_mm']
    return [outer.intersection(box(-20,-20,x-.1,200).union(split['key_union'])),
            outer.intersection(box(x+.1,-20,220,200).difference(split['slot_union']))]


def usb_access_plan(side,p,outer):
    """Top-open 10.2 mm cable corridor; exact cable/header remains a fit gate.

    A 9.6 mm nominal cable envelope plus 0.3 mm on each side is a design
    allowance, not a claim about the user's unspecified cable. Do not cut
    the lower component-concealment wall below the PCB top at Z4.1.
    """
    x0,y0,x1,y1=p['feature_geometries']['controller_socket'].bounds
    cx=(x0+x1)/2;cy=(y0+y1)/2
    end=outer.bounds[2]+1 if side=='left' else outer.bounds[0]-1
    return box(min(cx,end),cy-5.1,max(cx,end),cy+5.1)


def service_access_plans(side,p,outer):
    """CON-ARCH-007 AC-8: upper-only outward nail and vertical probe access."""
    sweep=p['mounting_service_geometries']['power_switch_actuator_sweep']
    cx,cy=sweep.centroid.coords[0]
    end=outer.bounds[2]+1 if side=='left' else outer.bounds[0]-1
    return {'usb':usb_access_plan(side,p,outer),
            'power':box(min(cx,end),cy-2,max(cx,end),cy+2),
            'reset':Point(p['reset_actuator_geometry'].centroid.coords[0]).buffer(1.8,quad_segs=64)}


def pocket_plans(side,p,enclosure):
    sign=1 if side=='left' else -1
    pockets=[];bridges=[]
    forbidden=p['all_component_cutouts'].union(p['mounting_land_geometry']).union(
        lower._support_plan_union(lower.legacy_geometry.require_shapely(),p['support_posts']))
    for y in [103.,111.]:
        line=LineString([(-20,y),(220,y)])
        section=enclosure['outer'].intersection(line)
        old_section=p['housing_outline'].intersection(line)
        x=section.bounds[0 if side=='left' else 2]
        old_x=old_section.bounds[0 if side=='left' else 2]
        end=x+sign*1.8
        reserve=box(min(x+sign*.005,end),y-1.25,max(x+sign*.005,end),y+1.25)
        if reserve.intersects(forbidden):raise RuntimeError(side+': magnet pocket hits protected feature')
        bridge=box(min(x,old_x+sign*1.8),y-1.75,max(x,old_x+sign*1.8),y+1.75)
        bridge=bridge.intersection(enclosure['outer']).difference(p['housing_outline'].buffer(-.02))
        if bridge.intersects(p['all_component_cutouts']):raise RuntimeError(side+': pocket bridge hits component')
        bridges.append(bridge)
        pockets.append({'x':x,'y':y,'sign':sign,'z':.75,'diameter_mm':2.4,'depth_mm':1.2})
    return pockets,unary_union(bridges)


def export_set(side,kind,solids,record,magnetic=False):
    suffix='_magnetic' if magnetic else ''
    label=f'{side}_{kind}{suffix}'
    result={'solids':[],'meshes':{}}
    for i,solid in enumerate(solids):
        if not solid.isValid() or len(solid.Solids())!=1:
            raise RuntimeError(label+': disconnected or invalid printable part')
        part='' if side=='left' else f'_part_{chr(97+i)}'
        name=f'kc2_{side}_{kind}_housing{part}{suffix}.stl'
        path=STAGING/name
        cq.exporters.export(solid,str(path),tolerance=.005,angularTolerance=.08)
        result['meshes'][name]=magnet.inspect_mesh(path,solid)
        result['solids'].append({'bounds_mm':magnet.bounds(solid),'volume_mm3':solid.Volume()})
    name=f'kc2_{side}_{kind}_housing{suffix}.step'
    path=STAGING/name
    cq.exporters.export(cq.Compound.makeCompound(solids),str(path))
    lower.normalize_exported_text(path)
    reopened=cq.importers.importStep(str(path)).val()
    if len(reopened.Solids())!=len(solids) or not reopened.isValid():raise RuntimeError(label+': STEP roundtrip')
    if abs(reopened.Volume()-sum(s.Volume() for s in solids))>.002:raise RuntimeError(label+': STEP volume changed')
    result.update(step=name,step_sha256=digest(path),step_reimport_valid=True)
    record['outputs'][label]=result
    write_json(STAGING/f'{side}-generation.json',record)


def generate_side(side,p,enclosure,transform):
    print(side+': build enclosed lower',flush=True)
    baseline=from_git(f'kc2_{side}_lower_housing.step')
    originals=sorted(cq.importers.importStep(str(baseline)).val().Solids(),key=lambda s:s.Center().x)
    masks=lower_masks(side,p,enclosure['outer'])
    pockets,bridges=pocket_plans(side,p,enclosure)
    record={'requirements':['CON-ARCH-006','OPS-ARCH-006'],'baseline_commit':BASELINE,
            'side':side,'status':'incomplete','physical_qualified':False,'outputs':{},
            'wall_nominal_mm':.8,'minimum_wall_mm':.4,'seat_z_mm':SEAT_Z,'transform':transform,
            'pockets':pockets,'source_sha256':{},'geometry':{
                k:v.wkt for k,v in enclosure.items()},'lower_masks_wkt':[m.wkt for m in masks],
            'bridge_wkt':bridges.wkt,'primary_support_count':len(p['support_posts']),
            'mounting_count':len(p['mounting_holes'])}
    normal=[];magnetic=[];additional=[]
    for i,(original,mask) in enumerate(zip(originals,masks)):
        floor_extension=enclosure['outer'].difference(p['housing_outline'].buffer(-.02)).intersection(mask)
        wall=enclosure['wall'].intersection(mask)
        additions=[prism(floor_extension,-2.2,-1),prism(wall,-1,SEAT_Z)]
        local_bridges=bridges.intersection(mask)
        if not local_bridges.is_empty:additions.append(prism(local_bridges,-1,2.5))
        extra=cq.Compound.makeCompound(additions)
        print(f'{side} lower {i}: fuse floor, sidewall and pocket bridge',flush=True)
        solid=original.fuse(*additions)
        normal.append(solid);additional.append(extra)
        cutters=[magnet.pocket_cutter(q['x'],q['y'],q['sign']) for q in pockets
                 if mask.buffer(1e-6).covers(planning.Polygon([(q['x'],q['y']),
                   (q['x']+q['sign']*.01,q['y']),(q['x'],q['y']+.01)]))]
        magnetic.append(solid.cut(*cutters) if cutters else solid)
    export_set(side,'lower',normal,record)
    export_set(side,'lower',magnetic,record,True)
    print(side+': build enclosed upper',flush=True)
    stack=upper.stack_parameters(plate_top_above_pcb_mm=5.2,clip_thickness_mm=1.5,aperture_mm=14.)
    shp=lower.legacy_geometry.require_shapely()
    expanded=dict(p,housing_outline=enclosure['outer'])
    up=upper.upper_plan(shp,expanded,stack)
    ports=service_access_plans(side,p,enclosure['outer'])
    usb=ports['usb'];access=unary_union(list(ports.values()))
    if access.intersection(up['lands'].union(up['collars'])).area>1e-7:
        raise RuntimeError(side+': service approach intersects mounting receiver')
    up['plate']=up['plate'].difference(access)
    if up['plate'].geom_type!='Polygon':raise RuntimeError(side+': service notch disconnects plate')
    record['usb_access']={'plan_wkt':usb.wkt,'z_min_mm':4.1,'z_max_mm':9.3,
                          'clear_width_mm':10.2,'nominal_cable_width_allowance_mm':9.6,
                          'exact_cable_and_header_qualified':False}
    record['service_access']={'plans_wkt':{k:v.wkt for k,v in ports.items()},
        'power_nail_corridor_width_mm':4.,'reset_hole_diameter_mm':3.6,
        'reset_nominal_probe_diameter_mm':3.,'z_min_mm':4.1,'z_max_mm':9.3}
    part_plans,joint=([up['plate']],None) if side=='left' else upper.split_upper_plan(shp,expanded,up)
    tops=[];wall_seats=[]
    for i,part in enumerate(part_plans):
        print(f'{side} upper {i}: fuse plate, receivers and sidewall',flush=True)
        plate=prism(part,7.8,9.3)
        stops=prism(up['lands'].intersection(part),4.1,7.8)
        collars=prism(up['collars'].intersection(part),5.3,7.8)
        wall_plan=enclosure['wall'].intersection(part).difference(access)
        wall=prism(wall_plan,4.1,7.8)
        top=plate.fuse(stops,collars,wall).cut(prism(up['pockets'].intersection(part),7.8,9.4))
        tops.append(top)
        seat=wall_plan.intersection(unary_union([enclosure['wall'].intersection(m) for m in masks]))
        if seat.area<10:raise RuntimeError(side+': insufficient direct perimeter seat')
        wall_seats.append({'part':i,'wall_footprint_area_mm2':wall_plan.area,'seated_area_mm2':seat.area,
                           'nominal_plane_mm':4.1,'wall_wkt':wall_plan.wkt})
    record['wall_seats']=wall_seats;record['upper_part_plans_wkt']=[p.wkt for p in part_plans]
    record['upper_split_joint']=joint
    export_set(side,'mx_upper',tops,record)
    for path in [Path(__file__),Path(planning.__file__),Path(lower.__file__),Path(upper.__file__),
                 Path(magnet.__file__),lower.BOARD_PATHS[side]]:
        record['source_sha256'][path.relative_to(ROOT).as_posix()]=digest(path)
    record['baseline_step_sha256']=digest(baseline)
    record['status']='generated_not_independently_verified'
    write_json(STAGING/f'{side}-generation.json',record)
    print(side+': staged CAD generated; independent audit/native/review still required',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side',choices=['left','right','all'],default='all')
    args=parser.parse_args()
    STAGING.mkdir(parents=True,exist_ok=True)
    plans,enclosures,transform=design_plans()
    print('Joined enclosure: '+json.dumps(transform),flush=True)
    write_json(STAGING/'joined-plan.json',transform)
    for side in ['left','right']:
        if args.side in ['all',side]:generate_side(side,plans[side],enclosures[side],transform)


if __name__=='__main__':main()
