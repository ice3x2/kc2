"""CON-ARCH-006 narrowed diode whole-tool misclassification diagnosis."""
import hashlib, json
from pathlib import Path
from shapely import wkt
from tools.kc2_required_lower_clearance import required_envelope
from tools.review_kc2_local_covers import prism
ROOT=Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    rp=ROOT/'.codex-tmp/registered-housing-fit/lower/right-void-review.json'
    report=json.loads(rp.read_text())
    raw=wkt.loads(report['component_envelope']['raw_classes_wkt']['diode_body_pads_fillets'])
    required=required_envelope({'diode':raw})
    paths=[Path(__file__),rp,ROOT/'hardware/MODELS/kc2_right_lower_housing.step',
           ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal/kc2_right_lower_housing.step',
           ROOT/'tools/kc2_required_lower_clearance.py',ROOT/'tools/review_kc2_local_covers.py']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('import both actual pairs',flush=True)
    shapes={label:cq.importers.importStep(str(path)).val() for label,path in [('baseline',paths[2]),('current',paths[3])]}
    rows=[]
    for i,g in enumerate(required.geoms):
        t=prism(g,-.4,2.5);b=t.BoundingBox();center=g.centroid
        row=dict(index=i,tool_bounds_mm=[b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax],tool_valid=t.isValid(),
                 tool_volume_mm3=t.Volume(),plan_volume_mm3=g.area*2.9,center_xy=[center.x,center.y],hits=[])
        for label,shape in shapes.items():
            for part,s in enumerate(sorted(shape.Solids(),key=lambda s:s.Center().x)):
                sb=s.BoundingBox()
                if sb.xmax<b.xmin or sb.xmin>b.xmax or sb.ymax<b.ymin or sb.ymin>b.ymax: continue
                hit=s.intersect(t)
                if hit.Volume()>.000001:
                    hb=hit.BoundingBox()
                    row['hits'].append(dict(variant=label,part=part,volume_mm3=hit.Volume(),
                       bounds_mm=[hb.xmin,hb.ymin,hb.zmin,hb.xmax,hb.ymax,hb.zmax],
                       center_inside_z0=s.isInside(cq.Vector(center.x,center.y,0),1e-7),
                       tool_distance_mm=s.distance(t),hit_valid=hit.isValid()))
        rows.append(row)
        print('diode',i,row['hits'],flush=True)
        result=dict(requirements=['CON-ARCH-006'],status='diagnostic_running',source_sha256=frozen,rows=rows,physical_qualified=False)
        out=rp.with_name('right-diode-failure-diagnosis.json');out.write_text(json.dumps(result,indent=2)+'\n')
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Changed source')
    result['status']='diagnosed_not_accepted';out.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':run()
