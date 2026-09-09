"""Independent CON-ARCH-006 local LOWER cover audit; no hardware writes.

The baseline is Git cc854a3, not the rejected global enclosure. Actual STEP
Boolean differences prove preservation and limit additions to local windows.
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import cadquery as cq
import trimesh
from shapely import wkt
from shapely.geometry import box
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/local-cover-build'
BASELINE='cc854a3e0e0f25ab3d63e2916cb4b99a487b6536'
VOLUME_TOLERANCE=.002

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def changed_bindings(root,bindings):
    return sorted(source for source,sha in bindings.items()
                  if not (root/source).is_file() or digest(root/source)!=sha)

def cut_union(shape,tools):
    """Subtract all tool solids as a union, not an adjacent OCC compound.

    Local wall and floor touch. OCC may misclassify a multi-solid compound
    operand; explicit individual tools and subjects retain set semantics.
    """
    cutters=tools.Solids()
    if not cutters:return shape
    pieces=[piece.cut(*cutters) for piece in shape.Solids()]
    return cq.Compound.makeCompound([solid for piece in pieces for solid in piece.Solids()])

def prism(plan,z0,z1):
    solids=[]
    for polygon in getattr(plan,'geoms',[plan]):
        if polygon.is_empty:continue
        wp=cq.Workplane('XY').workplane(offset=z0)
        for ring in [polygon.exterior,*polygon.interiors]:
            points=[]
            for x,y in list(ring.coords)[:-1]:
                if not points or math.dist(points[-1],(x,y))>1e-8:points.append((x,y))
            if len(points)>2:wp=wp.polyline(points).close()
        solids.extend(wp.extrude(z1-z0).val().Solids())
    if not solids:raise ValueError('Empty required prism')
    return cq.Compound.makeCompound(solids)

def audit_delta(before,after,allowed,protected=None):
    errors=[]
    if not before.isValid() or not after.isValid():errors.append('invalid STEP solid')
    if len(after.Solids())!=len(before.Solids()):errors.append('solid count changed')
    removed=cut_union(before,after).Volume()
    added=cut_union(after,before)
    added_volume=added.Volume()
    outside=cut_union(added,allowed).Volume() if added_volume>1e-9 else 0.
    missing=cut_union(allowed,after).Volume()
    obstruction=0. if protected is None or added_volume<=1e-9 else added.intersect(protected).Volume()
    if removed>VOLUME_TOLERANCE:errors.append('baseline material removed')
    if outside>VOLUME_TOLERANCE:errors.append('added material outside local cover allowance')
    if missing>VOLUME_TOLERANCE:errors.append('requested cover missing')
    if obstruction>VOLUME_TOLERANCE:errors.append('protected void obstructed')
    a,b=after.BoundingBox(),before.BoundingBox()
    if abs(a.zmin-b.zmin)>1e-5 or abs(a.zmax-b.zmax)>1e-5 or a.zmax>2.50001:
        errors.append('lower height changed')
    return {'errors':errors,'removed_mm3':removed,'added_mm3':added_volume,
            'off_allowance_added_mm3':outside,'missing_requested_mm3':missing,
            'new_material_in_protected_void_mm3':obstruction,'volume_tolerance_mm3':VOLUME_TOLERANCE,
            'baseline_z_mm':[b.zmin,b.zmax],'revised_z_mm':[a.zmin,a.zmax]}

def locality_errors(outline,clearance,wall,patch,part_patches,retained_gap=None):
    errors=[]
    exposed=[p for p in getattr(clearance,'geoms',[clearance]) if p.intersects(outline.boundary)]
    if not exposed:return ['no exposed baseline opening']
    # Independently bound the local zones; never accept a global perimeter band
    # simply because the generator declared it as its expected wall.
    local=unary_union(exposed)
    zone=local.buffer(.401+.30+.002,quad_segs=64)
    outer_allowance=local.buffer(.401+.002,quad_segs=64).union(outline)
    for name,shape in [('wall',wall),('floor patch',patch)]:
        if shape.difference(zone).area>.001:errors.append(name+' is not local to exposed openings')
        if shape.difference(outer_allowance).area>.001:errors.append(name+' expands beyond local allowance')
    if wall.intersection(clearance).area>.001:errors.append('wall crosses component clearance')
    union=unary_union(part_patches)
    if union.difference(patch).area>.001:errors.append('part patches exceed local patch')
    missing=patch.difference(union)
    if retained_gap is None:
        if missing.area>.001:errors.append('part patches do not cover exact local patch')
    elif missing.difference(retained_gap.buffer(1e-7)).area>.001:
        errors.append('part patches omit material outside retained seam')
    if retained_gap is not None and union.intersection(retained_gap).area>.001:
        errors.append('local patches close retained seam')
    if any(a.intersection(b).area>.001 for i,a in enumerate(part_patches) for b in part_patches[i+1:]):
        errors.append('local patches overlap split parts')
    return errors

def audit_side(side):
    path=STAGE/f'{side}-lower.json'
    manifest_sha=digest(path)
    record=json.loads(path.read_text(encoding='utf8'))
    bindings=dict(record['source_sha256'])
    bindings[path.relative_to(ROOT).as_posix()]=manifest_sha
    for source in [Path(__file__),ROOT/'tools/test_review_kc2_local_covers.py']:
        bindings[source.relative_to(ROOT).as_posix()]=digest(source)
    for output in record['outputs'].values():
        bindings[(STAGE/output['step']).relative_to(ROOT).as_posix()]=output['step_sha256']
        for name,mesh in output['meshes'].items():
            bindings[(STAGE/name).relative_to(ROOT).as_posix()]=mesh['sha256']
    if changed_bindings(ROOT,bindings):raise ValueError('Inputs changed before audit: '+str(changed_bindings(ROOT,bindings)))
    if record.get('status')!='generated_not_independently_verified':raise ValueError('Generation incomplete')
    if record.get('baseline_commit')!=BASELINE:raise ValueError('Wrong baseline')
    if record.get('physical_qualified') is not False:raise ValueError('Unearned physical qualification')
    for source,sha in record['source_sha256'].items():
        if digest(ROOT/source)!=sha:raise ValueError('Generation source changed: '+source)
    outline=wkt.loads(record['outline_wkt']);clearance=wkt.loads(record['clearance_wkt'])
    wall=wkt.loads(record['wall_wkt']);patch=wkt.loads(record['floor_patch_wkt'])
    part_patches=[wkt.loads(v) for v in record['part_patches_wkt']]
    retained_gap=None;baseline_code_bytes=None
    if side=='right':
        baseline_code_bytes=subprocess.check_output(['git','show',BASELINE+':tools/generate_kc2_x3_v2_housings.py'],cwd=ROOT)
        tree=ast.parse(baseline_code_bytes.decode('utf8'))
        gap=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='RIGHT_SPLIT_CLEARANCE_MM' for t in n.targets))
        if abs(gap-.2)>1e-9:raise ValueError('Unexpected baseline split clearance')
        sx=(outline.bounds[0]+outline.bounds[2])/2
        retained_gap=box(sx-gap/2,outline.bounds[1]-10,sx+gap/2,patch.bounds[3]+10)
    errors=locality_errors(outline,clearance,wall,patch,part_patches,retained_gap)
    if record.get('opening_count')!=(5 if side=='left' else 7):errors.append('wrong local window inventory')
    exposed=[p for p in getattr(clearance,'geoms',[clearance]) if p.intersects(outline.boundary)]
    if len(exposed)!=record.get('opening_count'):errors.append('declared window count differs from geometry')
    if record.get('wall_z_mm')!=[-1.,2.5] or record.get('floor_z_mm')!=[-2.2,-1.]:errors.append('declared datums changed')
    effective_patch=unary_union(part_patches);effective_wall=wall.intersection(effective_patch)
    allowed=cq.Compound.makeCompound([*prism(effective_wall,-1,2.5).Solids(),*prism(effective_patch,-2.2,-1).Solids()])
    protected=prism(clearance,-1,2.5)
    report={'requirements':['CON-ARCH-006','OPS-ARCH-006'],'baseline_commit':BASELINE,
        'side':side,'errors':errors,'physical_qualified':False,'source_sha256':bindings,
        'git_source_sha256':{},'variants':{},'scope':'Actual additive-only lower STEP delta, local cover/floor inclusion, declared component clearance, original magnet/pilot void protection and per-part STL topology/envelope. Upper cover and physical qualifications separate.'}
    if baseline_code_bytes is not None:
        report['git_source_sha256']['tools/generate_kc2_x3_v2_housings.py']=hashlib.sha256(baseline_code_bytes).hexdigest()
        report['retained_seam']={'width_mm':.2,'x_center_mm':sx,'omitted_local_patch_area_mm2':patch.difference(effective_patch).area}
    original_manifest_path='hardware/MODELS/kc2_housing_manifest.json'
    original_manifest_bytes=subprocess.check_output(['git','show',BASELINE+':'+original_manifest_path],cwd=ROOT)
    old=json.loads(original_manifest_bytes)
    report['git_source_sha256'][original_manifest_path]=hashlib.sha256(original_manifest_bytes).hexdigest()
    pilot_solids=[]
    for hole in old['outputs'][side]['mounting_system']['holes']:
        x,y=hole['housing_center_mm']
        pilot_solids.append(cq.Solid.makeCylinder(.55,2.8,cq.Vector(x,y,-.3),cq.Vector(0,0,1)))
    pilots=cq.Compound.makeCompound(pilot_solids)
    before_shapes={};after_shapes={}
    with tempfile.TemporaryDirectory(prefix='kc2-local-lower-review-') as temp:
        for variant in ['normal','magnetic']:
            output=record['outputs'][variant];name=output['step']
            source='hardware/MODELS/'+name
            data=subprocess.check_output(['git','show',BASELINE+':'+source],cwd=ROOT)
            report['git_source_sha256'][source]=hashlib.sha256(data).hexdigest()
            if report['git_source_sha256'][source]!=output['baseline_step_sha256']:raise ValueError('Wrong baseline STEP bytes')
            basepath=Path(temp)/name;basepath.write_bytes(data)
            afterpath=STAGE/name
            if digest(afterpath)!=output['step_sha256']:raise ValueError('Output STEP changed')
            print(side,variant,'import baseline and actual STEP',flush=True)
            before=cq.importers.importStep(str(basepath)).val();after=cq.importers.importStep(str(afterpath)).val()
            before_shapes[variant]=before;after_shapes[variant]=after
            if retained_gap is not None:
                # Local-cover seam extension must line up with the actual old
                # floor gap, not merely an untrusted mask in the new manifest.
                interior_gap=retained_gap.buffer(-.00001).intersection(patch).intersection(outline)
                if interior_gap.is_empty:raise ValueError('No baseline floor evidence for local seam extension')
                collision=before.intersect(prism(interior_gap,-2.2,-1.)).Volume()
                report['retained_seam'][variant+'_baseline_floor_gap_obstruction_mm3']=collision
                if collision>VOLUME_TOLERANCE:errors.append('local seam does not match baseline floor gap')
            print(side,variant,'actual local Boolean delta',flush=True)
            row=audit_delta(before,after,allowed,protected)
            added=cut_union(after,before)
            row['new_material_in_pilots_mm3']=added.intersect(pilots).Volume()
            if row['new_material_in_pilots_mm3']>VOLUME_TOLERANCE:row['errors'].append('original pilot filled')
            row['meshes']={}
            solids=sorted(after.Solids(),key=lambda s:s.Center().x)
            names=sorted(output['meshes'])
            if len(names)!=len(solids):row['errors'].append('wrong printable part count')
            for name,solid in zip(names,solids):
                meshpath=STAGE/name;sha=digest(meshpath)
                if sha!=output['meshes'][name]['sha256']:raise ValueError('Output mesh changed')
                mesh=trimesh.load_mesh(meshpath)
                bb=solid.BoundingBox();expected=[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax]
                bound_error=max(abs(a-b) for a,b in zip(mesh.bounds.flatten(),expected))
                volume_error=abs(mesh.volume-solid.Volume())
                ok=(mesh.is_watertight and mesh.is_winding_consistent and mesh.body_count==1
                    and max(mesh.extents)<=150.001 and bound_error<.02 and volume_error<max(.01,solid.Volume()*.0005))
                row['meshes'][name]={'passes':bool(ok),'bounds_mm':mesh.bounds.flatten().tolist(),
                    'bounds_error_mm':bound_error,'volume_error_mm3':volume_error,'center_mass_mm':mesh.center_mass.tolist()}
                if not ok:row['errors'].append('invalid STL: '+name)
                report['source_sha256'][meshpath.relative_to(ROOT).as_posix()]=sha
            errors.extend(variant+': '+e for e in row['errors'])
            report['variants'][variant]=row
        print(side,'compare original magnet void',flush=True)
        original_void=cut_union(before_shapes['normal'],before_shapes['magnetic'])
        revised_void=cut_union(after_shapes['normal'],after_shapes['magnetic'])
        missing=cut_union(original_void,revised_void).Volume();extra=cut_union(revised_void,original_void).Volume()
        report['magnet_void']={'original_mm3':original_void.Volume(),'revised_mm3':revised_void.Volume(),
                               'missing_mm3':missing,'extra_mm3':extra}
        if missing>VOLUME_TOLERANCE or extra>VOLUME_TOLERANCE:errors.append('magnet geometry changed')
    changed=changed_bindings(ROOT,bindings)
    report['inputs_unchanged_at_finish']=not changed
    if changed:errors.append('inputs changed during audit: '+str(changed))
    report['status']='pass' if not errors else 'failed'
    (STAGE/f'{side}-lower-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'side':side,'status':report['status'],'errors':errors}),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side',required=True,choices=['left','right'])
    args=parser.parse_args()
    raise SystemExit(bool(audit_side(args.side)['errors']))
