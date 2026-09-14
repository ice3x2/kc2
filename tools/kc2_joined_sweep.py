"""CON-ARCH-006 exact polygon translation sweep of conservative XY envelopes.

The swept set is start U end U all boundary-edge swept quadrilaterals.
Every point newly entering a translated polygon crosses its boundary, so this
is exact for polygonal inputs including holes/nonconvex disconnected regions.
It is not a finite-position sampling or a convex-hull shortcut of whole models.
"""
from dataclasses import dataclass
import math
from shapely import affinity
from shapely.geometry import Polygon,box
from shapely.ops import unary_union

REQUIRED_COMPONENTS={'pcb','old_lower','perimeter_floor','perimeter_wall',
                     'registrar_floor','registrar_wall','upper','central'}
CENTRAL_WORLD_ROI=unary_union([box(161.0125,39.25+y-5,177.0125,39.25+y+5) for y in (95.,117.)])


@dataclass(frozen=True)
class Envelope:
    name:str
    geometry:object
    z0:float
    z1:float


def horizontal_sweep(geometry,travel=-7.8):
    if isinstance(travel,bool) or not isinstance(travel,(int,float)) or not math.isfinite(travel) or travel>=0:
        raise ValueError('Negative finite approach travel required')
    if geometry.is_empty or not geometry.is_valid:raise ValueError('Invalid envelope')
    strips=[geometry,affinity.translate(geometry,xoff=travel)]
    for p in getattr(geometry,'geoms',[geometry]):
        if p.geom_type!='Polygon':raise ValueError('Polygonal envelopes required')
        for ring in [p.exterior,*p.interiors]:
            points=list(ring.coords)
            for a,b in zip(points,points[1:]):
                if a[1]==b[1]:continue
                strips.append(Polygon([a,b,(b[0]+travel,b[1]),(a[0]+travel,a[1])]))
    return unary_union(strips)


def audit_sweep(assemblies):
    keys={(s,k) for s in ['left','right'] for k in ['mx','choc_v1','deep_sea']}
    if set(assemblies)!=keys:raise ValueError('All six assembly/profile variants required')
    for key,rows in assemblies.items():
        if len(rows)!=len(REQUIRED_COMPONENTS) or {r.name for r in rows}!=REQUIRED_COMPONENTS:
            raise ValueError('Missing or duplicate component envelope')
        for r in rows:
            if r.geometry.is_empty or not r.geometry.is_valid or not math.isfinite(r.z0) or not math.isfinite(r.z1) or r.z0>=r.z1:
                raise ValueError('Invalid geometry/height envelope')
    errors=[];results={};cache={}
    for kind in ['mx','choc_v1','deep_sea']:
        pairs=[]
        for a in assemblies['left',kind]:
            key=a.geometry.wkb
            if key not in cache:cache[key]=horizontal_sweep(a.geometry)
            swept=cache[key]
            for b in assemblies['right',kind]:
                z0,z1=max(a.z0,b.z0),min(a.z1,b.z1)
                if z0>=z1:continue
                gap=swept.distance(b.geometry)
                bad_area=0.;exempt=False
                if gap<.3-1e-8:
                    # Circumscribed buffer prevents polygonal circle segments
                    # underestimating the required0.30mm Euclidean clearance.
                    bad=swept.intersection(b.geometry.buffer(.3/math.cos(math.pi/256),quad_segs=64))
                    if z1<=1.8 and a.name not in ('pcb','upper') and b.name not in ('pcb','upper'):
                        exempt=True;bad=bad.difference(CENTRAL_WORLD_ROI.buffer(-.3))
                    bad_area=bad.area
                    if bad_area>1e-8:errors.append(f'{kind}: {a.name}/{b.name} swept clearance')
                pairs.append(dict(left=a.name,right=b.name,z=[z0,z1],minimum_xy_gap_mm=gap,
                    outside_exception_clearance_violation_mm2=bad_area,central_exception_applied=exempt))
        results[kind]=pairs
    return dict(status='failed' if errors else 'pass',errors=errors,profiles=results,
                approach_world_x_mm=[-7.8,0.],minimum_clearance_mm=.3,
                physical_qualified=False,keycap_envelopes_verified=False,
                actual_CAD_verified=False,central_actual_audit_required=True,
                scope='Exact horizontal polygon sweep of conservative source geometry envelopes, not measured keycap/print fit')


