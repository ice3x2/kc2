"""CON-ARCH-006 bounded normal-only actual overlap localization, not approval."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    from shapely import wkt,affinity
    from tools.review_kc2_integrated_central import contract_solids,subtract
    from tools.review_kc2_filled_plates import section_geometry
    from tools.kc2_component_local_certificate import _non_destructive_common
    stage=ROOT/'.codex-tmp/registered-housing-fit'
    failure_path=ROOT/'docs/reports/registered-housing-fit-20260913/diagnostics/central-overlap-attempt-1/integrated-review.json'
    frozen={}
    def bind(path,expected=None):
        sha=hashlib.sha256(path.read_bytes()).hexdigest();name=path.relative_to(ROOT).as_posix()
        if expected is not None and sha!=expected:raise ValueError('Stale diagnosis input '+name)
        if name in frozen and frozen[name]!=sha:raise ValueError('Input changed '+name)
        frozen[name]=sha;return path
    failure=json.loads(bind(failure_path).read_text())
    if failure['status']!='failed':raise ValueError('Expected preserved actual failure')
    for name,sha in failure['source_sha256'].items():bind(ROOT/name,sha)
    for name in ('diagnose_kc2_central_overlap','review_kc2_integrated_central',
                 'review_kc2_filled_plates','kc2_component_local_certificate'):
        bind(ROOT/'tools'/(name+'.py'))
    def describe(shape):
        solids=shape.Solids()
        def bounds(s):
            b=s.BoundingBox();return [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]
        return dict(valid=shape.isValid(),volume_mm3=shape.Volume(),solid_count=len(solids),
                    pieces=[dict(volume_mm3=s.Volume(),bounds_mm=bounds(s)) for s in solids])
    shapes={};isolated={}
    for side in ('left','right'):
        path=stage/'lower'/f'{side}-normal'/f'kc2_{side}_lower_housing.step'
        print('import actual normal',side,flush=True)
        shapes[side]=cq.importers.importStep(str(bind(path))).val()
        for y in (95,117):
            path=stage/'central'/f'{side}-central-y{y}.step'
            isolated[side,y]=cq.importers.importStep(str(bind(path))).val()
    print('import old left stock only',flush=True)
    baseline=cq.importers.importStep(str(bind(ROOT/'hardware/MODELS/kc2_left_lower_housing.step'))).val()
    perimeter=json.loads(bind(ROOT/'.codex-tmp/perimeter-wall-plans.json').read_text())['sides']['left']
    def common(shape,side,y):return shape.mirror('YZ').translate((.1 if side=='left' else 153.3,-y,0))
    roi=cq.Workplane('XY').box(16,10,7.21,centered=(False,False,False)).val().translate((-9,-5,-2.2))
    expected=contract_solids()['male'].intersect(contract_solids()['contact'])
    rows=[]
    for y in (95,117):
        print('localize actual central overlap',y,flush=True)
        left=common(shapes['left'],'left',y).intersect(roi)
        right=common(shapes['right'],'right',y).intersect(roi)
        overlap=left.intersect(right)
        nd=_non_destructive_common(left,right)
        unexpected=subtract(overlap,expected)
        oldleft=common(baseline,'left',y).intersect(roi)
        refs={s:common(isolated[s,y],s,y) for s in ('left','right')}
        row=dict(y=y,actual_overlap=describe(overlap),non_destructive_overlap=describe(nd),
                 unexpected=describe(unexpected),
                 unexpected_in_isolated_left_mm3=unexpected.intersect(refs['left']).Volume(),
                 unexpected_in_isolated_right_mm3=unexpected.intersect(refs['right']).Volume(),
                 unexpected_in_old_left_mm3=unexpected.intersect(oldleft).Volume(),sections=[])
        levels=sorted({round(v.Z,9) for v in unexpected.Vertices()})
        row['unexpected_vertex_z_mm']=levels
        planned={key:affinity.translate(affinity.scale(wkt.loads(perimeter[key]),xfact=-1,yfact=1,origin=(0,0)),xoff=.1,yoff=-y)
                 for key in ('wall_wkt','floor_addition_wkt')}
        for lo,hi in zip(levels,levels[1:]):
            if hi-lo<1e-7:continue
            z=(lo+hi)/2;section=section_geometry(unexpected,z)
            row['sections'].append(dict(z_band_mm=[lo,hi],z_mm=z,area_mm2=section.area,wkt=section.wkt,
                bounds_mm=list(section.bounds) if not section.is_empty else [],
                planned_left_wall_overlap_mm2=section.intersection(planned['wall_wkt']).area,
                planned_left_floor_addition_overlap_mm2=section.intersection(planned['floor_addition_wkt']).area))
        print(json.dumps({k:v for k,v in row.items() if k!='sections'}),flush=True)
        rows.append(row)
    for name,sha in frozen.items():bind(ROOT/name,sha)
    report=dict(requirements=['CON-ARCH-006'],status='diagnosed_not_accepted',source_sha256=frozen,rows=rows,
                scope='Normal variants only; actual local overlap positions and original/isolated stock attribution, not correction approval',physical_qualified=False)
    output=stage/'central/overlap-localization.json'
    if output.exists():raise ValueError('Existing immutable diagnosis retained')
    output.write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':run()
