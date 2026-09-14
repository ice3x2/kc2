"""CON-ARCH-006 exact binary-STL zero-area normalization, no file writer.

All surviving oriented facet records remain byte-identical, including normals
and attributes. No tolerance welding, hole filling or positive-area removal.
"""
import hashlib
import struct
from fractions import Fraction
import numpy as np
import trimesh


def sha(data):return hashlib.sha256(data).hexdigest()


def decode(data):
    if not isinstance(data,bytes) or len(data)<84:raise ValueError('Expected binary STL bytes')
    count=struct.unpack_from('<I',data,80)[0]
    if count<1 or len(data)!=84+50*count:raise ValueError('Malformed binary STL facet count')
    records=[data[84+50*i:134+50*i] for i in range(count)]
    values=np.array([struct.unpack('<12fH',r)[:12] for r in records],dtype=np.float64)
    if not np.isfinite(values).all():raise ValueError('Nonfinite serialized STL normal/coordinates')
    return records,values[:,3:].reshape(-1,3,3)


def material_mesh(triangles):
    # Standard exact-float vertex sharing for topology checks. No geometry is
    # emitted from this object; output is made only from original facet bytes.
    vertices,inverse=np.unique(triangles.reshape(-1,3),axis=0,return_inverse=True)
    return trimesh.Trimesh(vertices=vertices,faces=inverse.reshape(-1,3),process=False)


def exact_zero_facet(triangle):
    # Rational arithmetic makes the deletion decision exact for serialized
    # binary32 values, even if a double cross product cancels tiny real area.
    a,b,c=[[Fraction(float(v)) for v in point] for point in triangle]
    u=[x-y for x,y in zip(b,a)];v=[x-y for x,y in zip(c,a)]
    return all(u[i]*v[j]-u[j]*v[i]==0 for i,j in ((0,1),(1,2),(2,0)))


def normalize(data):
    records,triangles=decode(data)
    cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    zero=np.all(cross==0.,axis=1)
    for i in np.where(zero)[0]:zero[i]=exact_zero_facet(triangles[i])
    keep=~zero
    if not keep.any():raise ValueError('No positive-area material facets')
    surviving=[r for r,k in zip(records,keep) if k]
    output=data if not zero.any() else data[:80]+struct.pack('<I',len(surviving))+b''.join(surviving)
    reread,actual=decode(output)
    if reread!=surviving or not np.array_equal(actual,triangles[keep]):
        raise ValueError('Surviving oriented facet bytes changed')
    before=material_mesh(triangles);after=material_mesh(actual)
    if (not after.is_watertight or not after.is_winding_consistent or not np.isfinite(after.volume)
        or after.volume<=0 or len(after.split(only_watertight=False))!=1):
        raise ValueError('Remaining actual mesh is not one closed positive consistently wound material')
    # Exact bounds are possible because no surviving float32 vertex changes.
    if not np.array_equal(triangles.reshape(-1,3).min(axis=0),actual.reshape(-1,3).min(axis=0)) or not np.array_equal(triangles.reshape(-1,3).max(axis=0),actual.reshape(-1,3).max(axis=0)):
        raise ValueError('Discarding artifact would alter serialized bounds')
    delta=float(after.volume-before.volume)
    # Summation order may change when exactly zero-contribution triangles are
    # omitted. This 64-ULP relative bound covers only floating summation noise;
    # unchanged oriented facet bytes provide the stronger material identity.
    epsilon=float(64*np.finfo(np.float64).eps*max(1.,abs(before.volume),abs(after.volume)))
    if not np.isfinite(before.volume) or abs(delta)>epsilon:raise ValueError('Material volume changed')
    result=dict(requirements=['CON-ARCH-006'],schema='binary-stl-exact-zero-area-filter-v1',status='pass',errors=[],
        input_sha256=sha(data),output_sha256=sha(output),input_facets=len(records),output_facets=len(surviving),
        removed_count=int(zero.sum()),removed_facets=[dict(index=int(i),xyz_mm=triangles[i].tolist(),area_mm2=0.) for i in np.where(zero)[0]],
        surviving_oriented_records_sha256=sha(b''.join(sorted(surviving))),output_oriented_records_sha256=sha(b''.join(sorted(reread))),
        surviving_oriented_record_sequence_unchanged=True,serialized_bounds_unchanged=True,
        before_volume_mm3=float(before.volume),after_volume_mm3=float(after.volume),volume_delta_mm3=delta,
        volume_summation_epsilon_mm3=epsilon,output_watertight=True,output_winding_consistent=True,output_components=1,
        physical_qualified=False,method='remove only exactly zero cross-product serialized facets; all retained facet bytes unchanged')
    return output,result
