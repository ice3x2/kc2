"""CON-ARCH-006 restore continuous existing wall/floor at obsolete guide windows.

Only missing stock inside the original perimeter is added. Canonical publication
is separate from staged geometry generation and actual-output verification.
"""
from pathlib import Path
import argparse
import json
import cadquery as cq
from shapely import wkt
from shapely.geometry import box
from tools.kc2_central_flexure import prism
from tools.stage_kc2_flat_central_revision import digest, _export_mesh
from tools.review_kc2_flat_central_native import _signature
from tools.kc2_flat_central_native import compare_cad_signatures

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / '.codex-tmp/smooth-central-seam'
PARENT = ROOT / 'hardware/MODELS/kc2_flat_central_housing_manifest.json'
PERIMETER = ROOT / 'docs/reports/registered-housing-fit-20260913/evidence/perimeter-wall-plans.json'
TOL = .002


def box_solid(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0,y0,z0))


def patches(side):
    if side not in ('left', 'right'): raise ValueError('Unknown side')
    outer, inner, floor_inner = (-1.5, -.3, 1.7) if side == 'left' else (150.9,149.7,147.7)
    result = []
    for y in (95.,117.):
        # 6.2 mm spans the old 5.7 mm clearance window and joins existing stock.
        result.append(box_solid(min(outer,inner), max(outer,inner), y-3.1,y+3.1,-2.2,4.1))
        result.append(box_solid(min(outer,floor_inner), max(outer,floor_inner), y-3.1,y+3.1,-2.2,-1))
    return result


def smooth(shape, required):
    result = shape.fuse(*required).clean()
    if not result.isValid() or len(result.Solids()) != len(shape.Solids()):
        raise ValueError('Repair disconnected housing')
    return result


def audit(before, after, required):
    added = after.cut(before)
    values = dict(removed_material=before.cut(after).Volume(),
                  off_patch_addition=added.cut(*required).Volume() if added.Solids() else 0.,
                  unfilled_patch=sum(p.cut(after).Volume() for p in required))
    errors = [k for k,v in values.items() if v > TOL]
    if not after.isValid() or len(after.Solids()) != len(before.Solids()):
        errors.append('invalid_topology')
    return dict(errors=errors, added_mm3=added.Volume(), **values)


def generate(side):
    parent = json.loads(PARENT.read_text())
    per = json.loads(PERIMETER.read_text())['sides'][side]
    required = patches(side)
    # Reject a patch extending beyond the previously approved wall or floor.
    wall = wkt.loads(per['wall_wkt']); floor = wkt.loads(per['floor_addition_wkt'])
    old = ROOT / f'docs/reports/reinforced-covers-20260913/{side}-lower.json'
    protected = prism(wkt.loads(json.loads(old.read_text())['clearance_wkt']), -1,2.5)
    inner = prism(wkt.loads(per['inner_wkt']), 2.5,4.1)
    for i,p in enumerate(required):
        b = p.BoundingBox(); plan = box(b.xmin,b.ymin,b.xmax,b.ymax)
        if plan.difference(wall if i%2 == 0 else floor).area > 1e-7:
            raise ValueError('Patch widens original perimeter')
        if p.intersect(protected).Volume() > TOL or p.intersect(inner).Volume() > TOL:
            raise ValueError('Patch obstructs protected component/PCB envelope')
    output = {}
    for kind in ('normal','magnetic'):
        label = side+':'+kind
        stem = f'kc2_{side}_lower_housing'+('_magnetic' if kind=='magnetic' else '')
        source = ROOT/'hardware/MODELS'/(stem+'.step')
        if digest(source) != parent['outputs'][source.relative_to(ROOT).as_posix()]:
            raise ValueError('Input differs from current reviewed publication')
        print('import', label, flush=True)
        before = cq.importers.importStep(str(source)).val()
        folder = STAGE/'lower'/(side+'-'+kind); folder.mkdir(parents=True,exist_ok=True)
        print('fill former guide cavities', label, flush=True)
        after = smooth(before,required)
        print('audit material changes', label, flush=True)
        proof = audit(before,after,required)
        if proof['errors']: raise ValueError(proof)
        step = folder/(stem+'.step'); cq.exporters.export(after,str(step))
        actual = cq.importers.importStep(str(step)).val()
        errors = compare_cad_signatures(_signature(after),_signature(actual))
        if errors: raise ValueError(errors)
        print('verify continuous wall on reopened STEP', label, flush=True)
        missing = sum(p.cut(actual).Volume() for p in required)
        if missing > TOL: raise ValueError('Export lost smooth wall')
        names = [stem+'.stl'] if side=='left' else [
            f'kc2_right_lower_housing_part_{part}'+('_magnetic' if kind=='magnetic' else '')+'.stl' for part in ('a','b')]
        meshes=[];outputs={step.name:digest(step)}
        solids = sorted(actual.Solids(),key=lambda s:s.Center().x)
        for name,solid in zip(names,solids):
            path=folder/name; mesh,filtered=_export_mesh(solid,path)
            meshes.append(dict(mesh=mesh,filter=filtered));outputs[name]=digest(path)
        gap=None
        if side=='right':
            # Only the facing A/B strip can contain the minimum distance.
            # Outside it, X separation alone is >=1 mm. Avoid comparing every
            # unrelated socket face with every other face in the entire case.
            a,b=solids; ba,bb=a.BoundingBox(),b.BoundingBox()
            region=box_solid(bb.xmin-1,ba.xmax+1,-5,140,-3,6)
            gap=a.intersect(region).distance(b.intersect(region))
            if gap>=1: raise ValueError('Local A/B distance cannot bound the full minimum')
        if gap is not None and gap < .39999: raise ValueError('A/B clearance reduced')
        row=dict(status='generated_pending_independent_review',errors=[],body_count=len(solids),
            side=side,magnetic=kind=='magnetic',preservation=proof,outputs=outputs,meshes=meshes,
            reopened_wall_missing_mm3=missing,actual_ab_gap_mm=gap,
            source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in
                (source,PARENT,PERIMETER,old,Path(__file__),ROOT/'tools/test_kc2_smooth_central_seam.py')},
            signature=_signature(actual),physical_qualified=False)
        (folder/'generation.json').write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8')
        output[label]=row
        print('pass',label,proof,flush=True)
    (STAGE/(side+'-generation.json')).write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('side',choices=['left','right'])
    generate(parser.parse_args().side)
