"""Independent CON-ARCH-006 / OPS-ARCH-006 post-service-fix actual-solid review.

Review output is deliberately separate from the generation and main audit.
It does not qualify native archives or exact purchased parts.
"""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import cadquery as cq
import trimesh
from shapely.geometry import Point
from tools import generate_kc2_enclosed_housings as gen

plans,enclosures,transform=gen.design_plans()
report={'requirements':['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],'errors':[], 'findings':[], 'sides':{},'source_sha256':{},
        'scope':'Independent imported STEP full-volume USB corridor, POWER travel vertical and outward4mm nail corridor, RESET diameter3 probe and screw-driver approach; actual STL topology/dimensions. Other component and seat/backing tests are separate main-audit evidence.',
        'physical_status':'Pending actual header/cable/keycap, print/strength, probe handling and polarity/pull; no physical or order qualification.'}
for side,p in plans.items():
    manifest=json.loads((gen.STAGING/f'{side}-generation.json').read_text())
    report['source_sha256'][(gen.STAGING/f'{side}-generation.json').relative_to(root).as_posix()]=gen.digest(gen.STAGING/f'{side}-generation.json')
    assert manifest['status']=='generated_not_independently_verified'
    for path,sha in manifest['source_sha256'].items():
        assert gen.digest(root/path)==sha, 'stale '+path
    row={'meshes':{},'service_intersection_volumes_mm3':{}}
    for file in gen.STAGING.glob(f'kc2_{side}_*.stl'):
        mesh=trimesh.load_mesh(file)
        row['meshes'][file.name]={'watertight':bool(mesh.is_watertight),'bodies':int(mesh.body_count),
            'within_150_mm':bool(max(mesh.extents)<=150),'bounds':mesh.bounds.tolist()}
        if not mesh.is_watertight or mesh.body_count!=1 or max(mesh.extents)>150:
            report['errors'].append(file.name+' mesh')
        report['source_sha256'][file.relative_to(root).as_posix()]=gen.digest(file)
    file=gen.STAGING/f'kc2_{side}_mx_upper_housing.step'
    assert gen.digest(file)==manifest['outputs'][side+'_mx_upper']['step_sha256']
    print(side,'import actual STEP',flush=True)
    upper=cq.importers.importStep(str(file)).val()
    report['source_sha256'][file.relative_to(root).as_posix()]=gen.digest(file)
    x0,y0,x1,y1=p['feature_geometries']['controller_socket'].bounds
    cx=(x0+x1)/2; cy=(y0+y1)/2
    from shapely.geometry import box
    end=enclosures[side]['outer'].bounds[2]+1 if side=='left' else enclosures[side]['outer'].bounds[0]-1
    corridor=box(min(cx,end)+.001,cy-5.099,max(cx,end)-.001,cy+5.099)
    pc=p['mounting_service_geometries']['power_switch_actuator_sweep'].centroid
    power_corridor=box(min(pc.x,end)+.001,pc.y-1.999,max(pc.x,end)-.001,pc.y+1.999)
    tests={'usb_10_198mm_corridor_nominal_cable_max_9_6mm':(corridor,4.101,9.301),
           'power_outward_3_998mm_nail_corridor':(power_corridor,4.101,9.301),
           'power_full_sweep_vertical':(p['mounting_service_geometries']['power_switch_actuator_sweep'],4.101,15),
           'reset_3mm_vertical_probe':(Point(p['reset_actuator_geometry'].centroid.coords[0]).buffer(1.5,quad_segs=32),4.101,15)}
    for h in p['mounting_holes']:
        tests['driver_'+h['ref']]=(Point(*h['housing_center_mm']).buffer(1.5,quad_segs=32),7.801,15)
    for name,(plan,z0,z1) in tests.items():
        volume=upper.intersect(gen.prism(plan,z0,z1)).Volume()
        row['service_intersection_volumes_mm3'][name]=volume
        print(side,name,volume,flush=True)
        if volume>.001:report['errors'].append(side+' '+name+' blocked')
    report['sides'][side]=row
report['source_sha256'][Path(__file__).relative_to(root).as_posix()]=gen.digest(__file__)
report['findings']=[{'status':'resolved_by_cad_revision','issue':'Initial USB approach blocked; final10.2mm clear corridor retains receiver collars. Conditional nominal cable width maximum9.6mm; supplied cable unqualified.'}] if not report['errors'] else [{'status':'open','issue':error} for error in report['errors']]
report['status']='pass' if not report['errors'] else 'failed'
out=root/'docs/reports/enclosed-housing-20260909/independent-review-final.json'
out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps({'errors':report['errors'],'report':str(out)}),flush=True)
