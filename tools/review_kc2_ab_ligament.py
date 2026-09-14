"""CON-ARCH-006 actual local clip-root failure witness, not exhaustive review."""
import json
from pathlib import Path
from shapely import wkt
from shapely.geometry import box
from shapely.ops import nearest_points


def ligament_witness(section,openings,roi,minimum=.6):
    edge=section.boundary.intersection(roi)
    if edge.is_empty:raise ValueError('Missing local seam edge')
    distance=edge.distance(openings)
    return dict(status='failed' if distance<minimum else 'local_witness_pass',
        minimum_local_mm=distance,required_mm=minimum,
        points=[list(p.coords[0]) for p in nearest_points(edge,openings)],
        scope='Local witness only, not exhaustive minimum wall or physical strength')


def review():
    import cadquery as cq
    from tools.review_kc2_filled_plates import section_geometry
    from tools.stage_kc2_ab_relief import ROOT,STAGE,digest
    report_path=ROOT/'docs/reports/solid-filled-plates-20260913/right-deep_sea.json'
    source=ROOT/'hardware/MODELS/kc2_right_deep_sea_upper_housing.step'
    revised=STAGE/'deep_sea'/source.name
    report=json.loads(report_path.read_text())
    openings=wkt.loads(report['plan_wkt']['openings'])
    roi=box(83.5,87.5,85,88.31)
    results={}
    for label,path in [('original',source),('relieved',revised)]:
        print('actual section',label,flush=True)
        solids=cq.importers.importStep(str(path)).solids().vals()
        if len(solids)!=2:raise ValueError('Unexpected body count')
        shape=solids[1]
        section=section_geometry(shape,6.0)
        results[label]=ligament_witness(section,openings,roi)
        results[label]['source_sha256']=digest(path)
    failed=results['relieved']['minimum_local_mm']<.6
    evidence=dict(requirements=['CON-ARCH-006'],status='failed' if failed else 'local_witness_pass',physical_qualified=False,
        stage_approved=False,z_mm=6.0,roi_wkt=roi.wkt,results=results,
        reduction_mm=results['original']['minimum_local_mm']-results['relieved']['minimum_local_mm'],
        reason='Local clip ligament below .60 mm' if failed else 'Only selected witness satisfies .60 mm',
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__),str(report_path.relative_to(ROOT)):digest(report_path)})
    (STAGE/'deep_sea'/'clip-ligament-review.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence),flush=True)


if __name__=='__main__':review()
