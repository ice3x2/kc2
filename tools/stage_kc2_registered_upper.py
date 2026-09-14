"""CON-ARCH-006 new filled upper/registrar STEP+STL; no canonical writes."""
from pathlib import Path
import json,hashlib,argparse
from shapely import wkt
from shapely.geometry import box,GeometryCollection
from shapely.ops import unary_union
from tools.kc2_registered_wall_plan import plan_registrars
from tools.kc2_registered_upper import compose_upper
from tools.kc2_solid_plate import build_solid

ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stage_path(side,kind):
    if side not in ('left','right') or kind not in ('mx','choc_v1','deep_sea'):raise ValueError('Invalid identity')
    return ROOT/'.codex-tmp/registered-housing-fit/upper'/(side+'-'+kind)

def generate(side,kind):
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import load_plans,inspect_mesh,bounds
    folder=stage_path(side,kind);folder.mkdir(parents=True,exist_ok=True)
    oldpath=ROOT/f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json'
    sources=[Path(__file__),oldpath,*[ROOT/'tools'/n for n in (
        'kc2_registered_upper.py','kc2_registered_wall_plan.py','kc2_solid_plate.py','kc2_filled_plate_profiles.py',
        'test_kc2_registered_upper.py','test_stage_kc2_registered_upper.py',
        'generate_kc2_magnetic_housings.py','generate_kc2_x3_v2_housings.py','generate_kc2_housings.py','render_kc2_x3_joined.py')]]
    sources += [ROOT/f'hardware/PCB/kc2_{s}/kc2_{s}.kicad_pcb' for s in ('left','right')]
    if side=='right':sources+=[ROOT/'tools/kc2_profile_split.py']
    before={p.relative_to(ROOT).as_posix():digest(p) for p in sources}
    print('extract actual PCB geometry',flush=True)
    plans,_,transform=load_plans();p=plans[side]
    old=json.loads(oldpath.read_text());gs={k:wkt.loads(v) for k,v in old['plan_wkt'].items()}
    rows=[(v['z0'],v['z1'],wkt.loads(v['wkt'])) for part in old['parts'] for v in part['layers']]
    levels=sorted({z for a,b,g in rows for z in (a,b) if 4.4<=z<=6.25}|{4.4,6.25})
    common=None
    for a,b in zip(levels,levels[1:]):
        mid=(a+b)/2;section=unary_union([g for lo,hi,g in rows if lo<=mid<hi])
        common=section if common is None else common.intersection(section)
    regs=plan_registrars(side=side,kind=kind,board=p['board'],lower_floor=p['housing_outline'],upper_solid=common,
        lower_protected=p['all_component_cutouts'],
        upper_protected=unary_union([gs[k] for k in ('body','openings','service','bores','pockets','bosses')]),
        central_exclusion=box(-10,28,20,140) if side=='left' else box(145,28,175,140),
        split_exclusion=GeometryCollection())
    domain=gs['domain'].union(unary_union([r.addition for r in regs.values()]))
    partition=None;masks=[domain]
    if side=='right':
        from tools.kc2_profile_split import profile_split
        a,b,partition=profile_split(domain,gs['openings'],gs['service'],old['mounting_centers']);masks=[a,b]
        for r in regs.values():
            if not any(mask.buffer(1e-7).covers(r.addition) for mask in masks):raise ValueError('Registrar crosses A/B split')
    parts=compose_upper(kind,gs,list(regs.values()),masks)
    report=dict(requirements=['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],status='building',side=side,kind=kind,
        physical_qualified=False,native_verified=False,canonical_changed=False,source_sha256=before,
        transform=transform,partition=partition,parts=[],outputs={},
        registrars={k:{n:getattr(r,n).wkt for n in ('wall','addition','groove','floor_addition')} for k,r in regs.items()})
    path=folder/'generation.json'
    def write():path.write_text(json.dumps(report,indent=2)+'\n')
    write();solids=[];stem=f'kc2_{side}_{kind}_upper_housing'
    for i,layers in enumerate(parts):
        print('build actual filled solid',side,kind,i,flush=True)
        solid=build_solid(layers);solids.append(solid)
        name=stem+('' if side=='left' else '_part_'+chr(97+i))+'.stl';stl=folder/name
        cq.exporters.export(solid,str(stl),tolerance=.005,angularTolerance=.08)
        mesh=inspect_mesh(stl,solid)
        report['parts'].append(dict(bounds_mm=bounds(solid),volume_mm3=solid.Volume(),mesh=mesh,
            layers=[dict(z0=l.z0,z1=l.z1,wkt=l.geometry.wkt) for l in layers]))
        report['outputs'][name]=digest(stl);write()
    step=folder/(stem+'.step');cq.exporters.export(cq.Compound.makeCompound(solids),str(step))
    reopened=cq.importers.importStep(str(step)).solids().vals()
    if len(reopened)!=len(solids) or not all(s.isValid() for s in reopened):raise ValueError('STEP round-trip invalid')
    if abs(sum(s.Volume() for s in reopened)-sum(s.Volume() for s in solids))>.01:raise ValueError('STEP volume mismatch')
    if before!={p.relative_to(ROOT).as_posix():digest(p) for p in sources}:raise ValueError('Sources changed during generation')
    report['outputs'][step.name]=digest(step);report['status']='generated_pending_independent_review';write()
    print(side,kind,report['status'],flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('side');parser.add_argument('kind');args=parser.parse_args()
    generate(args.side,args.kind)
