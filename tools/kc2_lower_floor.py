"""CON-ARCH-006 actual constant connected structural floor, no foot design."""
from tools.review_kc2_filled_plates import section_geometry
def inspect_floor(shape):
    errors=[]
    if not shape.isValid() or len(shape.Solids())!=1:return dict(errors=['invalid/disconnected body'])
    if abs(shape.BoundingBox().zmin+2.2)>1e-5:errors.append('bottom datum changed')
    if any(-2.2+1e-5<v.Z<-1.-1e-5 for v in shape.Vertices()):errors.append('unexpected floor transition')
    for face in shape.Faces():
        b=face.BoundingBox()
        if b.zmax>-2.2+1e-5 and b.zmin<-1.-1e-5:
            if face.geomType()!='PLANE':errors.append('non-prismatic floor face');break
            n=face.normalAt()
            if min(abs(n.z),abs(abs(n.z)-1))>1e-7:errors.append('sloped floor face');break
    section=section_geometry(shape,-1.6)
    if section.geom_type!='Polygon' or section.is_empty:errors.append('floor is not one connected polygon')
    if section.geom_type=='Polygon' and len(section.interiors):errors.append('enclosed through-floor void')
    return dict(errors=sorted(set(errors)),floor_z_mm=[-2.2,-1.],floor_thickness_mm=1.2,
        section_z_mm=-1.6,section_area_mm2=section.area,section_type=section.geom_type,
        enclosed_floor_void_count=len(section.interiors) if section.geom_type=='Polygon' else None,
        physical_qualified=False,scope='Actual floor boundary/face proof plus entire constant-stratum section; no feet or adhesion evaluation')
