"""CON-ARCH-006 actual prismatic BRep coverage, not volume-only approval.

Every face must be horizontal/vertical planar and every vertex Z an expected
stratum boundary. Only after that proof may one mid-section per stratum cover
its entire open height interval. Unexpected hidden-pocket levels are rejected.
"""
import cadquery as cq
from shapely.geometry import LineString
from shapely.ops import polygonize,unary_union


def section_geometry(shape,z):
    section=shape.intersect(cq.Face.makePlane(basePnt=(0,0,z)))
    lines=[]
    for edge in section.Edges():
        if edge.geomType()!='LINE':raise ValueError('Nonlinear section edge')
        points=[(round(v.X,8),round(v.Y,8)) for v in edge.Vertices()]
        if len(points)!=2:raise ValueError('Unexpected section edge topology')
        if points[0]!=points[1]:lines.append(LineString(points))
    cells=list(polygonize(unary_union(lines)))
    actual=unary_union([p for p in cells if shape.isInside((*p.representative_point().coords[0],z),1e-7)])
    if abs(actual.area-sum(f.Area() for f in section.Faces()))>.001:
        raise ValueError('Section polygonization lost area')
    return actual


def audit_prismatic_solid(shape,required_layers):
    errors=[]
    levels=sorted({z for r in required_layers for z in [r.z0,r.z1]})
    if not levels:raise ValueError('No expected layers')
    if not shape.isValid() or len(shape.Solids())!=1:errors.append('invalid or disconnected actual solid')
    if any(min(abs(v.Z-z) for z in levels)>1e-6 for v in shape.Vertices()):
        errors.append('unexpected vertical transition')
    for face in shape.Faces():
        if face.geomType()!='PLANE':
            errors.append('non-prismatic face');break
        normal=face.normalAt()
        if min(abs(normal.z),abs(abs(normal.z)-1))>1e-7:
            errors.append('sloped face');break
    sections=[]
    if not errors:
        for lower,upper in zip(levels,levels[1:]):
            z=(lower+upper)/2
            wanted=unary_union([r.geometry for r in required_layers if r.z0<z<r.z1])
            actual=section_geometry(shape,z)
            missing=wanted.difference(actual).area;extra=actual.difference(wanted).area
            sections.append(dict(z_mm=z,missing_mm2=missing,extra_mm2=extra,actual_area_mm2=actual.area))
            if missing>.001:errors.append('unfilled structural interior')
            if extra>.001:errors.append('filled reserved or exterior space')
    expected=sum(r.geometry.area*(r.z1-r.z0) for r in required_layers)
    error=abs(shape.Volume()-expected)
    if error>max(.002,expected*1e-7):errors.append('actual volume differs from full required fill')
    return dict(status='pass' if not errors else 'failed',errors=sorted(set(errors)),
                levels_mm=levels,sections=sections,volume_error_mm3=error,physical_qualified=False)
