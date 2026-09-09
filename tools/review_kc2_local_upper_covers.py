"""CON-ARCH-006 independent imported-STEP local upper audit, no CAD writes."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import cadquery as cq
import trimesh
from shapely import wkt
from shapely.geometry import box,Point
from shapely.ops import unary_union
from tools.review_kc2_local_covers import prism

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/local-cover-build'
BASELINE='cc854a3e0e0f25ab3d63e2916cb4b99a487b6536'
TOL=.002

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def outside_volume(added,allowed):
    # Separate Boolean tools avoid OCP compound residuals at touching
    # skirt/roof interfaces. No enlargement or tolerance waiver is applied.
    return added.cut(*allowed.Solids()).Volume()

def coverage_areas(required,declared,old_gap):
    missing=required.difference(unary_union(declared))
    # Existing plate split remains empty exactly; new outside split has only
    # a narrow allowance shared by both actual cover-part boundaries.
    seam=unary_union([a.buffer(.201).intersection(b.buffer(.201)) for i,a in enumerate(declared) for b in declared[i+1:]])
    return dict(missing_mm2=missing.area,retained_old_gap_mm2=missing.intersection(old_gap).area,
                unexplained_mm2=missing.difference(seam.union(old_gap)).area)

def split_clearance_records(originals,current,added):
    if len(current)!=2:return {'errors':[],'scope':'Unsplit left upper'}
    row={'original_parts_mm':originals[0].distance(originals[1]),
         'revised_parts_mm':current[0].distance(current[1]),
         'added_a_to_old_b_mm':added[0].distance(originals[1]),
         'added_b_to_old_a_mm':added[1].distance(originals[0]),
         'added_pair_mm':added[0].distance(added[1])}
    original=row['original_parts_mm']
    row['errors']=[name+' worsens measured original split clearance' for name,value in row.items()
                   if not math.isfinite(value) or value<=0 or value<original-1e-7]
    row['nominal_clearance_mm']=.2
    row['no_worsening_tolerance_mm']=1e-7
    return row

def approach_geometries(side,plan,outline):
    controller=plan['feature_geometries']['controller_socket'].centroid
    power=plan['mounting_service_geometries']['power_switch_actuator_sweep']
    pc=power.centroid
    end=outline.bounds[2]+2 if side=='left' else outline.bounds[0]-2
    result={'usb_nominal_9_6mm_cable':[box(min(controller.x,end),controller.y-5.1,max(controller.x,end),controller.y+5.1),4.1,9.301],
            'power_4mm_outward_nail':[box(min(pc.x,end),pc.y-2,max(pc.x,end),pc.y+2),4.1,9.301],
            'power_full_sweep_vertical':[power,4.1,15.],
            'reset_3mm_probe':[plan['reset_actuator_geometry'].centroid.buffer(1.5,quad_segs=32),4.1,15.]}
    for hole in plan['mounting_holes']:
        result['driver_'+hole['ref']]=[Point(*hole['housing_center_mm']).buffer(1.5,quad_segs=32),7.801,15.]
    return result

def delta_errors(before,after,allowed,protected=None):
    removed=before.cut(after).Volume()
    added=after.cut(before)
    missing=allowed.cut(after).Volume()
    outside=outside_volume(added,allowed) if added.Volume()>1e-8 else 0.
    collision=added.intersect(protected).Volume() if protected is not None and added.Volume()>1e-8 else 0.
    errors=[]
    if removed>TOL:errors.append('Original plate/support material removed')
    if missing>TOL:errors.append('Required local cover missing')
    if outside>TOL:errors.append('Material added outside local allowance')
    if collision>TOL:errors.append('Added material obstructs component/service clearance')
    if not after.isValid() or len(after.Solids())!=len(before.Solids()):errors.append('Invalid/disconnected upper solid')
    b=after.BoundingBox()
    if b.zmax>9.30001 or max(b.xlen,b.ylen,b.zlen)>150.001:errors.append('Upper height/print envelope changed')
    return dict(errors=errors,removed_mm3=removed,added_mm3=added.Volume(),missing_mm3=missing,
                outside_local_allowance_mm3=outside,component_service_collision_mm3=collision)

def audit(side):
    from tools import generate_kc2_magnetic_housings as m
    from tools import generate_kc2_mx_upper_housings as u
    path=STAGE/f'{side}-upper.json'
    record=json.loads(path.read_text(encoding='utf8'))
    if record.get('status')!='generated_not_independently_verified' or record.get('baseline_commit')!=BASELINE:
        raise ValueError('Incomplete or incorrect baseline generation')
    sources=dict(record['source_sha256']);sources[path.relative_to(ROOT).as_posix()]=sha(path)
    for p,h in sources.items():
        if sha(ROOT/p)!=h:raise ValueError('Stale source: '+p)
    for p in [Path(__file__),ROOT/'tools/test_review_kc2_local_upper_covers.py',ROOT/'tools/review_kc2_local_covers.py']:
        sources[p.relative_to(ROOT).as_posix()]=sha(p)
    plans,_,transform=m.load_plans();plan=plans[side]
    if abs(transform['dx']-124.625)>1e-8 or abs(transform['dy'])>1e-8:raise ValueError('Original joined transform changed')
    up=u.upper_plan(u.lower.legacy_geometry.require_shapely(),plan,
        u.stack_parameters(plate_top_above_pcb_mm=5.2,clip_thickness_mm=1.5,aperture_mm=14.))
    old_parts=[up['plate']] if side=='left' else u.split_upper_plan(u.lower.legacy_geometry.require_shapely(),plan,up)[0]
    body=plan['switch_service_body_geometry'];outline=plan['housing_outline']
    service=up['service'].union(up['pilots']).union(up['pockets'])
    locality=body.buffer(2.,quad_segs=32)
    outside=outline.union(body.buffer(.702,quad_segs=32))
    # Independently constructed geometric allowance, not producer cover_plan.
    skirt=outside.difference(outline.buffer(-.401).union(body.buffer(.301,quad_segs=32))).difference(service).intersection(locality)
    roof=outside.difference(outline.buffer(-.005)).intersection(body.buffer(.702,quad_segs=32)).difference(body).difference(service).intersection(locality)
    declared_skirts=[wkt.loads(r['skirt_plan_wkt']) for r in record['checks']]
    declared_roofs=[wkt.loads(r['roof_plan_wkt']) for r in record['checks']]
    errors=[];coverage={}
    for label,declared,allowed in [('skirt',declared_skirts,skirt),('roof',declared_roofs,roof)]:
        combined=unary_union(declared)
        if combined.difference(allowed).area>.001:errors.append(label+' exceeds independent local allowance')
        # Retained right split is the only permitted cover interruption.
        coverage[label]=coverage_areas(allowed,declared,up['plate'].difference(unary_union(old_parts)))
        if coverage[label]['unexplained_mm2']>.001:errors.append(label+' coverage missing outside exact retained/local split seam')
        if any(a.intersection(b).area>.001 for i,a in enumerate(declared) for b in declared[i+1:]):errors.append(label+' split overlap')
    output=record['outputs']['normal'];step=STAGE/output['step']
    if sha(step)!=output['step_sha256']:raise ValueError('Stale STEP')
    sources[step.relative_to(ROOT).as_posix()]=sha(step)
    baseline_path='hardware/MODELS/'+step.name
    data=subprocess.check_output(['git','show',BASELINE+':'+baseline_path],cwd=ROOT)
    git_sha=hashlib.sha256(data).hexdigest()
    if record['git_source_sha256'].get(BASELINE+':'+baseline_path)!=git_sha:raise ValueError('Incorrect baseline STEP hash')
    rows=[];additions=[]
    approaches={name:prism(g,z0,z1) for name,(g,z0,z1) in approach_geometries(side,plan,outline).items()}
    with tempfile.TemporaryDirectory(prefix='kc2-upper-independent-') as temp:
        baseline=Path(temp)/step.name;baseline.write_bytes(data)
        originals=sorted(cq.importers.importStep(str(baseline)).solids().vals(),key=lambda s:s.Center().x)
        current=sorted(cq.importers.importStep(str(step)).solids().vals(),key=lambda s:s.Center().x)
        if len(current)!=(1 if side=='left' else 2) or len(current)!=len(originals):raise ValueError('Incorrect actual part count')
        for i,(before,after) in enumerate(zip(originals,current)):
            print(side,'upper imported STEP part',i,'Boolean review',flush=True)
            allowed=cq.Compound.makeCompound([*prism(declared_skirts[i],4.4,7.8).Solids(),*prism(declared_roofs[i],7.8,9.3).Solids()])
            protected=cq.Compound.makeCompound([*prism(body.buffer(.299),4.4,7.799).Solids(),
                *prism(body,7.801,9.301).Solids(),*prism(service,4.4,9.301).Solids()])
            row=delta_errors(before,after,allowed,protected)
            added=after.cut(before)
            additions.append(added)
            row['new_service_approach_obstruction_mm3']={name:added.intersect(shape).Volume() for name,shape in approaches.items()}
            row['baseline_service_approach_overlap_mm3']={name:before.intersect(shape).Volume() for name,shape in approaches.items()}
            for name,value in row['new_service_approach_obstruction_mm3'].items():
                if value>TOL:row['errors'].append('New service/driver obstruction: '+name)
            # Local covers must float above PCB, never become a new lower wall seat.
            row['added_min_z_mm']=added.BoundingBox().zmin
            if row['added_min_z_mm']<4.39999:row['errors'].append('Cover reaches PCB/lower support datum')
            missing_roof=declared_skirts[i].difference(old_parts[i].union(declared_roofs[i])).area
            row['unsupported_skirt_plan_mm2']=missing_roof
            if missing_roof>.001:row['errors'].append('Skirt has no retained plate/local roof above it')
            name=step.stem+('' if side=='left' else '_part_'+chr(97+i))+'.stl'
            meshpath=STAGE/name;mesh=trimesh.load_mesh(meshpath)
            if sha(meshpath)!=output['meshes'][name]['sha256']:raise ValueError('Stale STL')
            sources[meshpath.relative_to(ROOT).as_posix()]=sha(meshpath)
            bounds=m.bounds(after);bound_error=max(abs(a-b) for a,b in zip(bounds,mesh.bounds.flatten()))
            volume_error=abs(after.Volume()-mesh.volume)
            ok=bool(mesh.is_watertight and mesh.is_winding_consistent and mesh.body_count==1 and max(mesh.extents)<=150.001 and bound_error<.02 and volume_error<max(.01,after.Volume()*.0005))
            row['mesh']={'path':name,'passes':ok,'bounds_error_mm':bound_error,'volume_error_mm3':volume_error}
            if not ok:row['errors'].append('STL topology/STEP equivalence failed')
            errors.extend(row['errors']);rows.append(row)
        split_clearance=split_clearance_records(originals,current,additions)
        errors.extend(split_clearance['errors'])
    for p,h in sources.items():
        if sha(ROOT/p)!=h:raise ValueError('Source changed during actual audit: '+p)
    report=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='failed' if errors else 'pass',errors=errors,
        source_sha256=sources,git_source_sha256={BASELINE+':'+baseline_path:git_sha},physical_qualified=False,
        transform=transform,coverage=coverage,split_clearance=split_clearance,parts=rows,scope='Independent actual STEP additive-only delta, local key-field coverage, original plate/support preservation, body/service clearance, no lower-seat transfer, no worsening of actual nominal-0.2 mm original split distances, STL topology and dimensions. Exact cap/print/strength physical qualification pending.')
    (STAGE/f'{side}-upper-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'side':side,'status':report['status'],'errors':errors}),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--side',required=True,choices=['left','right'])
    raise SystemExit(bool(audit(parser.parse_args().side)['errors']))
