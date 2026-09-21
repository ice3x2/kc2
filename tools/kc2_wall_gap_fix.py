"""CON-ARCH-006 additive closure of unintended same-body perimeter slits.

Never perform unconstrained mesh hole filling. Functional recesses, assembly
interfaces and body ownership are explicit exclusions from a local 2D closure.
"""
from pathlib import Path
import argparse
import json
from shapely import wkt
from shapely.geometry import GeometryCollection, Point
from shapely.ops import unary_union
from tools.kc2_pcb_seating import digest, horizontal_section

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/wall-gap-fix-20260921'
BASELINE='83ae5fcd998d95eea55aac33d42069e62d7d2aab'
KINDS=('normal','magnetic','mx','choc_v1','deep_sea')

def bridge_slots(stock,allowed,protected):
    if any(not g.is_valid for g in (stock,allowed,protected)):
        raise ValueError('Invalid planar input')
    closed=stock.buffer(.26,join_style=2).buffer(-.26,join_style=2)
    missing=closed.difference(stock).intersection(allowed).difference(protected)
    useful=unary_union([g for g in getattr(missing,'geoms',[missing])
                       if g.geom_type=='Polygon' and g.area>.02])
    # Small inward overlap avoids coincident-only CAD joins. Allowed/protected
    # constraints still apply to every point of the full added prism.
    return useful.buffer(.035,join_style=2).intersection(allowed).difference(protected).simplify(1e-7,preserve_topology=True)

