"""CON-ARCH-006 actual STL -> height-aware conservative envelope bridge.

No mesh union is required: clip triangles at each Z band and test projected
polygons individually. Degenerate vertical projections are omitted only after
mesh closure/positive-volume validation in the caller. Do not run until all
ten jobs and their independent source/native audits are complete.
"""
from pathlib import Path
import json,math
import numpy as np
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from tools.review_kc2_registered_assembly import qualify_void,void_path

ROOT=Path(__file__).resolve().parents[1]
TOLERANCE=.005


def inventory_gate(counts):
    expected={f'{f}:{s}:{k}':1 if s=='left' else 2 for f,ks in [('upper',['mx','choc_v1','deep_sea']),('lower',['normal','magnetic'])] for s in ['left','right'] for k in ks}
    if counts!=expected or sum(counts.values())!=15:raise ValueError('Ten jobs/fifteen actual STLs required')


def evidence_gate(report,required):
    if report.get('status')!='pass' or report.get('errors'):raise ValueError('Independent evidence not passing')
    if any(report.get('source_sha256',{}).get(k)!=v for k,v in required.items()):
        raise ValueError('Independent evidence does not bind required current artifacts')


def clip_triangle_z(triangle,z0,z1):
    points=[np.asarray(p,float) for p in triangle]
    for level,lower in [(z0,True),(z1,False)]:
        output=[]
        if not points:break
        for a,b in zip(points,points[1:]+points[:1]):
            ia=a[2]>=level if lower else a[2]<=level
            ib=b[2]>=level if lower else b[2]<=level
            if ia:output.append(a)
            if ia!=ib:output.append(a+(b-a)*((level-a[2])/(b[2]-a[2])))
        points=output
    return points


def audit_triangles(triangles,bands):
    if not bands or any(z0>=z1 or g.is_empty or not g.is_valid for z0,z1,g in bands):raise ValueError('Invalid allowed bands')
    expanded=[(z0,z1,g.buffer(TOLERANCE)) for z0,z1,g in bands]
    errors=[];outside=0.;count=0;bad=0
    for triangle in np.asarray(triangles):
        if triangle.shape!=(3,3) or not np.isfinite(triangle).all():raise ValueError('Invalid actual triangle')
        count+=1;lo,hi=float(triangle[:,2].min()),float(triangle[:,2].max())
        if lo<min(z0 for z0,_,_ in bands)-1e-5 or hi>max(z1 for _,z1,_ in bands)+1e-5:
            errors.append('actual mesh outside envelope Z');bad+=1;continue
        checks=[]
        if hi-lo<1e-5:
            allowed=unary_union([g for z0,z1,g in expanded if z0-1e-5<=lo<=z1+1e-5])
            checks.append((triangle,allowed))
        else:
            covered=[]
            for z0,z1,g in expanded:
                if min(hi,z1)-max(lo,z0)<=1e-9:continue
                covered.append((max(lo,z0),min(hi,z1)))
                checks.append((clip_triangle_z(triangle,z0,z1),g))
            cursor=lo
            for a,b in sorted(covered):
                if a>cursor+1e-5:errors.append('uncovered interior Z interval')
                cursor=max(cursor,b)
            if cursor<hi-1e-5:errors.append('uncovered interior Z interval')
        for points,allowed in checks:
            if len(points)<3:continue
            p=Polygon(np.asarray(points)[:,:2])
            if p.area<1e-12:continue
            if not p.is_valid:raise ValueError('Invalid projected triangle')
            if not allowed.covers(p):
                area=p.difference(allowed).area
                if area>1e-9:outside+=area;bad+=1
    if bad:errors.append('actual triangle outside height-aware envelope')
    return dict(status='failed' if errors else 'pass',errors=sorted(set(errors)),triangles=count,
                outside_projection_area_sum_mm2=outside,outside_triangle_count=bad,envelope_allowance_mm=TOLERANCE)


