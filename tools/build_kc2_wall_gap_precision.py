"""CON-ARCH-006 bounded submicron rounding for lower slit CAD joins.

The original STL-based candidate remains immutable. Effective patch geometry
and its deviation are recorded explicitly, not hidden by changing tolerances.
"""
import copy
import json
import argparse
from pathlib import Path
from shapely import wkt,set_precision
from tools.kc2_wall_gap_fix import ROOT,STAGE,write
from tools.kc2_pcb_seating import digest

def stable_patch(p):
    q=set_precision(p,.0001)
    error=p.hausdorff_distance(q)
    changed=p.symmetric_difference(q).area
    if q.is_empty or not q.is_valid or error>.00008 or changed>.05:
        raise ValueError('Precision cleanup changes more than submicron boundary rounding')
    return q,dict(grid_mm=.0001,hausdorff_mm=error,changed_area_mm2=changed)

def build(label):
    import cadquery as cq
    from tools.kc2_central_flexure import prism
    from tools.stage_kc2_registered_lower import audit_additive
    from tools.kc2_step_whitespace import normalize
    plan=json.loads((STAGE/'plan.json').read_text())
    if label not in ('right:normal','right:magnetic'):
        raise ValueError('Recovery is scoped to the observed right lower split-end precision issue')
    for name,sha in plan['source_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed source '+name)
    job=plan['jobs'][label];parts=copy.deepcopy(job['parts'])
    for part in parts:
        for patch in part['patches']:
            shape,proof=stable_patch(wkt.loads(patch['wkt']))
            patch.update(wkt=shape.wkt,precision=proof)
    folder=STAGE/label.replace(':','-');folder.mkdir(parents=True,exist_ok=True)
    print('import rounded patch build',label,flush=True)
    baseline=sorted(cq.importers.importStep(str(ROOT/'hardware/MODELS'/(job['stem']+'.step'))).solids().vals(),key=lambda s:s.Center().x)
    result=[];proofs=[]
    for i,(base,part) in enumerate(zip(baseline,parts)):
        additions=[prism(wkt.loads(p['wkt']),p['z0'],p['z1']) for p in part['patches']]
        solids=[s for a in additions for s in a.Solids()]
        print('fuse rounded patches',label,i,flush=True)
        final=base.fuse(*solids).clean()
        proof=audit_additive(base,final,additions)
        proof['missing_patch_mm3']=sum(abs(a.cut(final).Volume()) for a in additions)
        print('rounded patch proof',label,i,proof,flush=True)
        if proof['errors'] or proof['missing_patch_mm3']>.002:raise ValueError(proof)
        proof.update(base_volume_mm3=base.Volume(),final_volume_mm3=final.Volume())
        result.append(final);proofs.append(proof)
    target=folder/(job['stem']+'.step')
    cq.exporters.export(cq.Compound.makeCompound(result),str(target))
    target.write_bytes(normalize(target.read_bytes())[0])
    actual=cq.importers.importStep(str(target)).val()
    if not actual.isValid() or len(actual.Solids())!=len(parts) or abs(actual.Volume()-sum(s.Volume() for s in result))>.02:
        raise ValueError('Rounded STEP round trip failed')
    sources={**plan['source_sha256'],Path(__file__).relative_to(ROOT).as_posix():digest(Path(__file__)),
             'tools/test_kc2_wall_gap_precision.py':digest(ROOT/'tools/test_kc2_wall_gap_precision.py')}
    write(folder/'generation.json',dict(status='cad_generated',label=label,parts=proofs,effective_parts=parts,
        step=target.name,step_sha256=digest(target),plan_sha256=digest(STAGE/'plan.json'),source_sha256=sources,
        precision_reason='STL float32 boundary rounding at right split-end slits destabilized exact coplanar Boolean union'))
    print('done rounded build',label,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('label');build(parser.parse_args().label)