def review_source_envelopes():
    import json
    from pathlib import Path
    from shapely import wkt
    from tools.generate_kc2_magnetic_housings import load_plans
    from tools.kc2_registered_native import digest,revalidate_job
    from tools.kc2_perimeter_wall import to_world
    from tools.kc2_registered_wall_plan import plan_registrars
    from shapely.geometry import GeometryCollection
    root=Path(__file__).resolve().parents[1];bindings={}
    def read(path):
        data=path.read_bytes();import hashlib
        bindings[path.relative_to(root).as_posix()]=hashlib.sha256(data).hexdigest()
        return json.loads(data)
    def bind_sources(record):
        for name,sha in record.get('source_sha256',{}).items():
            if digest(root/name)!=sha:raise ValueError('Changed source '+name)
            if name in bindings and bindings[name]!=sha:raise ValueError('Conflicting source '+name)
            bindings[name]=sha
    per=read(root/'.codex-tmp/perimeter-wall-plans.json');bind_sources(per)
    features=read(root/'.codex-tmp/registered-housing-fit/central/central-features.json');bind_sources(features)
    for name in ['kc2_joined_sweep.py','test_kc2_joined_sweep.py','generate_kc2_magnetic_housings.py',
                 'generate_kc2_x3_v2_housings.py','generate_kc2_housings.py','render_kc2_x3_joined.py',
                 'kc2_registered_wall_plan.py','kc2_perimeter_wall.py']:
        bindings['tools/'+name]=digest(root/'tools'/name)
    for side in ['left','right']:
        name=f'hardware/PCB/kc2_{side}/kc2_{side}.kicad_pcb';bindings[name]=digest(root/name)
    print('load source PCB outlines',flush=True);plans,_,transform=load_plans()
    if abs(transform['dx']-124.625)>1e-8 or abs(transform['dy'])>1e-8:raise ValueError('Joined pose changed')
    assemblies={}
    for side,p in plans.items():
        old=read(root/f'docs/reports/reinforced-covers-20260913/{side}-lower.json')
        mx=read(root/f'docs/reports/solid-filled-plates-20260913/{side}-mx.json')
        gs={k:wkt.loads(v) for k,v in mx['plan_wkt'].items()}
        common=None
        for z in [4.5,5.0,5.15,5.8,6.2]:
            section=unary_union([wkt.loads(l['wkt']) for part in mx['parts'] for l in part['layers'] if l['z0']<=z<l['z1']])
            common=section if common is None else common.intersection(section)
        regs=plan_registrars(side=side,kind='mx',board=p['board'],lower_floor=p['housing_outline'],upper_solid=common,
            lower_protected=p['all_component_cutouts'],upper_protected=unary_union([gs[k] for k in ['body','openings','service','bores','pockets','bosses']]),
            central_exclusion=box(-10,28,20,140) if side=='left' else box(145,28,175,140),split_exclusion=GeometryCollection())
        t=lambda g:to_world(g,p['raw_bounds'],side)
        registrar_floor=unary_union([r.floor_addition for r in regs.values()])
        registrar_wall=unary_union([r.wall for r in regs.values()])
        additions=unary_union([r.addition for r in regs.values()])
        feature_boxes=unary_union([box(r['bounds_mm'][0],r['bounds_mm'][1],r['bounds_mm'][3],r['bounds_mm'][4])
            for r in features['features'] if r['name'].startswith(side+'-')])
        q=per['sides'][side];wall_top=max(b[1] for b in q['bands'])
        if wall_top!=4.1:raise ValueError('Final ordinary wall top must be4.10')
        base=[Envelope('pcb',t(p['board']),2.5,4.1),Envelope('old_lower',t(wkt.loads(old['new_outline_wkt'])),-2.2,2.5),
            Envelope('perimeter_floor',t(wkt.loads(q['floor_addition_wkt'])),-2.2,-1.),
            Envelope('perimeter_wall',t(wkt.loads(q['wall_wkt'])),-1.,4.1),
            Envelope('registrar_floor',t(registrar_floor),-2.2,-1.),Envelope('registrar_wall',t(registrar_wall),-1.,5.),
            Envelope('central',t(feature_boxes),-2.2,1.5)]
        for kind in ['mx','choc_v1','deep_sea']:
            d=read(root/f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json')
            assemblies[side,kind]=base+[Envelope('upper',t(wkt.loads(d['plan_wkt']['domain']).union(additions)),4.1,d['profile']['boss_top'])]
    print('exact full outline approach sweep',flush=True);result=audit_sweep(assemblies)
    revalidate_job(root,dict(source_sha256=bindings));result['source_sha256']=bindings
    result['normal_and_magnetic_scope']='Common conservative outer envelopes; magnet void removal cannot enlarge occupied material'
    result['limitations']=['Source-plan envelopes, not final actual STL proof','Central contact/elastic geometry excluded only within independently audited lower ROI',
        'Selected physical keycap underside and full travel unknown','Does not validate occupied parts outside supplied PCB/component envelopes']
    path=root/'.codex-tmp/registered-housing-fit/joined-sweep-plan-review.json'
    path.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['errors'],flush=True);return result


if __name__=='__main__':raise SystemExit(bool(review_source_envelopes()['errors']))