def source_bands(side,family,kind,read):
    """Reconstruct the exact broad envelopes used by the source sweep report."""
    from shapely import wkt
    per=read(ROOT/'.codex-tmp/perimeter-wall-plans.json')['sides'][side]
    old=read(ROOT/f'docs/reports/reinforced-covers-20260913/{side}-lower.json')
    coords=([(30,-1.5,36,-.3),(48,-1.5,54,-.3),(16.9,10,18.1,16)] if side=='left' else
        [(110,-1.5,116,-.3),(128,-1.5,134,-.3),(140.5875,10,141.7875,16)])
    walls=unary_union([box(*b) for b in coords]);patches=[]
    for i,(x0,y0,x1,y1) in enumerate(coords):
        patches.append(box(x0-1.45,y0,x1+1.45,y1+1.45) if i<2 else
            box(x0,y0-1.45,x1+1.45,y1+1.45) if side=='left' else box(x0-1.45,y0-1.45,x1,y1+1.45))
    patches=unary_union(patches)
    if family=='upper':
        d=read(ROOT/f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json')
        return [(4.1,d['profile']['boss_top'],wkt.loads(d['plan_wkt']['domain']).union(patches))]
    features=read(ROOT/'.codex-tmp/registered-housing-fit/central/central-features.json')
    central=unary_union([box(r['bounds_mm'][0],r['bounds_mm'][1],r['bounds_mm'][3],r['bounds_mm'][4]) for r in features['features'] if r['name'].startswith(side+'-')])
    baseline=wkt.loads(old['new_outline_wkt']);wall=wkt.loads(per['wall_wkt']);floor=wkt.loads(per['floor_addition_wkt'])
    if max(b[1] for b in per['bands'])!=4.1:raise ValueError('Wrong final wall height')
    return [(-2.2,-1,unary_union([baseline,floor,patches,central])),
        (-1,1.5,unary_union([baseline,wall,walls,central])),
        (1.5,1.8,unary_union([baseline,wall,walls])),(1.8,2.5,unary_union([baseline,wall,walls])),
        (2.5,4.1,wall.union(walls)),(4.1,5.,walls)]


def expanded_sweep(bandsets,boards,rawbounds):
    from tools.kc2_joined_sweep import horizontal_sweep,CENTRAL_WORLD_ROI
    from tools.kc2_perimeter_wall import to_world
    rows=[];errors=[]
    for kind in ['mx','choc_v1','deep_sea']:
        sides={}
        for side in ['left','right']:
            normal=bandsets[f'lower:{side}:normal'];magnetic=bandsets[f'lower:{side}:magnetic']
            if any(a!=x or b!=y or g.symmetric_difference(h).area>1e-8 for (a,b,g),(x,y,h) in zip(normal,magnetic)):
                raise ValueError('Normal/magnetic envelope disagreement')
            sides[side]=[(a,b,to_world(g.buffer(TOLERANCE),rawbounds[side],side)) for a,b,g in normal+bandsets[f'upper:{side}:{kind}']]
            sides[side].append((2.5,4.1,to_world(boards[side],rawbounds[side],side)))
        levels=sorted({z for s in sides.values() for a,b,g in s for z in [a,b]})
        for a,b in zip(levels,levels[1:]):
            mid=(a+b)/2
            geoms={s:unary_union([g for lo,hi,g in rows if lo<mid<hi]) for s,rows in sides.items()}
            if any(g.is_empty for g in geoms.values()):continue
            swept=horizontal_sweep(geoms['left']);gap=swept.distance(geoms['right'])
            bad=swept.intersection(geoms['right'].buffer(.3/math.cos(math.pi/256),quad_segs=64))
            if b<=1.8:bad=bad.difference(CENTRAL_WORLD_ROI.buffer(-.3))
            if bad.area>1e-8:errors.append(f'{kind} Z{a}..{b}: expanded-envelope swept clearance')
            rows.append(dict(kind=kind,z=[a,b],minimum_gap_mm=gap,outside_central_clearance_violation_mm2=bad.area))
    return dict(errors=errors,rows=rows)


def review():
    import trimesh
    from tools.kc2_registered_native import digest,preflight_job,revalidate_job
    from tools.generate_kc2_magnetic_housings import load_plans
    bindings={}
    def read(path):
        data=path.read_bytes();import hashlib
        key=path.relative_to(ROOT).as_posix();sha=hashlib.sha256(data).hexdigest()
        if key in bindings and bindings[key]!=sha:raise ValueError('Changed input')
        bindings[key]=sha;return json.loads(data)
    def verify_bindings(d):
        revalidate_job(ROOT,d)
        for k,v in d['source_sha256'].items():
            if k in bindings and bindings[k]!=v:raise ValueError('Conflicting evidence')
            bindings[k]=v
    for p in [Path(__file__),ROOT/'tools/test_review_kc2_actual_envelopes.py',
              ROOT/'tools/review_kc2_registered_assembly.py',ROOT/'tools/test_review_kc2_registered_assembly.py']:
        bindings[p.relative_to(ROOT).as_posix()]=digest(p)
    plan=read(ROOT/'.codex-tmp/registered-housing-fit/joined-sweep-plan-review.json');evidence_gate(plan,{})
    verify_bindings(plan)
    central=read(ROOT/'.codex-tmp/registered-housing-fit/central/integrated-review.json');evidence_gate(central,{})
    verify_bindings(central)
    if set(central.get('rows',{}))!={'normal-y95','normal-y117','magnetic-y95','magnetic-y117'}:raise ValueError('Incomplete actual central audit')
    if any(r.get('status')!='pass' or r.get('errors') for r in central['rows'].values()):raise ValueError('Central sub-audit failed')
    labels=[f'{f}:{s}:{k}' for f,ks in [('upper',['mx','choc_v1','deep_sea']),('lower',['normal','magnetic'])] for s in ['left','right'] for k in ks]
    jobs={label:preflight_job(ROOT,label) for label in labels};counts={};bandsets={};rows={}
    # Complete every prerequisite before loading the first large mesh.
    for label,job in jobs.items():
        verify_bindings(job);folder=job['source'].parent;gen=read(job['record_path']);family,side,kind=label.split(':')
        names=[n for n in gen['outputs'] if n.endswith('.stl')];counts[label]=len(names)
        required={job['source'].relative_to(ROOT).as_posix():job['step_sha256'],job['record_path'].relative_to(ROOT).as_posix():job['record_sha256']}
        auditpath=folder/'brep-review.json' if family=='upper' else ROOT/void_path(side)
        if family=='lower':
            qualified,qualified_sources=qualify_void(side,lambda name:(ROOT/name).read_bytes())
            evidence_gate(qualified,required)
            verify_bindings(dict(source_sha256=qualified_sources))
        for path in [auditpath,folder/'native-review.json']:
            d=read(path);evidence_gate(d,required);verify_bindings(d)
            if path.name=='native-review.json' and (d.get('selected_job')!=label or d.get('independent_geometry_verified') is not True):
                raise ValueError('Native job identity/geometry qualification mismatch')
        if family=='upper':
            d=read(folder/'mesh-review.json');evidence_gate(d,{**required,**{(folder/n).relative_to(ROOT).as_posix():gen['outputs'][n] for n in names}});verify_bindings(d)
        else:evidence_gate(central,required)
        bandsets[label]=source_bands(side,family,kind,read)
    inventory_gate(counts)
    for label,job in jobs.items():
        gen=read(job['record_path']);rows[label]=[]
        for name in sorted(n for n in gen['outputs'] if n.endswith('.stl')):
            print('actual triangle envelope',label,name,flush=True)
            mesh=trimesh.load_mesh(job['source'].parent/name,process=True)
            if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume<=0 or len(mesh.split())!=1 or max(mesh.extents)>150.001:
                raise ValueError('Invalid actual printable mesh')
            r=audit_triangles(mesh.triangles,bandsets[label]);r['stl']=name;rows[label].append(r);del mesh
    plans,_,transform=load_plans()
    if abs(transform['dx']-124.625)>1e-8 or abs(transform['dy'])>1e-8:raise ValueError('Fixed joined transform changed')
    sweep=expanded_sweep(bandsets,{s:p['board'] for s,p in plans.items()},{s:p['raw_bounds'] for s,p in plans.items()})
    errors=[label+': '+e for label,rs in rows.items() for r in rs for e in r['errors']]+sweep['errors']
    revalidate_job(ROOT,dict(source_sha256=bindings))
    result=dict(status='failed' if errors else 'pass',errors=errors,requirements=['CON-ARCH-006'],jobs=rows,
        source_sha256=bindings,expanded_envelope_sweep=sweep,actual_envelope_verified=not errors,
        physical_qualified=False,keycap_envelopes_verified=False,central_contact_audited_separately=True)
    (ROOT/'.codex-tmp/registered-housing-fit/actual-envelope-review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':raise SystemExit(bool(review()['errors']))
