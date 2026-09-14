"""CON-ARCH-006 bounded D8 boundary/point/section/ring-start diagnosis."""
import hashlib,json,math
from pathlib import Path
from shapely import wkt
from shapely.geometry import Point,Polygon,box
from tools.review_kc2_local_covers import prism
from tools.kc2_actual_sections import section_geometry
ROOT=Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.TopTools import TopTools_ListOfShape
    rp=ROOT/'.codex-tmp/registered-housing-fit/lower/right-void-review.json'
    sp=ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal/kc2_right_lower_housing.step'
    paths=[Path(__file__),rp,sp,ROOT/'tools/review_kc2_local_covers.py',ROOT/'tools/kc2_actual_sections.py']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    xy=wkt.loads(json.loads(rp.read_text())['component_envelope']['required_union_wkt']).geoms[2]
    coords=list(xy.exterior.coords)[:-1];point=(*coords[0],-.4)
    def extrema(a,b):
        d=BRepExtrema_DistShapeShape(a.wrapped,b.wrapped);d.Perform()
        if not d.IsDone() or not math.isfinite(d.Value()):raise ValueError('Invalid extrema result')
        return dict(distance_mm=d.Value(),inner_solution=d.InnerSolution(),is_done=True)
    print('fresh actual A boundary diagnosis',flush=True)
    a=cq.importers.importStep(str(sp)).val().Solids()[0]
    vertex=cq.Vertex.makeVertex(*point)
    shell_rows=[extrema(vertex,shell) for shell in a.Shells()]
    print('point-shell',shell_rows,flush=True)
    face_candidates=[]
    for i,face in enumerate(a.Faces()):
        b=face.BoundingBox();lower=[b.xmin-1e-5,b.ymin-1e-5,b.zmin-1e-5];upper=[b.xmax+1e-5,b.ymax+1e-5,b.zmax+1e-5]
        bound=math.sqrt(sum(max(lower[j]-point[j],point[j]-upper[j],0)**2 for j in range(3)))
        face_candidates.append((bound,i,face))
    best=math.inf;face_rows=[]
    for bound,i,face in sorted(face_candidates,key=lambda row:row[0]):
        if bound>best+1e-6:break
        row=dict(face=i,aabb_lower_bound_mm=bound,geometry_type=face.geomType(),**extrema(vertex,face))
        best=min(best,row['distance_mm']);face_rows.append(row)
    print('point-face minimum',best,'tested',len(face_rows),flush=True)
    perturb=[]
    for dx,dy,dz in [(0,0,0),(-1e-5,0,0),(1e-5,0,0),(0,-1e-5,0),(0,1e-5,0),(0,0,-1e-5),(0,0,1e-5)]:
        p=(point[0]+dx,point[1]+dy,point[2]+dz)
        perturb.append(dict(point_mm=p,inside=a.isInside(cq.Vector(*p),1e-7)))
    print('perturbed classifications',perturb,flush=True)
    rotated=Polygon(coords[1:]+coords[:1]);a2=cq.importers.importStep(str(sp)).val().Solids()[0]
    t2=prism(rotated,-.4,2.5).Solids()[0]
    rotated_result=dict(first_vertex_xy=list(rotated.exterior.coords)[0],symmetric_difference_mm2=xy.symmetric_difference(rotated).area,
        hausdorff_mm=xy.hausdorff_distance(rotated),tool_valid=t2.isValid(),tool_volume_mm3=t2.Volume(),**extrema(a2,t2))
    print('fresh cyclic-shift tool',rotated_result,flush=True)
    roi=box(xy.bounds[0]-1,xy.bounds[1]-1,xy.bounds[2]+1,xy.bounds[3]+1)
    cutter=prism(roi,-.5,2.50001).Solids()[0]
    args=TopTools_ListOfShape();args.Append(a.wrapped);ts=TopTools_ListOfShape();ts.Append(cutter.wrapped)
    common=BRepAlgoAPI_Common();common.SetArguments(args);common.SetTools(ts);common.SetNonDestructive(True);common.Build()
    if not common.IsDone():raise ValueError('ROI common incomplete')
    local=cq.Shape.cast(common.Shape())
    sections=[]
    for z in (-.40001,-.4,-.39999,0.):
        geometry=section_geometry(local,z)
        sections.append(dict(z_mm=z,material_area_mm2=geometry.area,tool_overlap_mm2=geometry.intersection(xy).area,
                             point_distance_mm=geometry.distance(Point(point[:2])),actual_wkt=geometry.wkt))
        print('actual local section',z,sections[-1]['point_distance_mm'],sections[-1]['tool_overlap_mm2'],flush=True)
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Source changed')
    result=dict(requirements=['CON-ARCH-006'],status='diagnosed_not_accepted',source_sha256=frozen,point_mm=point,
        point_shell_distances=shell_rows,point_face_minimum_mm=best,face_count=len(a.Faces()),checked_faces=face_rows,
        face_screening='All actual face AABBs padded outward 1e-5; skip only lower bound greater than measured best+1e-6',
        perturbations=perturb,cyclic_shift=rotated_result,roi_wkt=roi.wkt,sections=sections,
        local_vertex_z_mm=sorted(set(round(v.Z,8) for v in local.Vertices())),
        local_face_types=sorted(set(f.geomType() for f in local.Faces())),physical_qualified=False)
    rp.with_name('right-d8-boundary-diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':run()
