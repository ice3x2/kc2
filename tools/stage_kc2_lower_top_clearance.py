"""CON-ARCH-006 traceable left lower4.35→4.10 top-only refinement.

Preserves earlier development STEP/report in ignored lower-development before
replacing ignored final stage. Existing canonical hardware is never modified.
Earlier report is provenance, not current-source verification after this change.
"""
from pathlib import Path
import json,hashlib,argparse,shutil
from shapely import wkt
from shapely.ops import unary_union
from tools.kc2_central_flexure import prism
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lower_top(shape,wall,registrars):
    from shapely.geometry import box
    bounds=shape.BoundingBox()
    # Clipping by one plane avoids coincident multi-ring side faces in the
    # imported perimeter. Restore the exact unchanged registrar tips afterward;
    # the actual net-delta audit still limits removal to ordinary top material.
    clip=prism(box(bounds.xmin-1,bounds.ymin-1,bounds.xmax+1,bounds.ymax+1),4.1,bounds.zmax+1)
    base=shape.cut(clip).clean()
    final=base.fuse(*prism(registrars,4.1,5).Solids()).clean()
    if not final.isValid() or len(final.Solids())!=1:raise ValueError('Top relief invalid')
    return final
def generate(magnetic=False):
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import inspect_mesh,bounds
    variant='magnetic' if magnetic else 'normal'
    folder=ROOT/'.codex-tmp/registered-housing-fit/lower'/f'left-{variant}'
    dev=ROOT/'.codex-tmp/registered-housing-fit/lower-development'/f'left-{variant}'
    dev.mkdir(parents=True,exist_ok=True)
    stem='kc2_left_lower_housing'+('_magnetic' if magnetic else '')
    for name in ['generation.json','registrar-snapshot.json',stem+'.step']:
        target=dev/name
        if not target.exists():shutil.copyfile(folder/name,target)
    oldpath=dev/'generation.json';old=json.loads(oldpath.read_text());source=dev/(stem+'.step')
    if old['status']!='generated_pending_independent_review' or digest(source)!=old['outputs'][source.name]:
        raise ValueError('Invalid cached development STEP')
    snapshot=dev/'registrar-snapshot.json';regs=json.loads(snapshot.read_text())['registrars']
    perpath=ROOT/'.codex-tmp/perimeter-wall-plans.json';per=json.loads(perpath.read_text())
    paths=[Path(__file__),ROOT/'tools/test_stage_kc2_lower_top_clearance.py',source,oldpath,snapshot,perpath,
        ROOT/'tools/kc2_central_flexure.py',ROOT/'tools/generate_kc2_magnetic_housings.py',ROOT/'hardware/MODELS'/(stem+'.step')]
    for path,sha in per['source_sha256'].items():
        p=ROOT/path
        if digest(p)!=sha:raise ValueError('Stale perimeter source '+path)
        paths.append(p)
    before={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    row=per['sides']['left']
    if row['bands'][-1][-1]!=4.1:raise ValueError('Wrong perimeter wall top')
    wall=wkt.loads(row['wall_wkt']);registrars=unary_union([wkt.loads(r['wall']) for r in regs.values()])
    print('import cached development lower',variant,flush=True);base=cq.importers.importStep(str(source)).val()
    print('cut ordinary wall top strip',flush=True);final=lower_top(base,wall,registrars)
    cutter=prism(wall.difference(registrars),4.1,4.35001)
    print('verify only specified top material removed',flush=True)
    removed=base.cut(final);added=final.cut(base).Volume();outside=removed.cut(*cutter.Solids()).Volume()
    remaining=final.intersect(cutter).Volume()
    if max(added,outside,remaining)>.002:raise ValueError('Unexpected top-cut delta')
    step=folder/(stem+'.step');stl=folder/(stem+'.stl')
    cq.exporters.export(final,str(step));cq.exporters.export(final,str(stl),tolerance=.005,angularTolerance=.08)
    reopened=cq.importers.importStep(str(step)).val()
    if not reopened.isValid() or len(reopened.Solids())!=1 or abs(reopened.Volume()-final.Volume())>.01:raise ValueError('STEP roundtrip')
    if before!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Changed source')
    report=dict(requirements=['CON-ARCH-006'],side='left',magnetic=magnetic,status='generated_pending_independent_review',
        body_count=1,physical_qualified=False,canonical_changed=False,source_sha256=before,
        development_provenance=oldpath.relative_to(ROOT).as_posix(),ordinary_wall_top_mm=4.1,registrar_top_mm=5.,
        top_delta=dict(removed_mm3=removed.Volume(),added_mm3=added,off_allowance_removed_mm3=outside,remaining_strip_mm3=remaining),
        outputs={p.name:digest(p) for p in (step,stl)},mesh=inspect_mesh(stl,final),bounds_mm=bounds(final),volume_mm3=final.Volume())
    (folder/'generation.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--magnetic',action='store_true');args=p.parse_args();generate(args.magnetic)
