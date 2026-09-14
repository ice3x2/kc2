"""CON-ARCH-006 independent bounded shell/seed/prism certificate primitives.

No CAD imports at module import time: semantic source validation remains portable.
"""
import hashlib
import math


def number(value,minimum=0.,maximum=math.inf):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError('Invalid numeric certificate evidence')
    return value


def validate_local_evidence(record,tool_xy=None):
    for key in ('eligible','subject_valid','tool_valid','subject_closed','tool_closed','subject_not_contained_by_tool'):
        if record.get(key) is not True:raise ValueError('Unproved '+key)
    if record.get('errors')!=[]:raise ValueError('Local certificate errors')
    counts=[record.get(k) for k in ('a_shell_count','tool_shell_count')]
    if any(type(v) is not int or v<1 for v in counts):raise ValueError('Invalid shell counts')
    pairs=record['shell_pairs']
    if len(pairs)!=counts[0]*counts[1] or {(r['a_shell'],r['tool_shell']) for r in pairs}!={(i,j) for i in range(counts[0]) for j in range(counts[1])}:
        raise ValueError('Missing shell pair')
    for row in pairs:
        if type(row['a_shell']) is not int or type(row['tool_shell']) is not int:raise ValueError('Invalid shell IDs')
        if row['is_done'] is not True or row['inner_solution'] is not False:raise ValueError('Unproved shell distance')
        if number(row['distance_mm'])<=1e-4:raise ValueError('Nonpositive boundary clearance')
    seed=record['seed'];roi=record['roi']
    if seed['tool_plan_contains'] is not True or seed['actual_classifier_inside'] is not False or seed['actual_section_inside'] is not False:
        raise ValueError('Outside seed not proved')
    if len(seed['xyz'])!=3:raise ValueError('Missing seed coordinates')
    for value in seed['xyz']:number(value,-math.inf)
    number(seed['xyz'][2],-.4,2.5)
    if number(seed['section_distance_mm'])<=0:raise ValueError('Seed on material')
    if roi['errors']!=[] or roi['valid'] is not True or roi['all_faces_planar_axis_aligned'] is not True or roi['levels_mm']!=[-.5,2.5]:
        raise ValueError('Unproved local prism')
    fc,vc,hc=[roi[k] for k in ('face_count','vertical_face_count','horizontal_face_count')]
    if any(type(v) is not int or v<0 for v in (fc,vc,hc)) or fc<1 or vc+hc!=fc:raise ValueError('Face inventory mismatch')
    number(roi['section_z_mm'],-.4,2.5)
    number(roi['section_area_mm2'])
    number(roi['tool_overlap_mm2'],0,1e-8)
    number(roi['tool_outside_roi_mm2'],0,1e-10)
    number(roi['volume_error_mm3'],0,.002)
    from shapely import wkt
    from shapely.geometry import Point
    actual=wkt.loads(roi['section_wkt']);footprint=wkt.loads(roi['footprint_wkt'])
    point=Point(seed['xyz'][:2])
    if not (-.4<seed['xyz'][2]<2.5) or abs(seed['xyz'][2]-roi['section_z_mm'])>1e-9:
        raise ValueError('Seed section height mismatch')
    if not actual.is_valid or actual.is_empty or not footprint.contains(point) or actual.covers(point):
        raise ValueError('Actual section seed not outside')
    if (abs(actual.area-roi['section_area_mm2'])>1e-8 or abs(actual.distance(point)-seed['section_distance_mm'])>1e-8
            or actual.difference(footprint).area>1e-8):raise ValueError('Actual section evidence mismatch')
    if tool_xy is not None and (not tool_xy.contains(point) or tool_xy.difference(footprint).area>1e-10
            or actual.intersection(tool_xy).area>1e-8):raise ValueError('Tool/ROI section identity mismatch')
    return True


