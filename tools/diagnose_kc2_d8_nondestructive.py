"""CON-ARCH-006 one fresh D8 tool: extrema before/after non-destructive Common."""
import hashlib,json
from pathlib import Path
from shapely import wkt
from tools.review_kc2_local_covers import prism
ROOT=Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopTools import TopTools_ListOfShape
    rp=ROOT/'.codex-tmp/registered-housing-fit/lower/right-void-review.json'
    sp=ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal/kc2_right_lower_housing.step'
    paths=[Path(__file__),rp,sp,ROOT/'tools/review_kc2_local_covers.py']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    xy=wkt.loads(json.loads(rp.read_text())['component_envelope']['required_union_wkt']).geoms[2]
    print('fresh actual A and exact D8 polygon2 tool',flush=True)
    a=cq.importers.importStep(str(sp)).val().Solids()[0]
    t=prism(xy,-.4,2.5).Solids()[0]
    def distance():
        solver=BRepExtrema_DistShapeShape(a.wrapped,t.wrapped);solver.Perform()
        return dict(is_done=solver.IsDone(),distance_mm=solver.Value(),inner_solution=solver.InnerSolution(),solution_count=solver.NbSolution())
    before=distance();print('distance before',before,flush=True)
    center=t.Center()
    classified=dict(center_inside=a.isInside(center,1e-7),
        vertex_inside=[dict(x=v.X,y=v.Y,z=v.Z,inside=a.isInside(v.Center(),1e-7)) for v in t.Vertices()])
    args=TopTools_ListOfShape();args.Append(a.wrapped)
    cutters=TopTools_ListOfShape();cutters.Append(t.wrapped)
    common=BRepAlgoAPI_Common();common.SetArguments(args);common.SetTools(cutters)
    common.SetNonDestructive(True)
    print('build NON-DESTRUCTIVE Common',flush=True);common.Build()
    if not common.IsDone():raise ValueError('Common incomplete')
    hit=cq.Shape.cast(common.Shape())
    after=distance();print('distance after',after,'common',hit.Volume(),flush=True)
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Sources changed')
    result=dict(requirements=['CON-ARCH-006'],status='diagnosed_not_accepted',source_sha256=frozen,
        reference='right D8',local_center_xy=[16.775,35.025],pcb_center_xy=[181.9125,74.275],
        distance_before=before,distance_after=after,non_destructive_common_mm3=hit.Volume(),
        tool_valid=t.isValid(),subject_valid=a.isValid(),classifications=classified,
        tool_area_mm2=xy.area,tool_volume_mm3=t.Volume(),physical_qualified=False)
    rp.with_name('right-d8-nondestructive-diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':run()
