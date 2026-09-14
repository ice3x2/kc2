"""CON-ARCH-006 independent actual central-region inclusion/contact audit.

Literal nominal geometry is reconstructed without importing the producer.
The exact convex tongue sweep proves straight-X insertion in its whole Z span;
this is not an elastic force, fatigue, tolerance or full-keyboard sweep proof.
"""
from pathlib import Path
import json
from shapely.geometry import box,Polygon
from shapely import affinity
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]


def extrude(g,z0,z1):
    import cadquery as cq
    pieces=[]
    for p in getattr(g,'geoms',[g]):
        if p.is_empty:continue
        wp=cq.Workplane('XY').workplane(offset=z0)
        for ring in [p.exterior,*p.interiors]:wp=wp.polyline(list(ring.coords)[:-1]).close()
        pieces.extend(wp.extrude(z1-z0).val().Solids())
    if not pieces:raise ValueError('Empty prism')
    return pieces[0] if len(pieces)==1 else cq.Compound.makeCompound(pieces)


def contract_solids():
    male_xy=Polygon([(-1,-1.2),(2.4,-1.2),(2.8,-.8),(2.8,.8),(2.4,1.2),(-1,1.2)])
    beams=box(1.2,1.35,3.2,2.55).union(box(1.2,-2.55,3.2,-1.35))
    floor=box(1.2,1.35,5,2.55).union(box(1.2,-2.55,5,-1.35)).union(box(4,-2.55,5,2.55))
    tip=Polygon([(1.2,1.35),(1.6,1.18),(3.2,1.18),(3.2,1.35)])
    tips=tip.union(affinity.scale(tip,yfact=-1,origin=(0,0)))
    layers=[]
    for i in range(1,8):
        g=unary_union([affinity.scale(t,xfact=1,yfact=i/7,origin=(0,1.35 if t.centroid.y>0 else -1.35)) for t in tips.geoms])
        layers.append(extrude(g,.8+(i-1)*.1,.8+i*.1))
    contact=layers[0].fuse(*[s for l in layers[1:] for s in l.Solids()])
    female=extrude(floor,-2.2,-1).fuse(*extrude(beams,-1,1.5).Solids(),extrude(box(4,-2.55,5,2.55),-1,1.5),*contact.Solids()).clean()
    sweep=male_xy.union(affinity.translate(male_xy,xoff=-7.8)).convex_hull
    occupied=beams.union(tips)
    return dict(male=extrude(male_xy,-2.2,1.5),female=female,contact=contact,
                sweep=extrude(sweep,-2.2,1.5),
                free=extrude(occupied.buffer(.3,join_style=2).difference(occupied),-1,1.5),
                overhead=extrude(occupied.buffer(.3,join_style=2),1.5,1.8))


def subtract(a,b):return a if not a.Solids() or not b.Solids() else a.cut(*b.Solids())
def common_volume(a,b):return sum(x.intersect(y).Volume() for x in a.Solids() for y in b.Solids())


def audit_pair(left,right,isolated_left,isolated_right):
    if any(not s.isValid() or not s.Solids() for s in [left,right,isolated_left,isolated_right]):
        raise ValueError('Invalid actual/reference shape')
    c=contract_solids();expected=c['male'].intersect(c['contact'])
    actual=left.intersect(right)
    metrics=dict(required_left_missing_mm3=subtract(isolated_left,left).Volume(),
        required_right_missing_mm3=subtract(isolated_right,right).Volume(),
        free_obstruction_mm3=common_volume(right,c['free']),
        overhead_obstruction_mm3=common_volume(right,c['overhead']),
        expected_contact_mm3=expected.Volume(),actual_contact_mm3=actual.Volume(),
        unintended_overlap_mm3=subtract(actual,expected).Volume(),
        missing_contact_mm3=subtract(expected,actual).Volume(),
        rigid_insertion_obstruction_mm3=common_volume(subtract(right,c['contact']),c['sweep']))
    errors=[]
    checks=[('required_left_missing_mm3','required isolated feature missing'),('required_right_missing_mm3','required isolated feature missing'),
        ('free_obstruction_mm3','lateral/rear free space obstructed'),('overhead_obstruction_mm3','overhead free space obstructed'),
        ('unintended_overlap_mm3','unintended central intersection'),('missing_contact_mm3','intended contact missing'),
        ('rigid_insertion_obstruction_mm3','rigid insertion obstruction')]
    for k,msg in checks:
        if metrics[k]>1e-5 and msg not in errors:errors.append(msg)
    if metrics['expected_contact_mm3']<=1e-5:errors.append('nominal contact absent')
    return dict(status='failed' if errors else 'pass',errors=errors,**metrics,
                force_qualified=False,full_keyboard_insertion_verified=False,
                scope='Actual central cropped BReps; exact convex nominal tongue sweep7.8mm, full paired overlap insideROI, free cheek sides/rear/overhead')


