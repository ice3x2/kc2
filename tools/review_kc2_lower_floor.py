"""CON-ARCH-006 per-job actual floor + STL topology/size gate; NO foot gate."""
from pathlib import Path
import argparse,json,hashlib
from tools.kc2_lower_floor import inspect_floor
from tools.kc2_lower_native_identity import native_output
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def review(side,magnetic=False,native=False):
    import cadquery as cq
    import trimesh
    if side not in ('left','right'):raise ValueError('Invalid side')
    variant='magnetic' if magnetic else 'normal';folder=ROOT/'.codex-tmp/registered-housing-fit/lower'/f'{side}-{variant}'
    gp=folder/'generation.json';g=json.loads(gp.read_text());name=f'kc2_{side}_lower_housing'+('_magnetic' if magnetic else '')+'.step'
    actual=folder/name
    if g['status']!='generated_pending_independent_review' or digest(actual)!=g['outputs'][name]:raise ValueError('Invalid generation')
    expected=1 if side=='left' else 2
    names=sorted(k for k in g['outputs'] if k.endswith('.stl'))
    if len(names)!=expected or g.get('body_count')!=expected:raise ValueError('Wrong body/STL inventory')
    paths=[Path(__file__),ROOT/'tools/kc2_lower_floor.py',ROOT/'tools/test_kc2_lower_floor.py',
        ROOT/'tools/review_kc2_filled_plates.py',ROOT/'tools/kc2_lower_native_identity.py',gp,actual]
    for path,sha in g['source_sha256'].items():
        p=ROOT/path
        if digest(p)!=sha:raise ValueError('Stale source '+path)
        paths.append(p)
    for name in names:
        p=folder/name
        if digest(p)!=g['outputs'][name]:raise ValueError('Changed mesh')
        paths.append(p)
    if native:
        np=folder/'native-generation.json';nr=json.loads(np.read_text());row=native_output(nr,side,variant,digest(gp),digest(actual));paths.append(np)
        for path,sha in nr['source_sha256'].items():
            p=ROOT/path
            if digest(p)!=sha:raise ValueError('Stale native source '+path)
            paths.append(p)
        for field in ('readback','f3d'):
            p=folder/row['readback_step' if field=='readback' else 'f3d']
            if digest(p)!=row[field+'_sha256']:raise ValueError('Changed native artifact')
            paths.append(p)
        actual=folder/row['readback_step']
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('actual structural floor/STL',side,variant,'native',native,flush=True)
    solids=sorted(cq.importers.importStep(str(actual)).solids().vals(),key=lambda s:s.Center().x)
    if len(solids)!=expected:raise ValueError('Wrong actual body count')
    rows=[];errors=[]
    for i,(solid,name) in enumerate(zip(solids,names)):
        row=inspect_floor(solid);mesh=trimesh.load_mesh(folder/name);bb=solid.BoundingBox()
        bounds=[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax]
        bound_error=max(abs(a-b) for a,b in zip(bounds,mesh.bounds.flatten()))
        volume_error=abs(float(mesh.volume)-solid.Volume())
        meshrow=dict(stl=name,sha256=digest(folder/name),watertight=bool(mesh.is_watertight),
            winding_consistent=bool(mesh.is_winding_consistent),components=len(mesh.split(only_watertight=False)),
            volume_mm3=float(mesh.volume),extents_mm=mesh.extents.tolist(),bounds_error_mm=bound_error,volume_error_mm3=volume_error)
        if not meshrow['watertight'] or not meshrow['winding_consistent'] or meshrow['components']!=1 or meshrow['volume_mm3']<=0:
            row['errors'].append('invalid STL topology/volume')
        if max(mesh.extents)>150.001:row['errors'].append('STL exceeds150mm')
        if bound_error>1e-4 or volume_error>max(.02,abs(solid.Volume())*1e-6):row['errors'].append('STL differs from BRep envelope/volume')
        row.update(part=i,mesh=meshrow);rows.append(row);errors.extend(f'part{i}: '+e for e in row['errors'])
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Source changed during audit')
    result=dict(requirements=['CON-ARCH-006'],status='fail' if errors else 'pass',errors=errors,side=side,magnetic=magnetic,
        native_readback=native,body_count=expected,parts=rows,source_sha256=frozen,physical_qualified=False,
        scope='Actual constant connected structural floor and all actual STL shells/positivevolume/150mm envelope; no silicone feet or adhesion')
    (folder/('floor'+('-native' if native else '')+'-review.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],errors,flush=True);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('side');p.add_argument('--magnetic',action='store_true');p.add_argument('--native',action='store_true');args=p.parse_args()
    raise SystemExit(bool(review(args.side,args.magnetic,args.native)['errors']))
