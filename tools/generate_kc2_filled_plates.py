"""CON-ARCH-006 complete filled plate fields; staged only until actual review."""
from pathlib import Path
import argparse
from dataclasses import asdict
import hashlib,json
from shapely import affinity
from shapely.geometry import box,Point
from shapely.ops import unary_union
from tools.kc2_filled_plate_profiles import PROFILES,plate_layers
from tools import generate_kc2_mx_upper_housings as upper
from tools.kc2_local_upper_covers import extended_split_masks
from tools.review_kc2_local_upper_covers import approach_geometries

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/solid-filled-plates'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_plan(side,plan,kind):
    profile=PROFILES[kind]
    shp=upper.lower.legacy_geometry.require_shapely()
    previous=upper.upper_plan(shp,plan,upper.stack_parameters(plate_top_above_pcb_mm=5.2,clip_thickness_mm=1.5,aperture_mm=14))
    original_parts=[previous['plate']] if side=='left' else upper.split_upper_plan(shp,plan,previous)[0]
    masks=[plan['housing_outline'].buffer(5)] if side=='left' else extended_split_masks(plan,previous)
    original_union=unary_union(original_parts)
    # Full interior fill reaches captive keys that perimeter-only covers never
    # touched. Do not fill the old key's receiver gap from the opposite mask.
    masks=[mask.difference(original_union).difference(unary_union([other for j,other in enumerate(original_parts) if j!=i]).buffer(.2)).union(part)
           for i,(mask,part) in enumerate(zip(masks,original_parts))]
    clearance=.301 if kind=='mx' else .3
    raw_size=profile.body_clear_width-2*clearance
    bodies=[];apertures=[]
    for switch in plan['switches']:
        x,y=switch['center'];half=raw_size/2;hole=profile.aperture/2
        bodies.append(affinity.rotate(box(x-half,y-half,x+half,y+half).buffer(clearance,quad_segs=32),switch['angle_deg'],origin=(x,y)))
        apertures.append(affinity.rotate(box(x-hole,y-hole,x+hole,y+hole),switch['angle_deg'],origin=(x,y)))
    body=unary_union(bodies);openings=unary_union(apertures)
    domain=plan['housing_outline'].union(body.buffer(1.201,quad_segs=32))
    centers=[Point(*h['housing_center_mm']) for h in plan['mounting_holes']]
    bores=unary_union([p.buffer(.8,quad_segs=64) for p in centers])
    pockets=unary_union([p.buffer(1.7,quad_segs=64) for p in centers])
    bosses=unary_union([p.buffer(2.3,quad_segs=64) for p in centers])
    lands=unary_union([p.buffer(1.5,quad_segs=64) for p in centers])
    approaches=approach_geometries(side,plan,plan['housing_outline'])
    # Preserve explicit outward USB/control/probe access rather than making a
    # dense block that traps the controller. Driver space is the head pocket.
    service=previous['service'].union(unary_union([g for name,(g,z0,z1) in approaches.items() if not name.startswith('driver_')]))
    parts=[plate_layers(profile,domain,body,openings,service,bores,pockets,bosses,lands,mask) for mask in masks]
    return dict(kind=kind,side=side,profile=profile,domain=domain,body=body,openings=openings,service=service,
                bores=bores,pockets=pockets,bosses=bosses,lands=lands,masks=masks,parts=parts,
                mounting_centers=[h['housing_center_mm'] for h in plan['mounting_holes']],
                switch_count=len(plan['switches']))


def generate(side,kind):
    import cadquery as cq
    from tools import generate_kc2_magnetic_housings as magnetic
    from tools.kc2_solid_plate import build_solid
    source_names=['generate_kc2_filled_plates.py','kc2_filled_plate_profiles.py','kc2_solid_plate.py',
        'test_kc2_solid_plate.py','test_kc2_filled_plate_profiles.py','test_kc2_filled_plate_plan.py',
        'generate_kc2_magnetic_housings.py','generate_kc2_mx_upper_housings.py',
        'generate_kc2_x3_v2_housings.py','generate_kc2_housings.py','render_kc2_x3_joined.py',
        'kc2_local_upper_covers.py','review_kc2_local_upper_covers.py','review_kc2_local_covers.py']
    paths=[ROOT/'tools'/name for name in source_names]
    paths.extend(ROOT/f'hardware/PCB/kc2_{s}/kc2_{s}.kicad_pcb' for s in ['left','right'])
    before={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    plans,_,transform=magnetic.load_plans()
    p=build_plan(side,plans[side],kind)
    STAGE.mkdir(parents=True,exist_ok=True)
    name=f'kc2_{side}_{kind}_upper_housing'
    report=dict(requirements=['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],status='generating',
        side=side,kind=kind,profile=asdict(p['profile']),physical_qualified=False,
        source_sha256=before,transform=transform,switch_count=p['switch_count'],
        mounting_centers=p['mounting_centers'],parts=[],outputs={})
    report['plan_wkt']={key:p[key].wkt for key in ['domain','body','openings','service','bores','pockets','bosses','lands']}
    report['masks_wkt']=[mask.wkt for mask in p['masks']]
    solids=[]
    for index,rows in enumerate(p['parts']):
        print(side,kind,'build solid',index,flush=True)
        solid=build_solid(rows)
        if max(solid.BoundingBox().xlen,solid.BoundingBox().ylen,solid.BoundingBox().zlen)>150.001:
            raise ValueError('Exceeds printer envelope')
        suffix='' if side=='left' else '_part_'+chr(97+index)
        stl=STAGE/(name+suffix+'.stl')
        cq.exporters.export(solid,str(stl),tolerance=.005,angularTolerance=.08)
        mesh=magnetic.inspect_mesh(stl,solid)
        report['parts'].append(dict(index=index,bounds_mm=magnetic.bounds(solid),volume_mm3=solid.Volume(),
            section_volume_mm3=sum(r.geometry.area*(r.z1-r.z0) for r in rows),
            layers=[dict(z0=r.z0,z1=r.z1,wkt=r.geometry.wkt) for r in rows],stl=stl.name,mesh=mesh))
        solids.append(solid)
    step=STAGE/(name+'.step')
    cq.exporters.export(cq.Compound.makeCompound(solids),str(step))
    upper.lower.normalize_exported_text(step)
    imported=cq.importers.importStep(str(step)).solids().vals()
    if len(imported)!=len(solids) or not all(s.isValid() for s in imported):
        raise ValueError('Invalid STEP round trip')
    if abs(sum(s.Volume() for s in imported)-sum(s.Volume() for s in solids))>max(.01,sum(s.Volume() for s in solids)*1e-6):
        raise ValueError('STEP volume round trip failed')
    report['outputs']={step.name:digest(step),**{row['stl']:digest(STAGE/row['stl']) for row in report['parts']}}
    if before!={path.relative_to(ROOT).as_posix():digest(path) for path in paths}:
        raise ValueError('Generation sources changed')
    report['status']='generated_pending_independent_review'
    (STAGE/f'{side}-{kind}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(side=side,kind=kind,status=report['status'],parts=len(solids))),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side',required=True,choices=['left','right'])
    parser.add_argument('--kind',required=True,choices=list(PROFILES))
    args=parser.parse_args();generate(args.side,args.kind)