def names(side,kind):
    lower=kind in ('normal','magnetic')
    stem=f'kc2_{side}_lower_housing'+('_magnetic' if kind=='magnetic' else '') if lower else f'kc2_{side}_{kind}_upper_housing'
    if side=='left':return stem,[stem+'.stl']
    prefix=stem.removesuffix('_magnetic')
    suffix='_magnetic' if kind=='magnetic' else ''
    return stem,[prefix+'_part_'+letter+suffix+'.stl' for letter in 'ab']

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def make_plan():
    import trimesh
    sources={}
    def read(name):
        path=ROOT/name;sources[name]=digest(path)
        return json.loads(path.read_text(encoding='utf-8'))
    wrap=read('docs/reports/wrap-housings-20260920/plan.json')
    board=read('docs/reports/wrap-housings-20260920/board-envelopes.json')
    jobs={}
    for side in ('left','right'):
        p=wrap['sides'][side]
        domain=wkt.loads(p['domain_wkt'])
        exclusions=wkt.loads(p['central_wkt']).union(wkt.loads(p['service_wkt']))
        lower_protected=wkt.loads(read(f'docs/reports/reinforced-covers-20260913/{side}-lower.json')['clearance_wkt'])
        for kind in KINDS:
            stem,files=names(side,kind)
            for name in [stem+'.step',stem+'.f3d',*files]:
                path=ROOT/'hardware/MODELS'/name;sources[path.relative_to(ROOT).as_posix()]=digest(path)
            lower=kind in ('normal','magnetic')
            meshes=[trimesh.load_mesh(ROOT/'hardware/MODELS'/name) for name in files]
            projections=[horizontal_section(m,-1.6) if lower else None for m in meshes]
            if not lower:
                old=read(f'docs/reports/registered-housing-fit-20260913/evidence/upper/{side}-{kind}/generation.json')
                profile=read(f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json')
                protected=unary_union([wkt.loads(profile['plan_wkt'][k]) for k in ('body','openings','service','bores','pockets')])
                protected=protected.union(unary_union([wkt.loads(v['groove']) for v in old['registrars'].values()]))
                projections=[unary_union([wkt.loads(layer['wkt']) for layer in part['layers']]).union(wkt.loads(p['upper_rim_parts_wkt'][kind][i])) for i,part in enumerate(old['parts'])]
            else:
                mounts=read(f'docs/reports/solid-filled-plates-20260913/{side}-mx.json')['mounting_centers']
                protected=lower_protected.union(unary_union([Point(*xy).buffer(.81) for xy in mounts]))
            parts=[]
            for i,mesh in enumerate(meshes):
                allowed=domain.buffer(1.5,join_style=2).difference(domain.buffer(-3,join_style=2)).difference(exclusions)
                # Upper stock projection contains the very slit being closed;
                # allow a local inward bridge while retaining the exact domain.
                owner=projections[i] if lower else projections[i].buffer(.3,join_style=2).intersection(domain)
                allowed=allowed.intersection(owner)
                if len(projections)>1:
                    allowed=allowed.difference(projections[1-i].buffer(.3999,join_style=2))
                layers=[dict(z0=-1.,z1=2.5,wkt=horizontal_section(mesh,.75).wkt)] if lower else old['parts'][i]['layers']
                patches=[]
                for layer in layers:
                    lo,hi=layer['z0'],layer['z1']
                    if not lower and hi<=4.4:continue
                    stock=wkt.loads(layer['wkt'])
                    if not lower:
                        stock=stock.union(wkt.loads(p['upper_rim_parts_wkt'][kind][i]))
                    patch=bridge_slots(stock,allowed,protected)
                    if patch.is_empty:continue
                    patches.append(dict(z0=lo,z1=hi,wkt=patch.wkt,
                        added_plan_area_mm2=patch.difference(stock).area,
                        region_count=len(getattr(patch,'geoms',[patch]))))
                parts.append(dict(patches=patches,protected_wkt=protected.wkt,allowed_wkt=allowed.wkt))
            jobs[side+':'+kind]=dict(side=side,kind=kind,stem=stem,stl_names=files,parts=parts)
            print(side,kind,[(len(v['patches']),sum(x['added_plan_area_mm2']*(x['z1']-x['z0']) for x in v['patches'])) for v in parts],flush=True)
    for name in ('tools/kc2_wall_gap_fix.py','tools/test_kc2_wall_gap_fix.py','tools/kc2_pcb_seating.py'):
        sources[name]=digest(ROOT/name)
    plan=dict(requirement='CON-ARCH-006',baseline_commit=BASELINE,jobs=jobs,source_sha256=sources,
              physical_qualified=False,method='Same-part local closing at radius 0.26 mm, explicit protected/ownership masks, 0.035 mm root overlap')
    write(STAGE/'plan.json',plan)
    return plan

def build(label):
    import cadquery as cq
    from tools.kc2_central_flexure import prism
    from tools.stage_kc2_registered_lower import audit_additive
    from tools.kc2_step_whitespace import normalize
    plan=json.loads((STAGE/'plan.json').read_text())
    for name,sha in plan['source_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed input '+name)
    job=plan['jobs'][label];stem=job['stem']
    folder=STAGE/label.replace(':','-');folder.mkdir(parents=True,exist_ok=True)
    print('import',label,flush=True)
    before=sorted(cq.importers.importStep(str(ROOT/'hardware/MODELS'/(stem+'.step'))).solids().vals(),key=lambda s:s.Center().x)
    if len(before)!=len(job['parts']):raise ValueError('Wrong body count')
    shapes=[];proofs=[]
    for i,(base,part) in enumerate(zip(before,job['parts'])):
        print('fuse',label,i,flush=True)
        patches=[prism(wkt.loads(p['wkt']),p['z0'],p['z1']) for p in part['patches']]
        solids=[s for p in patches for s in p.Solids()]
        final=base.fuse(*solids).clean() if solids else base
        proof=audit_additive(base,final,patches)
        proof['missing_patch_mm3']=sum(abs(p.cut(final).Volume()) for p in patches)
        if proof['errors'] or proof['missing_patch_mm3']>.002:raise ValueError(proof)
        proof['base_volume_mm3']=base.Volume();proof['final_volume_mm3']=final.Volume()
        shapes.append(final);proofs.append(proof)
    path=folder/(stem+'.step')
    cq.exporters.export(cq.Compound.makeCompound(shapes),str(path))
    path.write_bytes(normalize(path.read_bytes())[0])
    reread=cq.importers.importStep(str(path)).val()
    if not reread.isValid() or len(reread.Solids())!=len(shapes) or abs(reread.Volume()-sum(s.Volume() for s in shapes))>.02:
        raise ValueError('STEP round trip failed')
    result=dict(status='cad_generated',label=label,parts=proofs,step=path.name,step_sha256=digest(path),
                plan_sha256=digest(STAGE/'plan.json'),source_sha256=plan['source_sha256'])
    write(folder/'generation.json',result)
    print('done',label,flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('job')
    arg=parser.parse_args().job
    make_plan() if arg=='plan' else build(arg)
