"""CON-ARCH-006 actual STL prismatic-surface and complete-section proof."""
import numpy as np
from shapely.geometry import Polygon,GeometryCollection
from shapely.ops import unary_union


def mesh_section(mesh,z):
    section=mesh.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
    result=GeometryCollection()
    if section is None:return result
    for loop in section.discrete:
        if np.linalg.norm(loop[0]-loop[-1])>1e-5:raise ValueError('Open mesh section loop')
        polygon=Polygon(loop[:,:2])
        if not polygon.is_valid:raise ValueError('Invalid mesh section loop')
        result=result.symmetric_difference(polygon)
    return result


def audit_mesh(mesh,layers):
    errors=[];sections=[]
    levels=sorted({z for r in layers for z in (r.z0,r.z1)})
    if not levels:raise ValueError('Missing expected layers')
    if (not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume<=0
            or len(mesh.split())!=1):errors.append('invalid closed positive solid')
    if max(mesh.extents)>150.001:errors.append('printer envelope exceeded')
    # STL floats introduce micrometre-scale coordinate rounding. This is not
    # permission to omit millimetre-scale material or functional clearances.
    if np.any(np.min(np.abs(mesh.vertices[:,2,None]-np.array(levels)[None,:]),axis=1)>1e-5):
        errors.append('unexpected vertical transition')
    nz=np.abs(mesh.face_normals[:,2])
    if np.any(np.minimum(nz,np.abs(nz-1))>1e-5):errors.append('non-prismatic surface')
    projection=[]
    if not errors:
        for low,high in zip(levels,levels[1:]):
            z=(low+high)/2
            wanted=unary_union([r.geometry for r in layers if r.z0<z<r.z1])
            actual=mesh_section(mesh,z);projection.append(actual)
            missing=wanted.difference(actual).area;extra=actual.difference(wanted).area
            sections.append(dict(z_mm=z,missing_mm2=missing,extra_mm2=extra,area_mm2=actual.area))
            if missing>.02:errors.append('unfilled structural interior')
            if extra>.02:errors.append('filled reserved space')
    wanted_volume=sum(r.geometry.area*(r.z1-r.z0) for r in layers)
    volume_error=abs(float(mesh.volume)-wanted_volume)
    if volume_error>max(.02,wanted_volume*1e-5):errors.append('volume mismatch')
    return dict(status='failed' if errors else 'pass',errors=sorted(set(errors)),
        levels_mm=levels,sections=sections,volume_error_mm3=volume_error,
        footprint_wkt=unary_union(projection).wkt,bounds_mm=mesh.bounds.flatten().tolist(),
        physical_qualified=False)
