"""CON-ARCH-006 four actual central feature BReps, staging only.

Not standalone print recommendations, complete lower housings or native files.
Existing component clearance cutters trim ONLY additional attachment roots.
"""
from pathlib import Path
import hashlib,json
from shapely import wkt,affinity
from tools.kc2_central_flexure import flexure_plan,place_feature_solids,prism

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/registered-housing-fit/central'

def safe_stage(path):
    path=Path(path).resolve()
    if not path.is_relative_to((ROOT/'.codex-tmp/registered-housing-fit').resolve()):
        raise ValueError('Refuse nonstaging export')
    return path

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run():
    import cadquery as cq
    import trimesh
    stage=safe_stage(STAGE);stage.mkdir(parents=True,exist_ok=True)
    sources=[Path(__file__),ROOT/'tools/kc2_central_flexure.py',ROOT/'tools/kc2_central_fit.py',
             ROOT/'tools/test_kc2_central_flexure.py',ROOT/'tools/test_stage_kc2_central_features.py']
    sources += [ROOT/f'docs/reports/reinforced-covers-20260913/{s}-lower.json' for s in ('left','right')]
    bindings={p.relative_to(ROOT).as_posix():digest(p) for p in sources}
    records=[];outputs={}
    for side in ('left','right'):
        record=json.loads((ROOT/f'docs/reports/reinforced-covers-20260913/{side}-lower.json').read_text())
        protected=wkt.loads(record['clearance_wkt']);outline=wkt.loads(record['new_outline_wkt'])
        shapes=place_feature_solids(side,protected)
        for y,shape in zip((95.,117.),shapes):
            name=f'{side}-central-y{int(y)}';step=stage/(name+'.step');stl=stage/(name+'.stl')
            cq.exporters.export(shape,str(step));reopened=cq.importers.importStep(str(step)).val()
            if not reopened.isValid() or len(reopened.Solids())!=1 or abs(reopened.Volume()-shape.Volume())>1e-6:
                raise ValueError('Feature STEP mismatch')
            cq.exporters.export(shape,str(stl),tolerance=.005,angularTolerance=.08)
            mesh=trimesh.load_mesh(stl)
            if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split())!=1:
                raise ValueError('Feature STL invalid')
            b=shape.BoundingBox();local=protected.intersection(wkt.loads(record['new_outline_wkt']).buffer(2))
            # Only near this tiny feature needs a cutting solid, not entire PCB.
            from shapely.geometry import box
            local=local.intersection(box(b.xmin-.01,b.ymin-.01,b.xmax+.01,b.ymax+.01))
            collision=0 if local.is_empty else shape.intersect(prism(local,-1,2.5)).Volume()
            if collision>1e-7:raise ValueError('Protected component intersection')
            row=dict(name=name,volume_mm3=shape.Volume(),bounds_mm=[b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax],
                     component_intersection_mm3=collision,step_round_trip=True,stl_watertight=True)
            if side=='right':
                free=flexure_plan()['free_space']
                mapped=affinity.translate(affinity.scale(free,xfact=-1,yfact=1,origin=(0,0)),xoff=153.3,yoff=y)
                row['existing_outline_in_free_space_mm2']=mapped.intersection(outline).area
                if row['existing_outline_in_free_space_mm2']>1e-8:
                    raise ValueError('Existing housing may obstruct flexure pocket')
            records.append(row);outputs[step.name]=digest(step);outputs[stl.name]=digest(stl)
    if bindings!={p.relative_to(ROOT).as_posix():digest(p) for p in sources}:raise ValueError('Sources changed')
    result=dict(status='feature_geometry_pass_integration_pending',requirements=['CON-ARCH-006','CON-ARCH-007'],
                physical_qualified=False,native_verified=False,canonical_changed=False,
                source_sha256=bindings,outputs=outputs,features=records,
                pending=['complete lower fusion','exact integrated insertion sweep','PCB/support/magnet/root checks',
                         'printed force/strength/coupon','actual Fusion native','canonical publication'])
    (stage/'central-features.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_sha256','outputs','features')}))
    return result

if __name__=='__main__':run()
