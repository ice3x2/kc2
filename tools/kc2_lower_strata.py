"""CON-ARCH-006 conservative whole-material section proof, normal CAD only."""
import math
from shapely.geometry import LineString,GeometryCollection,box
from shapely.ops import polygonize,unary_union

EPS=1e-7
MARGIN=.0001

def material_metrics(material,required):
    if material.is_empty or not material.is_valid or not math.isfinite(material.area) or material.area<=0:
        raise ValueError('empty/invalid/nonfinite actual material section')
    gap=material.distance(required);overlap=material.intersection(required).area
    if not math.isfinite(gap) or gap<0 or not math.isfinite(overlap) or overlap<0:
        raise ValueError('nonfinite/negative actual clearance evidence')
    return gap,overlap

def circle(edge,expected):
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    c=BRepAdaptor_Curve(edge.wrapped).Circle();p=c.Location();d=c.Axis().Direction()
    if abs(abs(d.Z())-1)>EPS or abs(c.Radius()-.55)>EPS:
        raise ValueError('unqualified circle axis/radius')
    xy=(p.X(),p.Y())
    if not any(math.dist(xy,q)<EPS for q in expected):raise ValueError('wrong pilot center')
    return xy,c.Radius()

def line_polygon(wire):
    lines=[]
    for e in wire.Edges():
        if e.geomType()!='LINE':raise ValueError('outer/composite arc is not an allowed LINE wire')
        vertices=e.Vertices()
        if len(vertices)!=2:raise ValueError('invalid line topology')
        if abs(vertices[0].Z-vertices[1].Z)>EPS:raise ValueError('section wire not horizontal')
        points=[(round(v.X,12),round(v.Y,12)) for v in vertices]
        if points[0]!=points[1]:lines.append(LineString(points))
    cells=list(polygonize(unary_union(lines)))
    if len(cells)!=1 or not cells[0].is_valid:raise ValueError('nonclosed/nonunique wire polygon')
    return cells[0]

def face_superset(face,expected):
    outer=face.outerWire();p=line_polygon(outer);filled=[]
    for wire in face.Wires():
        if wire.isSame(outer):continue
        edges=wire.Edges()
        if all(e.geomType()=='LINE' for e in edges):p=p.difference(line_polygon(wire));continue
        if not edges or any(e.geomType()!='CIRCLE' for e in edges):raise ValueError('mixed/unsupported inner wire')
        circles=[circle(e,expected) for e in edges]
        center,radius=circles[0]
        if any(math.dist(center,q)>EPS or abs(radius-r)>EPS for q,r in circles):raise ValueError('mixed pilot circles')
        if abs(sum(e.Length() for e in edges)-2*math.pi*radius)>EPS:raise ValueError('inner pilot is not a full circle')
        filled.append(dict(center_mm=center,radius_mm=radius))
    expected_area=face.Area()+sum(math.pi*r['radius_mm']**2 for r in filled)
    if p.is_empty or not p.is_valid or not math.isfinite(p.area) or p.area<=0 or not math.isfinite(expected_area) or expected_area<=0 or abs(p.area-expected_area)>.001:
        raise ValueError('section face area/topology mismatch')
    return p,filled

def critical_face_superset(face,z,expected):
    outer=face.outerWire()
    if all(e.geomType()=='LINE' for e in outer.Edges()):
        return face_superset(face,expected)[0],'line_face_with_qualified_inner_pilots_filled'
    edges=outer.Edges()
    if (abs(z+.3)>EPS or abs(face.Center().z+.3)>EPS or face.geomType()!='PLANE'
        or abs(abs(face.normalAt().z)-1)>EPS or len(face.Wires())!=1
        or not edges or any(e.geomType()!='CIRCLE' for e in edges)):
        raise ValueError('unqualified critical outer circle')
    circles=[circle(e,expected) for e in edges];center,radius=circles[0]
    if (any(math.dist(center,p)>EPS or abs(radius-r)>EPS for p,r in circles)
        or abs(sum(e.Length() for e in edges)-2*math.pi*radius)>EPS
        or abs(face.Area()-math.pi*radius**2)>EPS):
        raise ValueError('blind pilot cap is not the exact full disk')
    bb=face.BoundingBox();padding=1e-5
    return box(bb.xmin-padding,bb.ymin-padding,bb.xmax+padding,bb.ymax+padding),'qualified_blind_pilot_cap_outward_aabb'

def section_superset(shape,z,expected):
    import cadquery as cq
    from tools.kc2_component_local_certificate import _non_destructive_common
    actual=_non_destructive_common(shape,cq.Face.makePlane(basePnt=(0,0,z)))
    bb=shape.BoundingBox();spans=bb.zmin<z<bb.zmax
    if spans and (not actual.isValid() or not actual.Faces()):raise ValueError('invalid/empty actual Common section')
    shapes=[];filled=[]
    for face in actual.Faces():
        p,holes=face_superset(face,expected);shapes.append(p);filled.extend(holes)
    result=unary_union(shapes) if shapes else GeometryCollection()
    if abs(result.area-sum(p.area for p in shapes))>.001:raise ValueError('section faces overlap')
    return result,filled

