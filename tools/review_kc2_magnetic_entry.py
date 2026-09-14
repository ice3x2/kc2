"""CON-ARCH-006 actual outside-to-pocket access and blind back-wall audit.

Independent literal cylinder coordinates; does not import the access producer.
The full diameter2.40 corridor is a continuous swept magnet-clearance envelope,
not a few cross-section samples. Foot placement/centroid are outside this scope.
"""
from pathlib import Path
import argparse,json,math

ROOT=Path(__file__).resolve().parents[1]


def cylinders(side):
    import cadquery as cq
    if side not in ('left','right'):raise ValueError('Unknown side')
    outside,mouth,sign=(-1.6,.1,1.) if side=='left' else (151.,149.3,-1.)
    def cylinder(x,y,length,radius=1.2):
        return cq.Solid.makeCylinder(radius,length,cq.Vector(x,y,.75),cq.Vector(sign,0,0))
    return {y:dict(entry=cylinder(outside,y,abs(mouth-outside)),
        corridor=cylinder(outside,y,abs(mouth-outside)+1.2),pocket=cylinder(mouth,y,1.2),
        back_web=cylinder(mouth+sign*1.2,y,.6),surround=cylinder(mouth,y,1.8,1.5)) for y in (103.,111.)}


def difference(a,b):return a if not a.Solids() or not b.Solids() else a.cut(*b.Solids())
def intersection(a,b):return sum(x.intersect(y).Volume() for x in a.Solids() for y in b.Solids())


def audit_entry(side,normal,magnetic,original_normal,original_magnetic):
    if any(not s.isValid() or not s.Solids() for s in [normal,magnetic,original_normal,original_magnetic]):
        raise ValueError('Invalid actual/source housing')
    tools=cylinders(side);rows={};errors=[]
    original_void=difference(original_normal,original_magnetic)
    actual_void=difference(normal,magnetic)
    expected=original_void
    for y,t in tools.items():
        added=normal.intersect(t['entry'])
        if added.Solids():expected=expected.fuse(*added.Solids())
        retained=original_magnetic.intersect(t['surround'])
        row=dict(external_corridor_obstruction_mm3=intersection(magnetic,t['corridor']),
            original_pocket_obstruction_mm3=intersection(magnetic,t['pocket']),
            back_web_missing_mm3=difference(t['back_web'],magnetic).Volume(),
            original_back_web_missing_mm3=difference(t['back_web'],original_magnetic).Volume(),
            original_surround_missing_mm3=difference(retained,magnetic).Volume(),
            corridor_volume_mm3=t['corridor'].Volume(),back_web_required_mm3=math.pi*1.2**2*.6,
            entry_expected_removed_mm3=added.Volume())
        for key,label in [('external_corridor_obstruction_mm3','external corridor blocked'),
            ('original_pocket_obstruction_mm3','original pocket obstructed'),('back_web_missing_mm3','back web removed'),
            ('original_back_web_missing_mm3','original back web contract not established'),
            ('original_surround_missing_mm3','original pocket surround removed')]:
            if row[key]>.002:errors.append(f'y{int(y)}: '+label)
        if row['entry_expected_removed_mm3']<=.002:errors.append(f'y{int(y)}: new-wall entry removal absent')
        rows[f'y{int(y)}']=row
    delta=dict(original_void_mm3=original_void.Volume(),actual_void_mm3=actual_void.Volume(),expected_void_mm3=expected.Volume(),
        expected_vs_actual_missing_mm3=difference(expected,actual_void).Volume(),
        expected_vs_actual_extra_mm3=difference(actual_void,expected).Volume(),
        magnetic_extra_material_mm3=difference(magnetic,normal).Volume())
    for k in ['expected_vs_actual_missing_mm3','expected_vs_actual_extra_mm3','magnetic_extra_material_mm3']:
        if delta[k]>.002:errors.append('magnetic delta '+k)
    return dict(status='failed' if errors else 'pass',errors=errors,side=side,rows=rows,delta=delta,
        physical_qualified=False,scope='Continuous outside-to-pocket diameter2.40mm corridor, retained1.20mm blind pocket,0.60mm back web and exact optional removal')


def review(side,native=False):
    import cadquery as cq
    from tools.kc2_registered_native import preflight_job,revalidate_job,digest
    bindings={};shapes={};original={}
    def bind(path,sha=None):
        actual=digest(path);key=path.relative_to(ROOT).as_posix()
        if sha is not None and actual!=sha:raise ValueError('Changed input '+key)
        if key in bindings and bindings[key]!=actual:raise ValueError('Conflicting input '+key)
        bindings[key]=actual
    for p in [Path(__file__),ROOT/'tools/test_review_kc2_magnetic_entry.py',ROOT/'tools/kc2_registered_native.py']:bind(p)
    for variant in ['normal','magnetic']:
        label=f'lower:{side}:{variant}';job=preflight_job(ROOT,label)
        for name,sha in job['source_sha256'].items():bind(ROOT/name,sha)
        source=job['source'];baseline=ROOT/'hardware/MODELS'/source.name;bind(baseline)
        if native:
            nr=source.parent/'native-generation.json';data=nr.read_bytes();import hashlib
            n=json.loads(data)
            if n.get('status')!='pass' or n.get('selected_job')!=label:raise ValueError('Native execution incomplete')
            entry=n['outputs'][label]
            if entry['generation_sha256']!=job['record_sha256'] or entry['source_sha256']!=job['step_sha256'] or entry['round_trip_verified'] is not True:
                raise ValueError('Native source chain mismatch')
            bind(nr,hashlib.sha256(data).hexdigest())
            for name,sha in n['source_sha256'].items():bind(ROOT/name,sha)
            bind(source.parent/entry['f3d'],entry['f3d_sha256'])
            source=source.parent/entry['readback_step'];bind(source,entry['readback_sha256'])
        print('import actual magnetic entry geometry',side,variant,'native' if native else 'STEP',flush=True)
        shapes[variant]=cq.importers.importStep(str(source)).val()
        original[variant]=cq.importers.importStep(str(baseline)).val()
        if len(shapes[variant].Solids())!=job['count']:raise ValueError('Actual body count mismatch')
    print('continuous entry and exact material delta',side,flush=True)
    result=audit_entry(side,shapes['normal'],shapes['magnetic'],original['normal'],original['magnetic'])
    revalidate_job(ROOT,dict(source_sha256=bindings));result.update(native=native,source_sha256=bindings,requirements=['CON-ARCH-006'])
    name=f'{side}-magnetic-entry'+('-native' if native else '')+'-review.json'
    path=ROOT/'.codex-tmp/registered-housing-fit/lower'/name
    path.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['errors'],flush=True);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('side',choices=['left','right']);p.add_argument('--native',action='store_true');a=p.parse_args()
    raise SystemExit(bool(review(a.side,a.native)['errors']))