def validate_certificate(record):
    if (record.get('schema')!='right-d8-local-certificate-v1' or record.get('status')!='pass'
            or record.get('errors')!=[] or record.get('actual_tool_count')!=153
            or record.get('required_z_mm')!=[-.4,2.5] or not record.get('source_sha256')):
        raise ValueError('Incomplete D8 certificate')
    inventory=record['tool_inventory']
    if len(inventory)!=153 or any(type(r['tool']) is not int for r in inventory) or [r['tool'] for r in inventory]!=list(range(153)):
        raise ValueError('Wrong actual tool inventory order')
    for row in inventory:
        if hashlib.sha256(row['expected_wkt'].encode()).hexdigest()!=row['expected_sha256']:
            raise ValueError('Tool geometry hash mismatch')
        if any(row.get(k) is not True for k in ('valid','closed','axis_prismatic')) or row['vertex_z_mm']!=[-.4,2.5]:
            raise ValueError('Unproved actual tool prism')
        if len(row['actual_bounds_mm'])!=6:raise ValueError('Missing tool bounds')
        for v in row['actual_bounds_mm']:number(v,-math.inf)
        if number(row['actual_volume_mm3'])<=0:raise ValueError('Invalid tool volume')
        number(row['actual_section_missing_mm2'],0,1e-8)
        number(row['actual_section_extra_mm2'],0,1e-8)
    cases=record['cases']
    if len(cases)!=2 or {(r['variant'],r['part'],r['tool']) for r in cases}!={('normal',0,2),('magnetic',0,2)}:
        raise ValueError('Wrong D8 identities')
    from shapely import wkt
    for case in cases:
        if type(case['part']) is not int or type(case['tool']) is not int:raise ValueError('Invalid case IDs')
        for path_key,sha_key in (('step_path','step_sha256'),('generation_path','generation_sha256')):
            if record['source_sha256'].get(case[path_key])!=case[sha_key]:raise ValueError('D8 source identity missing')
        validate_local_evidence(case['local'],wkt.loads(inventory[case['tool']]['expected_wkt']))
    return True


def verify_bindings(root,bindings,required):
    if not bindings or any(name not in bindings for name in required):
        raise ValueError('Missing required source binding')
    for name,expected in bindings.items():
        path=root/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Stale source binding '+name)


def _non_destructive_common(a,b):
    import cadquery as cq
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.TopTools import TopTools_ListOfShape
    args=TopTools_ListOfShape();args.Append(a.wrapped)
    tools=TopTools_ListOfShape();tools.Append(b.wrapped)
    common=BRepAlgoAPI_Common();common.SetArguments(args);common.SetTools(tools)
    common.SetNonDestructive(True);common.Build()
    if not common.IsDone():raise ValueError('Non-destructive Common failed')
    return cq.Shape.cast(common.Shape())


def _section_xy(shape,z):
    import cadquery as cq
    from shapely.geometry import LineString
    from shapely.ops import polygonize,unary_union
    section=_non_destructive_common(shape,cq.Face.makePlane(basePnt=(0,0,z)))
    def wire_polygon(wire):
        lines=[]
        for edge in wire.Edges():
            if edge.geomType()!='LINE':raise ValueError('Nonlinear tool section')
            points=[(round(v.X,12),round(v.Y,12)) for v in edge.Vertices()]
            if len(points)!=2:raise ValueError('Unexpected tool edge')
            lines.append(LineString(points))
        cells=list(polygonize(unary_union(lines)))
        if len(cells)!=1:raise ValueError('Invalid tool section wire')
        return cells[0]
    cells=[];area=0.
    for face in section.Faces():
        outer=face.outerWire();poly=wire_polygon(outer)
        for wire in face.Wires():
            if not wire.isSame(outer):poly=poly.difference(wire_polygon(wire))
        cells.append(poly);area+=face.Area()
    actual=unary_union(cells)
    if abs(actual.area-area)>1e-8:raise ValueError('Actual tool section area mismatch')
    return actual


def inspect_tool_prism(tool,expected,index):
    from tools.kc2_solid_clearance import solid_bounds
    solid_bounds(tool)
    levels=sorted(set(round(v.Z,8) for v in tool.Vertices()))
    if levels!=[-.4,2.5]:raise ValueError('Wrong actual tool Z strata')
    for face in tool.Faces():
        if face.geomType()!='PLANE':raise ValueError('Nonplanar tool face')
        nz=abs(face.normalAt().z)
        if min(nz,abs(nz-1))>1e-7:raise ValueError('Sloped tool face')
    actual=_section_xy(tool,1.05)
    b=tool.BoundingBox()
    return dict(tool=index,expected_wkt=expected.wkt,expected_sha256=hashlib.sha256(expected.wkt.encode()).hexdigest(),
        actual_bounds_mm=[b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax],actual_volume_mm3=tool.Volume(),
        actual_section_missing_mm2=expected.difference(actual).area,actual_section_extra_mm2=actual.difference(expected).area,
        actual_section_wkt=actual.wkt,valid=True,closed=True,axis_prismatic=True,vertex_z_mm=levels)


