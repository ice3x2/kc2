"""CON-ARCH-006 exact binary-STL conformity, without moving any vertex.

Accept only a three-edge boundary cycle whose three serialized float32 points
are exactly collinear as rational numbers. Split its one long triangle edge at
the EXISTING middle vertex. The two replacement triangles cover exactly the
same oriented surface. Noncollinear holes and arbitrary repair are rejected.
"""
import struct
from fractions import Fraction
import numpy as np
from tools.kc2_stl_zero_area_filter import decode, material_mesh, exact_zero_facet, sha
from tools.kc2_stl_zero_area_filter import normalize as validate_closed


def _collinear(points):
    return exact_zero_facet(np.asarray(points))


def normalize(data):
    records, triangles = decode(data)
    zero = [exact_zero_facet(t) if np.all(np.cross(t[1]-t[0], t[2]-t[0]) == 0) else False for t in triangles]
    kept = [r for r, z in zip(records, zero) if not z]
    source_volume = material_mesh(triangles).volume
    surviving = triangles[np.logical_not(zero)]
    mesh = material_mesh(surviving)
    edges, counts = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
    if np.any(counts > 2):
        raise ValueError('Nonmanifold edges are not repairable by conformity')
    border = edges[counts == 1]
    neighbors = {}
    for a, b in border:
        neighbors.setdefault(int(a), set()).add(int(b))
        neighbors.setdefault(int(b), set()).add(int(a))
    visited, splits = set(), {}
    for start in neighbors:
        if start in visited:
            continue
        component, todo = set(), [start]
        while todo:
            v = todo.pop()
            if v in component:
                continue
            component.add(v); todo.extend(neighbors[v]-component)
        visited.update(component)
        if len(component) != 3 or any(len(neighbors[v]) != 2 for v in component):
            raise ValueError('Boundary is not a single collinear T junction')
        ids = list(component)
        xyz = mesh.vertices[ids]
        if not _collinear(xyz):
            raise ValueError('Refusing to fill a noncollinear hole')
        axis = int(np.argmax(np.ptp(xyz, axis=0)))
        ordered = sorted(ids, key=lambda v:mesh.vertices[v, axis])
        first, mid, last = ordered
        if not mesh.vertices[first, axis] < mesh.vertices[mid, axis] < mesh.vertices[last, axis]:
            raise ValueError('No strict existing middle vertex')
        matches = [i for i, face in enumerate(mesh.faces) if first in face and last in face]
        if len(matches) != 1 or matches[0] in splits:
            raise ValueError('Ambiguous long edge')
        splits[matches[0]] = mesh.vertices[mid]
    output_records = []
    proof = []
    for i, (record, triangle) in enumerate(zip(kept, surviving)):
        if i not in splits:
            output_records.append(record)
            continue
        middle = splits[i]
        candidates = [j for j in range(3) if _collinear([triangle[j], middle, triangle[(j+1)%3]])]
        if len(candidates) != 1:
            raise ValueError('Ambiguous containing edge')
        j = candidates[0]
        a, b, c = triangle[j], triangle[(j+1)%3], triangle[(j+2)%3]
        # Each replacement keeps the original normal and attribute bytes.
        for points in ([a, middle, c], [middle, b, c]):
            output_records.append(record[:12]+struct.pack('<9f', *np.asarray(points).ravel())+record[-2:])
        proof.append(dict(source_facet_index=i, original_vertices=triangle.tolist(),
                          existing_middle_vertex=middle.tolist(), exact_collinearity=True))
    result = data[:80]+struct.pack('<I', len(output_records))+b''.join(output_records)
    result, check = validate_closed(result)
    _, reread = decode(result)
    delta = float(material_mesh(reread).volume-source_volume)
    epsilon = float(128*np.finfo(float).eps*max(1., abs(source_volume)))
    if abs(delta) > epsilon:
        raise ValueError('Conformity changed signed material volume')
    if not np.array_equal(triangles.reshape(-1, 3).min(axis=0), reread.reshape(-1, 3).min(axis=0)) or not np.array_equal(triangles.reshape(-1, 3).max(axis=0), reread.reshape(-1, 3).max(axis=0)):
        raise ValueError('Conformity changed bounds')
    return result, dict(status='pass', errors=[], input_sha256=sha(data), output_sha256=sha(result),
        removed_exact_zero_facets=sum(zero), split_count=len(proof), splits=proof,
        volume_delta_mm3=delta, volume_summation_epsilon_mm3=epsilon,
        output_watertight=check['output_watertight'], output_components=check['output_components'],
        vertices_moved=False, noncollinear_holes_filled=False, physical_qualified=False)
