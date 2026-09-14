"""CON-ARCH-006 fresh STL cross-sections and actual STEP patch clearance."""
from pathlib import Path
import json
import numpy as np
import trimesh
from shapely.geometry import Polygon, GeometryCollection, box
from tools.kc2_smooth_central_seam import ROOT, STAGE, patches, digest


def mesh_section(mesh,x):
    section=mesh.section(plane_origin=[x,0,0],plane_normal=[1,0,0])
    result=GeometryCollection()
    if section is not None:
        for points in section.discrete:
            polygon=Polygon(points[:,1:3])
            if not polygon.is_valid: polygon=polygon.buffer(0)
            result=result.symmetric_difference(polygon)
    return result


def review():
    import cadquery as cq
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from tools.generate_kc2_magnetic_housings import inspect_mesh
    from tools.kc2_flat_central_native import compare_cad_signatures
    from tools.review_kc2_flat_central_native import _signature
    rows={}; errors=[]; bindings={}; actuals={}
    fig,axes=plt.subplots(4,2,figsize=(12,12),layout='constrained')
    for side in ('left','right'):
        for kind in ('normal','magnetic'):
            label=side+':'+kind; folder=STAGE/'lower'/(side+'-'+kind)
            record_path=folder/'generation.json'
            r=json.loads(record_path.read_text()); stem=f'kc2_{side}_lower_housing'+('_magnetic' if kind=='magnetic' else '')
            path=folder/(stem+'.step'); print('review',label,flush=True)
            for name,sha in r['source_sha256'].items():
                if digest(ROOT/name)!=sha: raise ValueError('Changed generation input: '+name)
                bindings[name]=sha
            if r['errors'] or digest(path)!=r['outputs'][path.name]: raise ValueError('Unreviewed STEP')
            actual=cq.importers.importStep(str(path)).val();actuals[label]=actual
            if not actual.isValid(): raise ValueError('Invalid reopened solid')
            row_errors=compare_cad_signatures(r['signature'],_signature(actual))
            bindings[path.relative_to(ROOT).as_posix()]=digest(path)
            bindings[record_path.relative_to(ROOT).as_posix()]=digest(record_path)
            names=[n for n in r['outputs'] if n.endswith('.stl')]
            solids=sorted(actual.Solids(),key=lambda s:s.Center().x)
            meshes=[];mesh_records=[]
            for name,solid in zip(names,solids):
                mpath=folder/name
                if digest(mpath)!=r['outputs'][name]: raise ValueError('Changed STL')
                bindings[mpath.relative_to(ROOT).as_posix()]=digest(mpath)
                mr=inspect_mesh(mpath,solid);row_errors.extend(mr.get('errors',[]));mesh_records.append(mr)
                meshes.append(trimesh.load(mpath,force='mesh'))
            mesh=trimesh.util.concatenate(meshes)
            wall_x=-.9 if side=='left' else 150.3
            floor_x=.7 if side=='left' else 148.7
            section=mesh_section(mesh,wall_x);floor=mesh_section(mesh,floor_x)
            checks=[]
            for y in (95.,117.):
                wall_missing=box(y-2.85,-2.2,y+2.85,4.1).difference(section).area
                floor_missing=box(y-2.85,-2.2,y+2.85,-1).difference(floor).area
                if max(wall_missing,floor_missing)>.0001: row_errors.append('STL still has guide cavity')
                checks.append(dict(y_mm=y,wall_missing_mm2=wall_missing,floor_missing_mm2=floor_missing))
                if kind=='normal':
                    oldnames=names
                    oldmesh=trimesh.util.concatenate([trimesh.load(ROOT/'hardware/MODELS'/n,force='mesh') for n in oldnames])
                    oldsection=mesh_section(oldmesh,wall_x)
                    for column,g in enumerate((oldsection,section)):
                        index=(0 if side=='left' else 2)+(0 if y==95 else 1)
                        ax=axes[index,column];roi=box(y-4,-2.5,y+4,4.5);g=g.intersection(roi)
                        for p in getattr(g,'geoms',[g]):
                            if p.is_empty or not hasattr(p,'exterior'):continue
                            v=np.array(p.exterior.coords);ax.fill(v[:,0]-y,v[:,1],color='#298b9c' if column else '#a6afb9')
                            for hole in p.interiors:
                                v=np.array(hole.coords);ax.fill(v[:,0]-y,v[:,1],color='white')
                        ax.set(xlim=(-4,4),ylim=(-2.5,4.5),aspect='equal',xlabel='Y from former guide center (mm)',ylabel='Z (mm)',title=f'{side.title()} Y={y:g}: '+('AFTER' if column else 'BEFORE'))
                        ax.grid(alpha=.2)
            rows[label]=dict(errors=row_errors,sections=checks,meshes=mesh_records)
            errors.extend(label+': '+e for e in row_errors)
    print('check added wall against opposite actual housing',flush=True)
    joins=[]
    for kind in ('normal','magnetic'):
        left=actuals['left:'+kind].mirror('YZ').translate((170.1125,0,0))
        right=actuals['right:'+kind].mirror('YZ').translate((323.3125,0,0))
        for side,other,offset in [('left',right,170.1125),('right',left,323.3125)]:
            for i,p in enumerate(patches(side)):
                world=p.mirror('YZ').translate((offset,0,0))
                overlap=world.intersect(other).Volume(); gap=world.distance(other)
                joins.append(dict(kind=kind,side=side,patch=i,overlap_mm3=overlap,gap_mm=gap))
                if overlap>.002 or gap<.39999:errors.append('Opposite housing clearance lost')
    fig.savefig(STAGE/'wall-sections.png',dpi=150);plt.close(fig)
    for name in ('tools/kc2_smooth_central_seam.py','tools/test_kc2_smooth_central_seam.py','tools/review_kc2_smooth_central_seam.py'):
        bindings[name]=digest(ROOT/name)
    result=dict(status='pass' if not errors else 'failed',errors=errors,rows=rows,joins=joins,
        source_sha256=bindings,physical_qualified=False,
        scope='Fresh STEP signatures and STL manifold/section checks; new patches against complete opposite housing. Existing assembly protections follow unchanged stock and bounded additive proof.')
    (STAGE/'review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],errors,flush=True)
    return result


if __name__=='__main__': raise SystemExit(bool(review()['errors']))
