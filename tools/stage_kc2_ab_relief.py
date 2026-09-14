"""CON-ARCH-006 actual baseline A/B local subtraction; never publication.

Uses published full-domain masks without re-extracting PCB. No added material,
no moved coordinates, no claimed physical fit or complete housing approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cadquery as cq
from shapely import wkt
from shapely.geometry import GeometryCollection
from tools.kc2_split_fit_relief import plan_split_relief
from tools.generate_kc2_x3_v2_housings import _extrude_geometry

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/registered-housing-fit/ab'


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_stage(path):
    path=Path(path).resolve()
    if not path.is_relative_to(STAGE.resolve()):
        raise ValueError('Only ignored A/B staging paths permitted')
    return path


def cut_pair(solids,domains,*,protected=None):
    if len(solids)!=2 or len(domains)!=2:
        raise ValueError('Exactly two parts required')
    protected=GeometryCollection() if protected is None else protected
    z0=min(s.BoundingBox().zmin for s in solids)
    z1=max(s.BoundingBox().zmax for s in solids)
    plan=plan_split_relief(*domains,protected_a=protected,protected_b=protected,
                          target_gap=.4,entry_extra=0,z_min=z0,z_max=z1)
    revised=[]; rows=[]
    for index,(solid,cutter) in enumerate(zip(solids,[plan.core.cutter_a,plan.core.cutter_b])):
        print('actual cut',index,'cutter area',cutter.area,flush=True)
        if not solid.isValid() or len(solid.Solids())!=1:
            raise ValueError('Invalid baseline solid')
        tool=_extrude_geometry(cq,cutter,z1-z0+.2,z0-.1)
        changed=solid if tool is None else solid.cut(tool.val()).clean()
        if not changed.isValid() or len(changed.Solids())!=1:
            raise ValueError('Relief disconnected actual solid')
        added=changed.cut(solid).Volume()
        removed=solid.Volume()-changed.Volume()
        if added>1e-5 or removed < -1e-5:
            raise ValueError('Relief unexpectedly added material')
        rows.append(dict(index=index,before_volume_mm3=solid.Volume(),after_volume_mm3=changed.Volume(),
                         removed_mm3=removed,added_mm3=added,cutter_wkt=cutter.wkt))
        revised.append(changed)
    distance=revised[0].distance(revised[1])
    if distance<.39999:
        raise ValueError(f'Actual gap below target: {distance}')
    return revised,dict(status='actual_subtractive_stage_pass',physical_qualified=False,
        scope='Local A/B gap/topology/subtractive delta only; not full populated or root-strength approval',
        entry_extra_mm=0,entry_note='Core relief runs through first/last layer; extra stepped recess omitted to preserve roots',
        before_gap_mm=solids[0].distance(solids[1]),after_gap_mm=distance,
        target_gap_mm=.4,removed_volume_mm3=sum(r['removed_mm3'] for r in rows),parts=rows)


def stage(kind):
    if kind not in ['mx','choc_v1','deep_sea']:
        raise ValueError('Unsupported upper family')
    stage_dir=safe_stage(STAGE/kind);stage_dir.mkdir(parents=True,exist_ok=True)
    report_path=ROOT/f'docs/reports/solid-filled-plates-20260913/right-{kind}.json'
    source=ROOT/f'hardware/MODELS/kc2_right_{kind}_upper_housing.step'
    paths=[source,report_path,Path(__file__),ROOT/'tools/kc2_split_fit_relief.py',
           ROOT/'tools/test_stage_kc2_ab_relief.py']
    paths.extend(sorted((ROOT/'hardware/PCB').rglob('*.kicad_pcb')))
    before={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    report=json.loads(report_path.read_text())
    domain=wkt.loads(report['plan_wkt']['domain'])
    domains=[domain.intersection(wkt.loads(v)) for v in report['masks_wkt']]
    print('import',source.name,flush=True)
    solids=cq.importers.importStep(str(source)).solids().vals()
    # Published part order is A/B; verify spatial identity before cutting.
    if len(solids)!=2: raise ValueError('Unexpected baseline body count')
    for solid,part in zip(solids,report['parts']):
        if abs(solid.Volume()-part['volume_mm3'])>.01:
            raise ValueError('Baseline body identity/volume mismatch')
    revised,evidence=cut_pair(solids,domains,protected=wkt.loads(report['plan_wkt']['bosses']))
    step=stage_dir/source.name
    cq.exporters.export(cq.Compound.makeCompound(revised),str(step))
    readback=cq.importers.importStep(str(step)).solids().vals()
    if len(readback)!=2 or not all(s.isValid() for s in readback):
        raise ValueError('STEP readback invalid')
    if abs(sum(s.Volume() for s in readback)-sum(s.Volume() for s in revised))>.01:
        raise ValueError('STEP readback volume mismatch')
    import trimesh
    outputs={step.name:digest(step)}
    for index,solid in enumerate(revised):
        stl=stage_dir/(source.stem+'_part_'+chr(97+index)+'.stl')
        cq.exporters.export(solid,str(stl),tolerance=.005,angularTolerance=.08)
        mesh=trimesh.load_mesh(stl)
        if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split())!=1:
            raise ValueError('STL topology failed')
        if max(mesh.extents)>150.001: raise ValueError('Printer envelope exceeded')
        evidence['parts'][index]['mesh']=dict(watertight=True,components=1,extents_mm=mesh.extents.tolist(),volume_mm3=float(mesh.volume))
        outputs[stl.name]=digest(stl)
    after={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    if before!=after:raise ValueError('Source changed during stage')
    evidence.update(kind=kind,requirements=['CON-ARCH-006'],source_sha256=before,outputs=outputs,
                    canonical_changed=False,native_verified=False,protected_bosses=True)
    (stage_dir/'ab-relief.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ['parts','source_sha256']}),flush=True)
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['mx','choc_v1','deep_sea'])
    stage(parser.parse_args().kind)
