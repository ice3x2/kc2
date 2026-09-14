"""CON-ARCH-006 actual lower A/B subtraction, independent staging only."""
import argparse
import json
from pathlib import Path
import cadquery as cq
from shapely import wkt
from tools.stage_kc2_ab_relief import ROOT,STAGE,digest,safe_stage,cut_pair


def lower_domains(report):
    outline=wkt.loads(report['new_outline_wkt'])
    parts=[outline.intersection(wkt.loads(mask)) for mask in report['masks_wkt']]
    if len(parts)!=2 or any(p.geom_type!='Polygon' or not p.is_valid for p in parts):
        raise ValueError('Invalid lower floor domains')
    return parts


def stage(magnetic=False):
    suffix='_magnetic' if magnetic else ''
    directory=safe_stage(STAGE/('lower'+suffix));directory.mkdir(parents=True,exist_ok=True)
    source=ROOT/f'hardware/MODELS/kc2_right_lower_housing{suffix}.step'
    report_path=ROOT/'docs/reports/reinforced-covers-20260913/right-lower.json'
    upper_path=ROOT/'docs/reports/solid-filled-plates-20260913/right-mx.json'
    paths=[source,report_path,upper_path,Path(__file__),ROOT/'tools/stage_kc2_ab_relief.py',
           ROOT/'tools/kc2_split_fit_relief.py',ROOT/'tools/test_stage_kc2_ab_lower.py']
    before={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    report=json.loads(report_path.read_text());upper=json.loads(upper_path.read_text())
    domains=lower_domains(report)
    print('import',source.name,flush=True)
    solids=cq.importers.importStep(str(source)).solids().vals()
    if len(solids)!=2:raise ValueError('Expected exactly two baseline solids')
    # Import body order matches published whole housing; bounds establish masks.
    if solids[0].BoundingBox().xmin>solids[1].BoundingBox().xmin:
        solids.reverse()
    revised,evidence=cut_pair(solids,domains,protected=wkt.loads(upper['plan_wkt']['bosses']))
    output=directory/source.name
    cq.exporters.export(cq.Compound.makeCompound(revised),str(output))
    readback=cq.importers.importStep(str(output)).solids().vals()
    if len(readback)!=2 or not all(s.isValid() for s in readback):raise ValueError('STEP readback invalid')
    if abs(sum(s.Volume() for s in revised)-sum(s.Volume() for s in readback))>.01:
        raise ValueError('STEP readback volume mismatch')
    outputs={output.name:digest(output)}
    import trimesh
    for index,solid in enumerate(revised):
        stl=directory/f'kc2_right_lower_housing_part_{chr(97+index)}{suffix}.stl'
        cq.exporters.export(solid,str(stl),tolerance=.005,angularTolerance=.08)
        mesh=trimesh.load_mesh(stl)
        if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split())!=1:
            raise ValueError('STL topology failed')
        if max(mesh.extents)>150.001:raise ValueError('Printer envelope exceeded')
        evidence['parts'][index]['mesh']=dict(watertight=True,components=1,extents_mm=mesh.extents.tolist(),volume_mm3=float(mesh.volume))
        outputs[stl.name]=digest(stl)
    if before!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Source changed')
    evidence.update(requirements=['CON-ARCH-006'],magnetic=magnetic,source_sha256=before,
        outputs=outputs,canonical_changed=False,native_verified=False,
        pending='Full support/root/clip/component and native audit required before publication')
    (directory/'ab-relief.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ['parts','source_sha256']}),flush=True)
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--magnetic',action='store_true')
    stage(parser.parse_args().magnetic)