def inspect_local_prism(shape,tool_xy,seed_z):
    errors=[];zs=sorted(set(round(v.Z,8) for v in shape.Vertices()))
    if not shape.isValid():errors.append('invalid actual ROI')
    if zs!=[-.5,2.5]:errors.append('unexpected intermediate Z transition')
    vertical=horizontal=0
    for face in shape.Faces():
        if face.geomType()!='PLANE':errors.append('nonplanar ROI face');continue
        nz=abs(face.normalAt().z)
        if nz<=1e-7:vertical+=1
        elif abs(nz-1)<=1e-7:horizontal+=1
        else:errors.append('sloped ROI face')
    actual=_section_xy(shape,seed_z)
    overlap=actual.intersection(tool_xy).area
    volume_error=abs(shape.Volume()-actual.area*3.)
    if overlap>1e-8:errors.append('actual tool section overlap')
    if volume_error>.002:errors.append('actual ROI prism volume mismatch')
    return dict(errors=sorted(set(errors)),valid=shape.isValid(),levels_mm=zs,
        face_count=len(shape.Faces()),vertical_face_count=vertical,horizontal_face_count=horizontal,
        all_faces_planar_axis_aligned=vertical+horizontal==len(shape.Faces()),section_z_mm=seed_z,
        section_wkt=actual.wkt,section_area_mm2=actual.area,tool_overlap_mm2=overlap,volume_error_mm3=volume_error)


def certify_local(subject,tool,tool_xy,roi):
    from shapely.geometry import Point
    from shapely import wkt
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from tools.kc2_solid_clearance import solid_bounds
    from tools.review_kc2_local_covers import prism
    solid_bounds(subject);solid_bounds(tool)
    errors=[];rows=[]
    for i,a in enumerate(subject.Shells()):
        for j,b in enumerate(tool.Shells()):
            solver=BRepExtrema_DistShapeShape(a.wrapped,b.wrapped);solver.Perform()
            if not solver.IsDone() or not math.isfinite(solver.Value()):
                raise ValueError('Boundary solver incomplete/nonfinite')
            row=dict(a_shell=i,tool_shell=j,is_done=True,distance_mm=solver.Value(),inner_solution=solver.InnerSolution())
            rows.append(row)
            if row['distance_mm']<=1e-4 or row['inner_solution']:errors.append('boundaries touch/intersect or unproved')
    center=tool.Center();point=Point(center.x,center.y)
    plan_contains=tool_xy.contains(point)
    source_inside=subject.isInside(center,1e-7)
    cutter=prism(roi,-.5,2.50001).Solids()[0]
    local=_non_destructive_common(subject,cutter)
    local_result=inspect_local_prism(local,tool_xy,center.z)
    local_result['footprint_wkt']=roi.wkt
    local_result['tool_outside_roi_mm2']=tool_xy.difference(roi).area
    actual=wkt.loads(local_result['section_wkt'])
    inside=actual.covers(point)
    if not plan_contains or source_inside or inside:errors.append('outside seed not established')
    if local_result['tool_outside_roi_mm2']>1e-10:errors.append('tool outside ROI')
    ab,tb=subject.BoundingBox(),tool.BoundingBox()
    excluded=ab.xlen>tb.xlen+1e-4 or ab.ylen>tb.ylen+1e-4 or ab.zlen>tb.zlen+1e-4
    if not excluded:errors.append('reverse containment not excluded')
    errors.extend(local_result['errors'])
    return dict(eligible=not errors,errors=sorted(set(errors)),subject_valid=True,tool_valid=True,
        subject_closed=True,tool_closed=True,a_shell_count=len(subject.Shells()),tool_shell_count=len(tool.Shells()),
        shell_pairs=rows,seed=dict(xyz=[center.x,center.y,center.z],tool_plan_contains=plan_contains,
            actual_classifier_inside=source_inside,actual_section_inside=bool(inside),section_distance_mm=actual.distance(point)),
        subject_not_contained_by_tool=bool(excluded),roi=local_result)
