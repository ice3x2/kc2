"""CON-ARCH-006 D8 closed-boundary separation plus independent section seed."""
import hashlib,json,math
from pathlib import Path
from shapely import wkt
from shapely.geometry import Point
from tools.review_kc2_local_covers import prism
from tools.kc2_actual_sections import section_geometry
ROOT=Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.TopTools import TopTools_ListOfShape
    stage=ROOT/'.codex-tmp/registered-housing-fit/lower'
    rp=stage/'right-void-review.json';bp=stage/'right-d8-boundary-diagnosis.json'
    sp=stage/'right-normal/kc2_right_lower_housing.step'
    paths=[Path(__file__),rp,bp,sp,ROOT/'tools/review_kc2_local_covers.py',ROOT/'tools/kc2_actual_sections.py']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    prior=json.loads(bp.read_text())
    for name,sha in prior['source_sha256'].items():
        path=ROOT/name
        if digest(path)!=sha:raise ValueError('Changed prior diagnostic input')
        paths.append(path)
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    xy=wkt.loads(json.loads(rp.read_text())['component_envelope']['required_union_wkt']).geoms[2]
    roi=wkt.loads(prior['roi_wkt'])
    print('fresh A/D8 closed shells',flush=True)
    a=cq.importers.importStep(str(sp)).val().Solids()[0];tool=prism(xy,-.4,2.5).Solids()[0]
    ash, tsh=a.Shells(),tool.Shells()
    if not a.isValid() or not tool.isValid() or not ash or not tsh or any(not s.Closed() for s in ash+tsh):
        raise ValueError('Invalid/open boundary')
    rows=[]
    for i,s in enumerate(ash):
        for j,t in enumerate(tsh):
            d=BRepExtrema_DistShapeShape(s.wrapped,t.wrapped);d.Perform()
            if not d.IsDone() or not math.isfinite(d.Value()):raise ValueError('Boundary extrema incomplete')
            row=dict(a_shell=i,tool_shell=j,distance_mm=d.Value(),inner_solution=d.InnerSolution(),is_done=True)
            rows.append(row);print('shell distance',row,flush=True)
    center=tool.Center();seed=cq.Vector(center.x,center.y,center.z)
    seed_classification=a.isInside(seed,1e-7)
    roi_tool=prism(roi,-.5,2.50001).Solids()[0]
    args=TopTools_ListOfShape();args.Append(a.wrapped);cutters=TopTools_ListOfShape();cutters.Append(roi_tool.wrapped)
    common=BRepAlgoAPI_Common();common.SetArguments(args);common.SetTools(cutters);common.SetNonDestructive(True);common.Build()
    if not common.IsDone():raise ValueError('ROI extraction failed')
    local=cq.Shape.cast(common.Shape());faces=[];errors=[]
    if not local.isValid():errors.append('Invalid actual ROI')
    zs=sorted(set(round(v.Z,8) for v in local.Vertices()))
    if zs!=[-.5,2.5]:errors.append('Unexpected intermediate Z transition')
    for i,face in enumerate(local.Faces()):
        if face.geomType()!='PLANE':errors.append('Nonplane ROI face');continue
        n=face.normalAt();nz=abs(n.z)
        if min(nz,abs(nz-1))>1e-7:errors.append('Sloped ROI face')
        faces.append(dict(face=i,normal_xyz=[n.x,n.y,n.z],vertical=bool(nz<=1e-7),horizontal=bool(abs(nz-1)<=1e-7)))
    actual=section_geometry(local,center.z);point=Point(center.x,center.y)
    footprint_outside=xy.difference(roi).area
    overlap=actual.intersection(xy).area
    volume_error=abs(local.Volume()-actual.area*3.)
    if footprint_outside>1e-10:errors.append('Tool not fully inside ROI')
    if volume_error>.002:errors.append('ROI prism volume mismatch')
    if overlap>1e-8:errors.append('Actual ROI tool section overlap')
    if seed_classification or actual.covers(point):errors.append('Seed is not outside actual A')
    if any(r['distance_mm']<=1e-4 or r['inner_solution'] for r in rows):errors.append('Closed boundaries not separated')
    ab,tb=a.BoundingBox(),tool.BoundingBox()
    larger=bool(ab.xlen>tb.xlen+1e-4 or ab.ylen>tb.ylen+1e-4 or ab.zlen>tb.zlen+1e-4)
    if not larger:errors.append('Cannot exclude A entirely contained in tool')
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Changed diagnostic source')
    result=dict(requirements=['CON-ARCH-006'],status='diagnosed_not_accepted',errors=sorted(set(errors)),source_sha256=frozen,
        a_shell_count=len(ash),tool_shell_count=len(tsh),all_shells_closed=True,shell_pairs=rows,
        seed_xyz=[center.x,center.y,center.z],seed_solid_classifier_inside=seed_classification,
        seed_actual_section_inside=bool(actual.covers(point)),seed_section_distance_mm=actual.distance(point),
        a_extents_exclude_containment_in_tool=larger,roi_vertex_z_mm=zs,roi_faces=faces,
        roi_section_wkt=actual.wkt,roi_tool_overlap_mm2=overlap,tool_outside_roi_mm2=footprint_outside,
        roi_prism_volume_error_mm3=volume_error,scope='D8 local diagnosis only; not complete component or housing approval',physical_qualified=False)
    (stage/'right-d8-shell-seed-diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
    print('D8 local diagnostic errors',result['errors'],'seed inside',seed_classification,actual.covers(point),
          'overlap',overlap,'prism volume error',volume_error,flush=True)
    return result


if __name__=='__main__':run()