def topology(solids,expected,slab):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    lo,hi=slab;levels={lo,hi};cylinders=[];critical=[];counts={};errors=[]
    if len(solids)!=2 or any(not s.isValid() or len(s.Solids())!=1 or not s.Shells() or any(not sh.Closed() for sh in s.Shells()) for s in solids):
        return dict(errors=['two valid closed actual solids required'])
    for part,s in enumerate(solids):
        for v in s.Vertices():
            if lo<=v.Z<=hi:levels.add(round(v.Z,10))
        for face in s.Faces():
            bb=face.BoundingBox()
            if bb.zmax<lo-EPS or bb.zmin>hi+EPS:continue
            kind=face.geomType();counts[kind]=counts.get(kind,0)+1
            if kind=='PLANE':
                nz=abs(face.normalAt().z)
                if min(nz,abs(nz-1))>EPS:errors.append('sloped face')
                if abs(nz-1)<EPS:
                    z=face.Center().z
                    if lo-EPS<=z<=hi+EPS:
                        levels.add(round(max(lo,min(hi,z)),10));critical.append((z,face))
            elif kind=='CYLINDER':
                c=BRepAdaptor_Surface(face.wrapped,True).Cylinder();d=c.Axis().Direction();p=c.Location()
                uv=face.uvBounds();xy=(p.X(),p.Y())
                if abs(abs(d.Z())-1)>EPS or abs(c.Radius()-.55)>EPS or not any(math.dist(xy,q)<EPS for q in expected):
                    errors.append('wrong pilot cylinder axis/radius/center')
                if abs((uv[1]-uv[0])-2*math.pi)>EPS or abs(bb.zmin+.3)>1e-5 or abs(bb.zmax-2.5)>1e-5:
                    errors.append('pilot trim is not full [-.3,2.5] cylinder')
                cylinders.append(dict(part=part,center_mm=xy,radius_mm=c.Radius(),z_bounds_mm=[bb.zmin,bb.zmax]))
            else:errors.append('unsupported face '+kind)
        for edge in s.Edges():
            bb=edge.BoundingBox()
            if bb.zmax<lo-EPS or bb.zmin>hi+EPS:continue
            if edge.geomType()=='LINE':
                points=edge.Vertices()
                if len(points)!=2:errors.append('invalid LINE edge');continue
                a,b=points
                if abs(a.Z-b.Z)>EPS and math.hypot(a.X-b.X,a.Y-b.Y)>EPS:errors.append('oblique trim edge')
            elif edge.geomType()=='CIRCLE':
                try:circle(edge,expected)
                except ValueError as e:errors.append(str(e))
            else:errors.append('unsupported trim edge '+edge.geomType())
            for z in (edge.startPoint().z,edge.endPoint().z):
                if lo+EPS<z<hi-EPS:levels.add(round(z,10))
    if len(cylinders)!=len(expected) or any(sum(math.dist(c['center_mm'],p)<EPS for c in cylinders)!=1 for p in expected):
        errors.append('pilot cylinder inventory is not one-to-one')
    return dict(errors=sorted(set(errors)),levels_mm=sorted(levels),face_counts=counts,cylinders=cylinders,critical_faces=critical)

def audit_normal(solids,required,expected,slab=(-.4,2.5),progress=None):
    t=topology(solids,expected,slab);critical=t.pop('critical_faces',[])
    errors=list(t['errors']);rows=[];closures=[]
    result=dict(t,intervals=rows,critical_closures=closures,physical_qualified=False,
        magnetic_covered=False,scope='Full normal-material superset versus complete component union; not pilot-void fidelity or magnetic proof')
    if errors:return result
    try:
        for lo,hi in zip(t['levels_mm'],t['levels_mm'][1:]):
            if hi-lo<1e-8:raise ValueError('near-coincident critical strata need explicit resolution')
            z=(lo+hi)/2;plans=[];holes=[]
            if progress is not None:progress('interval %.10g..%.10g, section %.10g'%(lo,hi,z))
            for s in solids:
                p,h=section_superset(s,z,expected)
                bb=s.BoundingBox()
                if bb.zmin<z<bb.zmax and (p.is_empty or not p.is_valid or not math.isfinite(p.area) or p.area<=0):
                    raise ValueError('spanning actual body has no valid positive section')
                plans.append(p);holes.extend(h)
            material=unary_union(plans);gap,overlap=material_metrics(material,required)
            rows.append(dict(z_mm=z,z_interval_mm=[lo,hi],material_superset_wkt=material.wkt,
                             filled_inner_pilots=holes,clearance_mm=gap,overlap_mm2=overlap))
            if gap<MARGIN or overlap>0:errors.append('actual material/component conflict or insufficient numerical margin')
        from shapely import wkt
        for z in t['levels_mm']:
            if progress is not None:progress('critical closure %.10g'%z)
            adjacent=[wkt.loads(r['material_superset_wkt']) for r in rows if z in r['z_interval_mm']]
            cap_methods=[]
            for fz,face in critical:
                if abs(fz-z)<EPS:
                    p,method=critical_face_superset(face,z,expected);adjacent.append(p);cap_methods.append(method)
            material=unary_union(adjacent);gap,overlap=material_metrics(material,required)
            closures.append(dict(z_mm=z,material_superset_wkt=material.wkt,clearance_mm=gap,overlap_mm2=overlap,actual_face_methods=cap_methods))
            if gap<MARGIN or overlap>0:errors.append('critical closure component conflict')
    except ValueError as exc:errors.append(str(exc))
    result['errors']=sorted(set(errors));result['status']='fail' if errors else 'pass'
    return result
