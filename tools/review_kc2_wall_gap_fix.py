"""CON-ARCH-006 independent actual STL gap, native identity and motion review."""
import json
import numpy as np
import trimesh
from shapely import wkt
from shapely.geometry import box
from shapely.ops import unary_union
from tools.kc2_wall_gap_fix import ROOT,STAGE,write,bridge_slots
from tools.kc2_pcb_seating import digest,horizontal_section
from tools.review_kc2_wrap_motion import layers,sweep_overlap,project_mesh,sweep_right,validate_height_band
from tools.review_kc2_wrap_housings import world
from tools.kc2_stl_clearance import assess

def review():
    plan=json.loads((STAGE/'plan.json').read_text());errors=[];rows={};bands={};projections={};ab=[]
    clearance=json.loads((STAGE/'clearance-native.json').read_text())
    if clearance['status']!='pass' or clearance['errors'] or len(clearance['rows'])!=5:
        raise ValueError('Exact native A/B clearance evidence incomplete')
    bindings=dict(plan['source_sha256'])
    bindings.update(clearance['source_sha256'])
    bindings[(STAGE/'clearance-native.json').relative_to(ROOT).as_posix()]=digest(STAGE/'clearance-native.json')
    initial=STAGE/'review-initial.json'
    if initial.exists():bindings[initial.relative_to(ROOT).as_posix()]=digest(initial)
    bindings[(STAGE/'plan.json').relative_to(ROOT).as_posix()]=digest(STAGE/'plan.json')
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed source '+name)
    for label,job in plan['jobs'].items():
        folder=STAGE/label.replace(':','-')
        gen=json.loads((folder/'generation.json').read_text());native=json.loads((folder/'native.json').read_text())
        if gen['plan_sha256']!=digest(STAGE/'plan.json') or native['plan_sha256']!=digest(STAGE/'plan.json'):
            raise ValueError('Stale generation/native plan '+label)
        for name,sha in gen['source_sha256'].items():
            if digest(ROOT/name)!=sha:raise ValueError('Changed generation source '+name)
            bindings[name]=sha
        if native['status']!='pass' or native['errors'] or gen['step_sha256']!=native['source_step_sha256']:
            raise ValueError('Native export not verified '+label)
        for name,sha in native['outputs'].items():
            if digest(folder/name)!=sha:raise ValueError('Changed output '+name)
            bindings[(folder/name).relative_to(ROOT).as_posix()]=sha
        for name in ('generation.json','native.json',job['stem']+'.step'):
            bindings[(folder/name).relative_to(ROOT).as_posix()]=digest(folder/name)
        parts=[];meshes=[];shadows=[]
        for i,name in enumerate(job['stl_names']):
            mesh=trimesh.load_mesh(folder/name)
            baseline=trimesh.load_mesh(ROOT/'hardware/MODELS'/name)
            if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split())!=1 or mesh.volume<=0 or max(mesh.extents)>150:
                errors.append(name+': mesh or 150 mm envelope failed')
            expected=native['after'][i]
            bound_error=float(np.max(np.abs(mesh.bounds-np.array(expected['bounds_mm']))))
            vol_error=abs(float(mesh.volume)-expected['volume_mm3'])/expected['volume_mm3']
            if bound_error>.02 or vol_error>.001:errors.append(name+': native mesh units/geometry differs')
            preservation=gen['parts'][i]
            if preservation['errors'] or preservation['missing_patch_mm3']>.002:
                errors.append(name+': CAD preservation failed')
            part=gen.get('effective_parts',job['parts'])[i];protected=wkt.loads(part['protected_wkt']);allowed=wkt.loads(part['allowed_wkt'])
            sections=[]
            for patch in part['patches']:
                required=wkt.loads(patch['wkt'])
                for z in (patch['z0']+.01,(patch['z0']+patch['z1'])/2,patch['z1']-.01):
                    new=horizontal_section(mesh,z);old=horizontal_section(baseline,z)
                    # Float32 tessellation allowance at existing boundaries.
                    added=new.difference(old.buffer(.0001))
                    missing=required.difference(new.buffer(.0001)).area
                    obstruction=added.intersection(protected.buffer(-.0001)).area
                    off_plan=added.difference(allowed.buffer(.0001)).area
                    if missing>.005 or obstruction>.005 or off_plan>.005:
                        errors.append(name+': slit closure/protected region failed at '+str(z))
                    sections.append(dict(z_mm=z,missing_required_mm2=missing,
                                         obstructed_protected_mm2=obstruction,off_plan_mm2=off_plan))
            parts.append(dict(file=name,watertight=bool(mesh.is_watertight),native_bounds_error_mm=bound_error,
                native_volume_relative_error=vol_error,sections=sections,preservation=preservation))
            meshes.append(mesh);shadows.append(project_mesh(mesh))
        merged=trimesh.util.concatenate(meshes)
        validate_height_band(merged,job['kind'] in ('normal','magnetic'))
        bands[label]=layers(merged);projections[label]=unary_union(shadows)
        if len(shadows)==2:
            gap=shadows[0].distance(shadows[1]);overlap=shadows[0].intersection(shadows[1]).area
            exact=clearance['rows'][label]
            points=np.array(exact['points_mm'])
            if (abs(points[0,2]-points[1,2])>1e-7 or
                abs(float(np.linalg.norm(points[0,:2]-points[1,:2]))-exact['minimum_distance_mm'])>1e-7):
                errors.append(label+': native closest-distance witness is not lateral')
            rounding=assess(gap,exact['minimum_distance_mm'],float(np.max(np.abs(merged.vertices[:,:2]))))
            ab.append(dict(label=label,gap_mm=gap,overlap_mm2=overlap,native=exact,rounding=rounding))
            if not rounding['pass'] or overlap>.005:errors.append(label+': A/B clearance failed')
        rows[label]=dict(parts=parts)
        print('mesh and sections',label,'errors',len(errors),flush=True)
    assembly=[]
    for side in ('left','right'):
        for low in ('normal','magnetic'):
            for upper in ('mx','choc_v1','deep_sea'):
                checks=sweep_overlap(bands[side+':'+low],bands[side+':'+upper],1.5)
                maximum=max((v['overlap_mm2'] for v in checks),default=0)
                assembly.append(dict(side=side,lower=low,upper=upper,maximum_swept_overlap_mm2=maximum))
                if maximum>.005:errors.append(f'{side}:{low}:{upper}: insertion collision')
    joined=[]
    for low in ('normal','magnetic'):
        for upper in ('mx','choc_v1','deep_sea'):
            left=world(projections['left:'+low].union(projections['left:'+upper]),'left')
            right=world(projections['right:'+low].union(projections['right:'+upper]),'right')
            travel=max(1.,left.bounds[2]-right.bounds[0]+1.)
            overlap=left.intersection(sweep_right(right,travel)).area
            joined.append(dict(lower=low,upper=upper,swept_overlap_mm2=overlap))
            if overlap>.005:errors.append(low+':'+upper+': horizontal join collision')
    for name in ('tools/review_kc2_wall_gap_fix.py','tools/kc2_wall_gap_fix.py','tools/test_kc2_wall_gap_fix.py',
                 'tools/fusion/KC2WallGapFix.py','tools/review_kc2_wrap_motion.py','tools/kc2_pcb_seating.py',
                 'tools/review_kc2_wrap_housings.py','tools/stage_kc2_registered_lower.py',
                 'tools/kc2_central_flexure.py','tools/kc2_step_whitespace.py',
                 'tools/test_review_kc2_wrap_motion.py','tools/test_kc2_step_whitespace.py',
                 'tools/test_kc2_stl_tjunction.py','tools/kc2_stl_tjunction.py',
                 'tools/kc2_stl_clearance.py','tools/test_kc2_stl_clearance.py'):
        bindings[name]=digest(ROOT/name)
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Review input changed '+name)
    result=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='pass' if not errors else 'failed',
        rows=rows,assembly=assembly,joined=joined,ab=ab,errors=errors,source_sha256=bindings,physical_qualified=False,
        scope='Source-bound additive CAD proofs, Fusion archive reopen and STL, actual slit sections and protected regions, continuous prismatic upper insertion and projected A/B/central approach')
    write(STAGE/'review.json',result)
    print(result['status'],errors,flush=True)
    return result

if __name__=='__main__':raise SystemExit(review()['status']!='pass')
