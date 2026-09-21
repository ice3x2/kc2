"""CON-ARCH-006 actual STL and assembly review for finished upper housings."""
import json
import numpy as np
import trimesh
from shapely import wkt
from shapely.geometry import Point
from shapely.ops import unary_union

from tools.kc2_upper_finish import ROOT,STAGE,KINDS,digest,write,enclosed_nonfunctional_voids
from tools.kc2_pcb_seating import horizontal_section
from tools.kc2_stl_clearance import assess
from tools.review_kc2_wrap_motion import layers,sweep_overlap,project_mesh,sweep_right,validate_height_band
from tools.review_kc2_wrap_housings import world

def review():
    plan=json.loads((STAGE/'plan.json').read_text());errors=[];rows={};bands={};projections={};ab=[];bindings=dict(plan['source_sha256'])
    bindings[(STAGE/'plan.json').relative_to(ROOT).as_posix()]=digest(STAGE/'plan.json')
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed source '+name)
    for label,job in plan['jobs'].items():
        folder=STAGE/label.replace(':','-');gen=json.loads((folder/'generation.json').read_text());native=json.loads((folder/'native.json').read_text())
        if gen['plan_sha256']!=digest(STAGE/'plan.json') or native['plan_sha256']!=digest(STAGE/'plan.json') or native['status']!='pass' or native['errors']:
            raise ValueError('Stale/failed native job '+label)
        for name,sha in native['outputs'].items():
            if digest(folder/name)!=sha:raise ValueError('Changed output '+name)
            bindings[(folder/name).relative_to(ROOT).as_posix()]=sha
        for name in ('generation.json','native.json',job['stem']+'.step'):
            bindings[(folder/name).relative_to(ROOT).as_posix()]=digest(folder/name)
        meshes=[];shadows=[];partrows=[]
        for i,name in enumerate(job['stl_names']):
            mesh=trimesh.load_mesh(folder/name,force='mesh');old=trimesh.load_mesh(ROOT/'hardware/MODELS'/name,force='mesh')
            if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split())!=1 or mesh.volume<=0 or max(mesh.extents)>150:
                errors.append(name+': invalid mesh/envelope')
            expected=native['after'][i];bound=float(np.max(np.abs(mesh.bounds-np.array(expected['bounds_mm']))));vol=abs(mesh.volume-expected['volume_mm3'])/expected['volume_mm3']
            if bound>.02 or vol>.001:errors.append(name+': native STL differs')
            envelope_error=max(float(np.max(np.abs(mesh.bounds[:,:2]-old.bounds[:,:2]))),
                               abs(float(mesh.bounds[1,2]-old.bounds[1,2])))
            if envelope_error>.02 or abs(float(mesh.bounds[0,2])-4.4)>.01:
                errors.append(name+': external envelope/print datum changed')
            proof=gen['parts'][i]
            if proof['errors'] or proof['missing_addition_mm3']>.002:errors.append(name+': additive CAD proof failed')
            part=job['parts'][i];protected=wkt.loads(part['protected_wkt']);checks=[]
            for patch in part['patches']:
                required=wkt.loads(patch['required_wkt']);planned=wkt.loads(patch['wkt'])
                for z in (patch['z0']+.01,(patch['z0']+patch['z1'])/2,patch['z1']-.01):
                    new=horizontal_section(mesh,z);before=horizontal_section(old,z);added=new.difference(before.buffer(.0001))
                    row=dict(z_mm=z,missing_mm2=required.difference(new.buffer(.0001)).area,
                        protected_intrusion_mm2=added.intersection(protected.buffer(-.0001)).area,
                        off_plan_mm2=added.difference(planned.buffer(.0001)).area,
                        remaining_nonfunctional_void_mm2=enclosed_nonfunctional_voids(new,protected).area)
                    if max(row[k] for k in row if k!='z_mm')>.005:errors.append(name+': inner void check failed')
                    checks.append(row)
            below=[horizontal_section(mesh,z).area for z in (4.15,4.35,4.399)]
            new_mount=horizontal_section(mesh,4.45);old_mount=horizontal_section(old,4.45);mounts=[]
            for center in part['owned_mounts']:
                witness=Point(*center).buffer(2.4)
                changed=new_mount.intersection(witness).symmetric_difference(old_mount.intersection(witness)).area
                row=dict(center_xy=center,section_change_mm2=changed,
                         new_material_mm2=new_mount.intersection(witness).area)
                if changed>.005 or row['new_material_mm2']<10:
                    errors.append(name+': screw boss/bore changed above datum')
                mounts.append(row)
            clip=proof['clip']
            if (max(below)>.005 or abs(clip['result_min_z_mm']-4.4)>1e-6 or
                    clip['removed_below_datum_mm3']<=.01 or
                    clip['removed_at_or_above_datum_mm3']>.002 or clip['added_material_mm3']>.002):
                errors.append(name+': coplanar print-face check failed')
            partrows.append(dict(file=name,native_bounds_error_mm=bound,native_volume_relative_error=vol,
                inner_void_checks=checks,below_datum_section_area_mm2=below,mounts=mounts,preservation=proof))
            meshes.append(mesh);shadows.append(project_mesh(mesh))
        merged=trimesh.util.concatenate(meshes);validate_height_band(merged,False);bands[label]=layers(merged);projections[label]=unary_union(shadows)
        if len(shadows)==2:
            gap=shadows[0].distance(shadows[1]);overlap=shadows[0].intersection(shadows[1]).area;exact=native['native_ab_clearance'];points=np.array(exact['points_mm'])
            rounding=assess(gap,exact['minimum_distance_mm'],float(np.max(np.abs(merged.vertices[:,:2]))))
            lateral=abs(points[0,2]-points[1,2])<=1e-7 and abs(np.linalg.norm(points[0,:2]-points[1,:2])-exact['minimum_distance_mm'])<=1e-7
            ab.append(dict(label=label,gap_mm=gap,overlap_mm2=overlap,native=exact,rounding=rounding,lateral_witness=bool(lateral)))
            if overlap>.005 or not rounding['pass'] or not lateral:errors.append(label+': A/B clearance failed')
        rows[label]=dict(parts=partrows);print('review',label,'errors',len(errors),flush=True)
    # Lower meshes are unchanged reviewed canonical inputs.
    lower={}
    for side in ('left','right'):
        for kind in ('normal','magnetic'):
            if side=='left':names=[f'kc2_left_lower_housing'+('_magnetic' if kind=='magnetic' else '')+'.stl']
            else:names=[f'kc2_right_lower_housing_part_a'+('_magnetic' if kind=='magnetic' else '')+'.stl',f'kc2_right_lower_housing_part_b'+('_magnetic' if kind=='magnetic' else '')+'.stl']
            ms=[]
            for name in names:
                path=ROOT/'hardware/MODELS'/name;bindings[path.relative_to(ROOT).as_posix()]=digest(path);ms.append(trimesh.load_mesh(path,force='mesh'))
            merged=trimesh.util.concatenate(ms);validate_height_band(merged,True);lower[f'{side}:{kind}']=layers(merged)
    assembly=[]
    for side in ('left','right'):
        for low in ('normal','magnetic'):
            for upper in KINDS:
                checks=sweep_overlap(lower[f'{side}:{low}'],bands[f'{side}:{upper}'],1.5);maximum=max((x['overlap_mm2'] for x in checks),default=0.)
                assembly.append(dict(side=side,lower=low,upper=upper,maximum_swept_overlap_mm2=maximum))
                if maximum>.005:errors.append(f'{side}:{low}:{upper}: insertion collision')
    joined=[]
    for low in ('normal','magnetic'):
        for upper in KINDS:
            # Full lower projections are already part of each upper/lower joined envelope.
            def lower_projection(side):
                names=([f'kc2_left_lower_housing'+('_magnetic' if low=='magnetic' else '')+'.stl'] if side=='left' else
                    [f'kc2_right_lower_housing_part_a'+('_magnetic' if low=='magnetic' else '')+'.stl',f'kc2_right_lower_housing_part_b'+('_magnetic' if low=='magnetic' else '')+'.stl'])
                return unary_union([project_mesh(trimesh.load_mesh(ROOT/'hardware/MODELS'/n,force='mesh')) for n in names])
            left=world(lower_projection('left').union(projections[f'left:{upper}']),'left');right=world(lower_projection('right').union(projections[f'right:{upper}']),'right')
            overlap=left.intersection(sweep_right(right,max(1.,left.bounds[2]-right.bounds[0]+1.))).area
            joined.append(dict(lower=low,upper=upper,swept_overlap_mm2=overlap))
            if overlap>.005:errors.append(low+':'+upper+': joined approach collision')
    for name in ('tools/review_kc2_upper_finish.py','tools/kc2_upper_finish.py','tools/test_kc2_upper_finish.py','tools/fusion/KC2UpperFinish.py',
                 'tools/kc2_pcb_seating.py','tools/kc2_stl_clearance.py','tools/review_kc2_wrap_motion.py','tools/review_kc2_wrap_housings.py'):
        bindings[name]=digest(ROOT/name)
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Review input changed '+name)
    result=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='pass' if not errors else 'failed',rows=rows,ab=ab,
                assembly=assembly,joined=joined,errors=errors,source_sha256=bindings,physical_qualified=False,
                scope='Closed upper voids, no material below common Z4.40 print datum, preserved screw bores/bosses, actual Fusion/STL and assembly motion')
    write(STAGE/'review.json',result);print(result['status'],errors,flush=True);return result

if __name__=='__main__':raise SystemExit(review()['status']!='pass')
