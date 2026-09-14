"""CON-ARCH-006 exact BRep section faces, without repeated full-solid classifiers.

Use each kernel section face's outer/inner wires as the material boundary. Hole
membership comes from actual face topology, not expected design polygons. Face
area and final union area are independently compared to the kernel section.
"""
import cadquery as cq
from shapely.geometry import LineString,GeometryCollection
from shapely.ops import polygonize,unary_union

def wire_polygon(wire):
    lines=[]
    for edge in wire.Edges():
        if edge.geomType()!='LINE':raise ValueError('Nonlinear section edge')
        p=[(round(v.X,8),round(v.Y,8)) for v in edge.Vertices()]
        if len(p)!=2:raise ValueError('Unexpected section edge topology')
        if p[0]!=p[1]:lines.append(LineString(p))
    cells=list(polygonize(unary_union(lines)))
    if len(cells)!=1 or not cells[0].is_valid:raise ValueError('Wire is not one closed planar loop')
    return cells[0]

def section_geometry(shape,z):
    section=shape.intersect(cq.Face.makePlane(basePnt=(0,0,z)))
    polygons=[];kernel_area=0.
    for face in section.Faces():
        outer=face.outerWire();p=wire_polygon(outer)
        for wire in face.Wires():
            if not wire.isSame(outer):p=p.difference(wire_polygon(wire))
        area=face.Area();kernel_area+=area
        if abs(p.area-area)>.001:raise ValueError('Face wire conversion lost area')
        polygons.append(p)
    actual=unary_union(polygons) if polygons else GeometryCollection()
    if abs(actual.area-kernel_area)>.001:raise ValueError('Section material overlap/loss')
    return actual

def audit_prismatic_solid(shape,required_layers):
    errors=[];levels=sorted({z for l in required_layers for z in (l.z0,l.z1)})
    if not levels:raise ValueError('No expected layers')
    if not shape.isValid() or len(shape.Solids())!=1:errors.append('invalid or disconnected actual solid')
    if any(min(abs(v.Z-z) for z in levels)>1e-6 for v in shape.Vertices()):errors.append('unexpected vertical transition')
    for face in shape.Faces():
        if face.geomType()!='PLANE':errors.append('non-prismatic face');break
        nz=abs(face.normalAt().z)
        if min(nz,abs(nz-1))>1e-7:errors.append('sloped face');break
    sections=[]
    if not errors:
        for lo,hi in zip(levels,levels[1:]):
            z=(lo+hi)/2;wanted=unary_union([l.geometry for l in required_layers if l.z0<z<l.z1])
            print('section material topology',z,flush=True)
            actual=section_geometry(shape,z)
            missing=wanted.difference(actual).area;extra=actual.difference(wanted).area
            sections.append(dict(z_mm=z,missing_mm2=missing,extra_mm2=extra,actual_area_mm2=actual.area))
            if missing>.001:errors.append('unfilled structural interior')
            if extra>.001:errors.append('filled reserved or exterior space')
    expected=sum(l.geometry.area*(l.z1-l.z0) for l in required_layers);error=abs(shape.Volume()-expected)
    if error>max(.002,expected*1e-7):errors.append('actual volume differs from full required fill')
    return dict(status='pass' if not errors else 'failed',errors=sorted(set(errors)),levels_mm=levels,sections=sections,
        volume_error_mm3=error,physical_qualified=False,method='actual BRep face outer/inner wires with area cross-check')
