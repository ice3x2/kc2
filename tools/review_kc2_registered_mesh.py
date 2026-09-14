"""CON-ARCH-006 actual new upper STL complete-section and printer checks."""
from pathlib import Path
import argparse,json,hashlib

ROOT=Path(__file__).resolve().parents[1]
def required_stls(side,kind):
    if side not in ('left','right') or kind not in ('mx','choc_v1','deep_sea'):raise ValueError('Unknown identity')
    stem=f'kc2_{side}_{kind}_upper_housing'
    return [stem+'.stl'] if side=='left' else [stem+'_part_a.stl',stem+'_part_b.stl']

def review(side,kind):
    import trimesh
    from shapely import wkt
    from tools.kc2_solid_plate import Layer
    from tools.review_kc2_filled_mesh import audit_mesh
    names=required_stls(side,kind);folder=ROOT/'.codex-tmp/registered-housing-fit/upper'/(side+'-'+kind)
    path=folder/'generation.json';r=json.loads(path.read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if (r.get('status')!='generated_pending_independent_review' or r.get('side')!=side or r.get('kind')!=kind or
            len(r['parts'])!=len(names) or {n for n in r['outputs'] if n.endswith('.stl')}!=set(names)):
        raise ValueError('Incomplete print inventory')
    bindings=dict(r['source_sha256'])
    for p in [path,Path(__file__),ROOT/'tools/test_review_kc2_registered_mesh.py',ROOT/'tools/review_kc2_filled_mesh.py',
              ROOT/'tools/test_review_kc2_filled_mesh.py',ROOT/'tools/kc2_solid_plate.py']:
        bindings[p.relative_to(ROOT).as_posix()]=digest(p)
    for name,sha in r['outputs'].items():bindings[(folder/name).relative_to(ROOT).as_posix()]=sha
    def validate():
        for name,sha in bindings.items():
            if digest(ROOT/name)!=sha:raise ValueError('Changed mesh audit source '+name)
    validate();parts=[];errors=[]
    for name,part in zip(names,r['parts']):
        print('actual STL complete sections',name,flush=True)
        mesh=trimesh.load_mesh(folder/name,process=True)
        layers=[Layer(l['z0'],l['z1'],wkt.loads(l['wkt'])) for l in part['layers']]
        a=audit_mesh(mesh,layers);a['stl']=name;parts.append(a);errors.extend(a['errors'])
    validate()
    result=dict(status='pass' if not errors else 'failed',errors=errors,side=side,kind=kind,requirements=['CON-ARCH-006','OPS-ARCH-006'],
        physical_qualified=False,source_sha256=bindings,parts=parts,
        scope='Actual watertight STL prismatic faces, all height strata, declared full material/voids, positive volume,150mm printer envelope')
    (folder/'mesh-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],errors,flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('side');p.add_argument('kind');a=p.parse_args()
    raise SystemExit(0 if review(a.side,a.kind)['status']=='pass' else 1)
