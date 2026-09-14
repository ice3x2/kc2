"""CON-ARCH-006 reproduce exact aggregate diode operands, including disjoint boxes."""
import hashlib, json
from pathlib import Path
from shapely import wkt
from tools.review_kc2_local_covers import prism
ROOT=Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    rp=ROOT/'.codex-tmp/registered-housing-fit/lower/right-void-review.json'
    sp=ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal/kc2_right_lower_housing.step'
    d=json.loads(rp.read_text());xy=wkt.loads(d['component_envelope']['required_union_wkt'])
    paths=[Path(__file__),rp,sp,ROOT/'tools/review_kc2_local_covers.py']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('import exact source and complete aggregate tool',flush=True)
    shape=cq.importers.importStep(str(sp)).val();tool=prism(xy,-.4,2.5)
    rows=[];pairs=[]
    for i,t in enumerate(tool.Solids()):
        if abs(t.Volume()-46.794929654225015)>1e-6:continue
        for part,s in enumerate(shape.Solids()):
            b,c=s.BoundingBox(),t.BoundingBox()
            sep=max(c.xmin-b.xmax,b.xmin-c.xmax,c.ymin-b.ymax,b.ymin-c.ymax,c.zmin-b.zmax,b.zmin-c.zmax)
            pairs.append((sep,i,part,s,t))
    for sep,i,part,s,t in sorted(pairs,key=lambda item:(item[0]<=0,item[1],item[2])):
            b,c=s.BoundingBox(),t.BoundingBox()
            hit=s.intersect(t);row=dict(tool=i,part=part,box_axis_separation_mm=sep,
                tool_bounds_mm=[c.xmin,c.ymin,c.zmin,c.xmax,c.ymax,c.zmax],
                part_bounds_mm=[b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax],
                intersection_mm3=hit.Volume(),tool_valid=t.isValid(),tool_volume_mm3=t.Volume())
            if hit.Volume()>.001:
                center=t.Center();row.update(center_inside=s.isInside(center,1e-7),actual_distance_mm=s.distance(t))
                print('HIT',row,flush=True)
            rows.append(row)
            print('aggregate diode',i,'part',part,'separation',sep,'intersection',hit.Volume(),flush=True)
            out=rp.with_name('right-exact-aggregate-diode-diagnosis.json')
            result=dict(requirements=['CON-ARCH-006'],status='diagnostic_running',source_sha256=frozen,rows=rows,
                        tool_valid=tool.isValid(),tool_volume_mm3=tool.Volume(),plan_volume_mm3=xy.area*2.9,physical_qualified=False)
            out.write_text(json.dumps(result,indent=2)+'\n')
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Changed source')
    result['status']='diagnosed_not_accepted';out.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':run()