def review():
    import cadquery as cq
    from tools.kc2_registered_native import digest,preflight_job,revalidate_job
    bindings={};rows={};actual={};refs={}
    def bind(p,sha=None):
        h=digest(p)
        if sha is not None and sha!=h:raise ValueError('Changed input '+str(p))
        key=p.relative_to(ROOT).as_posix()
        if key in bindings and bindings[key]!=h:raise ValueError('Source changed during audit')
        bindings[key]=h
    feature_record_path=ROOT/'.codex-tmp/registered-housing-fit/central/central-features.json'
    feature_record=json.loads(feature_record_path.read_text());bind(feature_record_path)
    if feature_record.get('status')!='feature_geometry_pass_integration_pending':
        raise ValueError('Isolated feature generation incomplete')
    for name,sha in feature_record['source_sha256'].items():bind(ROOT/name,sha)
    for side in ['left','right']:
        oldpath=ROOT/f'docs/reports/reinforced-covers-20260913/{side}-lower.json';bind(oldpath)
        raw=json.loads(oldpath.read_text())['raw_bounds']
        if raw!=([35.,39.25,170.1125,161.75] if side=='left' else [35.,39.25,198.6875,161.75]):
            raise ValueError('Original coordinate transform changed')
        transform=lambda s,y:s.mirror('YZ').translate((raw[2]+(124.625 if side=='right' else 0)-170.0125,-y,0))
        for variant in ['normal','magnetic']:
            job=preflight_job(ROOT,f'lower:{side}:{variant}')
            for name,sha in job['source_sha256'].items():bind(ROOT/name,sha)
            print('import complete lower',side,variant,flush=True)
            s=cq.importers.importStep(str(job['source'])).val()
            if len(s.Solids())!=job['count'] or not s.isValid():raise ValueError('Actual body count/validity changed')
            for y in [95.,117.]:
                common=transform(s,y)
                # Full mating feature plus adjacent case; xnegative range also
                # contains the entire insertion tongue sweep. Isolated rootsfit.
                roi=cq.Workplane('XY').box(16,10,7.21,centered=(False,False,False)).val().translate((-9,-5,-2.2))
                actual[side,variant,y]=common.intersect(roi)
        for y in [95.,117.]:
            path=ROOT/f'.codex-tmp/registered-housing-fit/central/{side}-central-y{int(y)}.step'
            bind(path,feature_record['outputs'][path.name])
            refs[side,y]=transform(cq.importers.importStep(str(path)).val(),y)
    for variant in ['normal','magnetic']:
        for y in [95.,117.]:
            print('audit actual central',variant,y,flush=True)
            rows[f'{variant}-y{int(y)}']=audit_pair(actual['left',variant,y],actual['right',variant,y],refs['left',y],refs['right',y])
    for p in [Path(__file__),ROOT/'tools/test_review_kc2_integrated_central.py',ROOT/'tools/kc2_registered_native.py']:bind(p)
    revalidate_job(ROOT,dict(source_sha256=bindings))
    errors=[name+': '+e for name,r in rows.items() for e in r['errors']]
    result=dict(status='failed' if errors else 'pass',errors=errors,requirements=['CON-ARCH-006'],rows=rows,
                source_sha256=bindings,physical_qualified=False,canonical_changed=False)
    path=ROOT/'.codex-tmp/registered-housing-fit/central/integrated-review.json'
    path.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],errors,flush=True);return result


if __name__=='__main__':raise SystemExit(bool(review()['errors']))
