"""CON-ARCH-006 actual lower inclusion and retained void audit, not print force.

Separately executed reviewer. It shares declared perimeter and registrar plans,
therefore does not independently establish those plans' design correctness.
"""
import argparse,json,hashlib
from pathlib import Path
from shapely import wkt
from shapely.ops import unary_union
from tools.review_kc2_local_covers import prism,cut_union
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_inclusion(shape,required):return cut_union(required,shape).Volume()
def check_void(shape,void):return sum(s.intersect(v).Volume() for s in shape.Solids() for v in void.Solids())

def review(side,native=False):
    if side!='left':raise ValueError('Only complete left revision supported')
    import cadquery as cq
    reports={};paths=[];shapes={};baselines={};rows={};frozen={}
    def freeze():
        for p in paths:
            key=p.relative_to(ROOT).as_posix();sha=digest(p)
            if key in frozen and frozen[key]!=sha:raise ValueError('Review source changed '+key)
            frozen[key]=sha
    perimeter=ROOT/'.codex-tmp/perimeter-wall-plans.json';paths.append(perimeter)
    per=json.loads(perimeter.read_text())['sides'][side]
    oldpath=ROOT/f'docs/reports/reinforced-covers-20260913/{side}-lower.json';paths.append(oldpath)
    old=json.loads(oldpath.read_text());protected=prism(wkt.loads(old['clearance_wkt']),-1,2.5)
    upperold=ROOT/f'docs/reports/solid-filled-plates-20260913/{side}-mx.json';paths.append(upperold)
    centers=json.loads(upperold.read_text())['mounting_centers']
    pilots=cq.Compound.makeCompound([cq.Solid.makeCylinder(.55,2.8,cq.Vector(x,y,-.3),cq.Vector(0,0,1)) for x,y in centers])
    paths.extend([Path(__file__),ROOT/'tools/test_review_kc2_registered_lower.py',ROOT/'tools/review_kc2_local_covers.py'])
    if native:paths.extend([ROOT/'tools/kc2_lower_native_identity.py',ROOT/'tools/test_kc2_lower_native_identity.py'])
    for variant in ('normal','magnetic'):
        folder=ROOT/'.codex-tmp/registered-housing-fit/lower'/f'{side}-{variant}'
        reportpath=folder/'generation.json';record=json.loads(reportpath.read_text());paths.append(reportpath)
        if record['status']!='generated_pending_independent_review':raise ValueError('Incomplete generation')
        for path,sha in record['source_sha256'].items():
            p=ROOT/path
            if digest(p)!=sha:raise ValueError('Stale producer source '+path)
            paths.append(p)
        name=f'kc2_{side}_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step'
        actual=folder/name;baseline=ROOT/'hardware/MODELS'/name
        if digest(actual)!=record['outputs'][name]:raise ValueError('Actual STEP hash mismatch')
        if native:
            from tools.kc2_lower_native_identity import native_output
            nativepath=folder/'native-generation.json';nr=json.loads(nativepath.read_text())
            row=native_output(nr,side,variant,digest(reportpath),digest(actual))
            paths.extend([actual,nativepath])
            for path,sha in nr['source_sha256'].items():
                p=ROOT/path
                if digest(p)!=sha:raise ValueError('Stale native source '+path)
                paths.append(p)
            for field in ('readback','f3d'):
                p=folder/row['readback_step' if field=='readback' else 'f3d']
                if digest(p)!=row[field+'_sha256']:raise ValueError('Changed native '+field)
                paths.append(p)
            actual=folder/row['readback_step']
        paths.extend([actual,baseline])
        paths.append(folder/'registrar-snapshot.json');freeze()
        print('import actual/baseline',variant,flush=True)
        shapes[variant]=cq.importers.importStep(str(actual)).val();baselines[variant]=cq.importers.importStep(str(baseline)).val()
        regs=json.loads((folder/'registrar-snapshot.json').read_text())['registrars']
        required=[prism(wkt.loads(per['wall_wkt']),-1,per['bands'][-1][-1]),prism(wkt.loads(per['floor_addition_wkt']),-2.2,-1)]
        for r in regs.values():required.extend([prism(wkt.loads(r['wall']),-1,5),prism(wkt.loads(r['floor_addition']),-2.2,-1)])
        ordinary=wkt.loads(per['wall_wkt']).difference(unary_union([wkt.loads(r['wall']) for r in regs.values()]))
        upper_gap=prism(ordinary,4.10001,4.4)
        print('actual protected voids and complete wall inclusion',variant,flush=True)
        s=shapes[variant]
        rows[variant]=dict(component_obstruction_mm3=check_void(s,protected),pilot_obstruction_mm3=check_void(s,pilots),
            required_missing_mm3=sum(check_inclusion(s,r) for r in required),
            ordinary_wall_upper_gap_obstruction_mm3=check_void(s,upper_gap),
            canonical_baseline_removed_mm3=check_inclusion(s,baselines[variant]))
    print('actual original magnet void comparison',flush=True)
    original=cut_union(baselines['normal'],baselines['magnetic']);revised=cut_union(shapes['normal'],shapes['magnetic'])
    magnet=dict(original_mm3=original.Volume(),revised_mm3=revised.Volume(),missing_mm3=cut_union(original,revised).Volume(),
        extra_mm3=cut_union(revised,original).Volume(),blocked_mm3=check_void(shapes['magnetic'],original))
    errors=[f'{variant}: {key}' for variant,row in rows.items() for key,value in row.items() if value>.002]
    errors += [f'magnet {key}' for key in ('missing_mm3','extra_mm3','blocked_mm3') if magnet[key]>.002]
    freeze()
    report=dict(requirements=['CON-ARCH-006'],status='fail' if errors else 'pass',errors=errors,
        side=side,native_readback=native,variants=rows,magnet=magnet,physical_qualified=False,
        scope='Actual original component/pilot/magnet voids and complete declared wall/registrar inclusion; full assembly and fit-force separate',
        source_sha256=frozen)
    output=ROOT/'.codex-tmp/registered-housing-fit/lower'/(side+('-native' if native else '')+'-void-review.json')
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'}),flush=True)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('side');p.add_argument('--native',action='store_true');args=p.parse_args();raise SystemExit(bool(review(args.side,args.native)['errors']))
