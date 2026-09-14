"""CON-ARCH-006 additive lower CAD integration; never writes canonical models.

Only the left complete housing is supported until the separate right A/B
relief is integrated. Producer checks are not independent acceptance evidence.
"""
from pathlib import Path
import argparse,hashlib,json
from shapely import wkt
from tools.kc2_central_flexure import prism,place_feature_solids

ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stage_path(side,magnetic):
    if side not in ('left','right') or type(magnetic) is not bool:raise ValueError('Invalid identity')
    return ROOT/'.codex-tmp/registered-housing-fit/lower'/(side+('-magnetic' if magnetic else '-normal'))

def compose_lower(baseline,additions):
    final=baseline.fuse(*[s for a in additions for s in a.Solids()]).clean()
    if not final.isValid() or len(final.Solids())!=1:raise ValueError('Invalid/disconnected lower')
    return final

def audit_additive(baseline,final,additions):
    errors=[]
    removed=baseline.cut(final).Volume()
    remainder=final.cut(baseline)
    if additions and remainder.Volume()>1e-8:
        remainder=remainder.cut(*[s for a in additions for s in a.Solids()])
    unexpected=remainder.Volume()
    if removed>.002:errors.append('Baseline material lost')
    if unexpected>.002:errors.append('Unplanned material added')
    if not final.isValid() or len(final.Solids())!=1:errors.append('Invalid/disconnected final')
    return dict(errors=errors,removed_baseline_mm3=removed,unplanned_added_mm3=unexpected)

def generate(side,magnetic=False):
    if side!='left':raise ValueError('Right A/B relief integration is not implemented')
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import inspect_mesh,bounds
    folder=stage_path(side,magnetic);folder.mkdir(parents=True,exist_ok=True)
    stem=f'kc2_{side}_lower_housing'+('_magnetic' if magnetic else '')
    basepath=ROOT/'hardware/MODELS'/(stem+'.step')
    perimeterpath=ROOT/'.codex-tmp/perimeter-wall-plans.json'
    registrarpath=ROOT/f'.codex-tmp/registered-housing-fit/upper/{side}-deep_sea/generation.json'
    oldpath=ROOT/f'docs/reports/reinforced-covers-20260913/{side}-lower.json'
    pp=json.loads(perimeterpath.read_text());upper_observed=json.loads(registrarpath.read_text());registrars=upper_observed['registrars']
    if upper_observed['side']!=side or upper_observed['kind']!='deep_sea' or len(registrars)!=3:
        raise ValueError('Registrar snapshot identity mismatch')
    # The upper producer updates its report while building. Snapshot only the
    # planned registrar geometry and bind all immutable sources, not live status.
    snapshot=folder/'registrar-snapshot.json'
    snapshot.write_text(json.dumps(dict(side=side,registrars=registrars,
        source_sha256=upper_observed['source_sha256'],scope='Registrar plan snapshot; no upper completion claim'),indent=2)+'\n')
    sources=[Path(__file__),ROOT/'tools/test_stage_kc2_registered_lower.py',basepath,perimeterpath,snapshot,oldpath]
    for path,sha in upper_observed['source_sha256'].items():
        p=ROOT/path
        if digest(p)!=sha:raise ValueError('Stale registrar source '+path)
        sources.append(p)
    sources += [ROOT/'tools'/n for n in ['kc2_central_flexure.py','kc2_central_fit.py','kc2_perimeter_wall.py',
        'kc2_registered_wall_plan.py','generate_kc2_magnetic_housings.py']]
    for path,sha in pp['source_sha256'].items():
        p=ROOT/path
        if digest(p)!=sha:raise ValueError('Stale perimeter source '+path)
        sources.append(p)
    before={p.relative_to(ROOT).as_posix():digest(p) for p in sources}
    row=pp['sides'][side];wall=wkt.loads(row['wall_wkt']);floor=wkt.loads(row['floor_addition_wkt'])
    protected=wkt.loads(json.loads(oldpath.read_text())['clearance_wkt'])
    print('build additions',stem,flush=True)
    additions=[prism(wall,-1,4.35),prism(floor,-2.2,-1)]
    for r in registrars.values():
        additions.extend([prism(wkt.loads(r['wall']),-1,5),prism(wkt.loads(r['floor_addition']),-2.2,-1)])
    additions+=place_feature_solids(side,protected)
    print('import baseline',flush=True)
    baseline=cq.importers.importStep(str(basepath)).val()
    print('fuse complete lower',flush=True);final=compose_lower(baseline,additions)
    print('audit additive preservation',flush=True);audit=audit_additive(baseline,final,additions)
    if audit['errors']:raise ValueError(audit)
    report=dict(requirements=['CON-ARCH-006'],side=side,magnetic=magnetic,
        status='building',physical_qualified=False,canonical_changed=False,source_sha256=before,
        preservation=audit,body_count=len(final.Solids()),bounds_mm=bounds(final),volume_mm3=final.Volume(),outputs={})
    step=folder/(stem+'.step');stl=folder/(stem+'.stl')
    print('export STEP/STL',flush=True)
    cq.exporters.export(final,str(step));cq.exporters.export(final,str(stl),tolerance=.005,angularTolerance=.08)
    report['mesh']=inspect_mesh(stl,final)
    reopened=cq.importers.importStep(str(step)).val()
    if not reopened.isValid() or len(reopened.Solids())!=1 or abs(reopened.Volume()-final.Volume())>.01:
        raise ValueError('STEP round trip failed')
    if before!={p.relative_to(ROOT).as_posix():digest(p) for p in sources}:raise ValueError('Sources changed during generation')
    report['outputs']={p.name:digest(p) for p in (step,stl)}
    report['status']='generated_pending_independent_review'
    (folder/'generation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('side');parser.add_argument('--magnetic',action='store_true')
    args=parser.parse_args();generate(args.side,args.magnetic)
