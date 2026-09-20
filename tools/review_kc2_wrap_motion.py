"""CON-ARCH-006 continuous nominal translation checks on actual STL geometry.

Vertical insertion uses certified prismatic Z bands and interval arithmetic.
Horizontal and A/B checks use conservative full XY triangle projections.
No assembly force, deformation or arbitrary rotation is qualified.
"""
import json
import numpy as np
import trimesh
import shapely
from shapely import affinity
from shapely.geometry import Polygon
from shapely.ops import unary_union
from tools.kc2_wrap_native import jobs, preflight
from tools.review_kc2_wrap_housings import ROOT, STAGE, check_bindings, world
from tools.kc2_pcb_seating import digest, horizontal_section


def prismatic_band(mesh, lo, hi):
    z = mesh.triangles[:,:,2]
    relevant = (z.max(axis=1) > lo+1e-5) & (z.min(axis=1) < hi-1e-5)
    normals = mesh.face_normals[relevant]
    nz = np.abs(normals[:,2])
    transverse = np.linalg.norm(normals[:,:2],axis=1)
    drift = np.divide(nz,transverse,out=np.full_like(nz,np.inf),where=transverse>1e-12)*(hi-lo)
    horizontal = np.ptp(z[relevant],axis=1) <= 1e-5
    return bool(np.all(np.isfinite(normals)) and np.all(horizontal | (drift <= 2e-5)))


def layers(mesh, lo=4.1, hi=5.6):
    if not prismatic_band(mesh, lo, hi):
        raise ValueError('Actual relevant surface is not prismatic; cannot certify sweep')
    levels = sorted({lo,hi} | {float(z) for z in np.round(mesh.vertices[:,2],5) if lo < z < hi})
    # 0.00005 mm outward expansion exceeds the permitted 0.00002 mm
    # directional drift plus level rounding, preserving a conservative sweep.
    return [(a,b,horizontal_section(mesh,(a+b)/2).buffer(.00005))
            for a,b in zip(levels,levels[1:]) if b-a > 1e-5]


def validate_height_band(mesh, lower):
    if ((lower and mesh.bounds[1,2] > 5.6+1e-5) or
            (not lower and mesh.bounds[0,2] < 4.1-1e-5)):
        raise ValueError('Material lies outside the certified contact-height band')


def sweep_overlap(fixed, moving, lift):
    rows = []
    for a,b,lower in fixed:
        for c,d,upper in moving:
            # Interiors overlap at every offset in this open interval. This is
            # an interval certificate, not a finite sampling of the travel.
            start, stop = max(0.,a-d), min(lift,b-c)
            if stop-start <= 1e-5 or lower.is_empty or upper.is_empty:
                continue
            area = lower.intersection(upper).area
            rows.append(dict(offset_interval_mm=[start,stop], fixed_z_mm=[a,b],
                             moving_z_mm=[c,d], overlap_mm2=area))
    return rows


def project_mesh(mesh):
    triangles = mesh.triangles[:,:,:2]
    vectors = triangles[:,1:,:]-triangles[:,0:1,:]
    twice_area = np.abs(vectors[:,0,0]*vectors[:,1,1]-vectors[:,0,1]*vectors[:,1,0])
    kept = triangles[twice_area > 1e-10]
    return shapely.union_all(shapely.polygons(kept))


def sweep_right(shape, distance):
    if distance < 0:
        raise ValueError('Rightward travel must be nonnegative')
    filled = unary_union([Polygon(g.exterior) for g in getattr(shape,'geoms',[shape]) if not g.is_empty])
    stock = [filled, affinity.translate(filled,xoff=distance)]
    for p in getattr(filled,'geoms',[filled]):
        coords = list(p.exterior.coords)
        for a,b in zip(coords,coords[1:]):
            quad = Polygon([a,b,(b[0]+distance,b[1]),(a[0]+distance,a[1])])
            if quad.area > 1e-10:
                stock.append(quad)
    return unary_union(stock)


def review():
    rows, bands, projections, errors, bindings = {}, {}, {}, [], {}
    ab = []
    for label in jobs():
        job = preflight(ROOT,label)
        generation = json.loads(job['generation_path'].read_text())
        bindings.update(generation['source_sha256'])
        bindings[job['generation_path'].relative_to(ROOT).as_posix()] = digest(job['generation_path'])
        meshes, shadows = [], []
        for name, sha in generation['outputs'].items():
            if not name.endswith('.stl'):
                continue
            path = job['folder']/name
            if digest(path) != sha:
                raise ValueError('Changed actual motion input: '+name)
            bindings[path.relative_to(ROOT).as_posix()] = sha
            mesh = trimesh.load(path,force='mesh')
            if not mesh.is_watertight or len(mesh.split()) != 1:
                raise ValueError('Invalid actual motion mesh')
            meshes.append(mesh)
            shadows.append(project_mesh(mesh))
        merged = trimesh.util.concatenate(meshes)
        validate_height_band(merged,label.split(':')[1] in ('normal','magnetic'))
        bands[label] = layers(merged)
        projections[label] = unary_union(shadows)
        rows[label] = dict(body_count=len(meshes), prismatic_relevant_band=True,
                          band_z_mm=[4.1,5.6], layer_count=len(bands[label]),
                          maximum_allowed_directional_drift_mm=.00002,
                          conservative_xy_expansion_mm=.00005,z_tolerance_mm=.00001,
                          actual_z_bounds_mm=merged.bounds[:,2].tolist())
        if len(shadows) == 2:
            overlap = shadows[0].intersection(shadows[1]).area
            gap = shadows[0].distance(shadows[1])
            ab.append(dict(label=label, projected_overlap_mm2=overlap, projected_gap_mm=gap))
            if overlap > .005 or gap < .3999:
                errors.append(label+': A/B vertical path or gap not certified')
        print('actual motion layers/projection',label,flush=True)
    assemblies = []
    for side in ('left','right'):
        for lower in ('normal','magnetic'):
            for upper in ('mx','choc_v1','deep_sea'):
                intervals = sweep_overlap(bands[side+':'+lower],bands[side+':'+upper],1.5)
                maximum = max((r['overlap_mm2'] for r in intervals),default=0.)
                assemblies.append(dict(side=side,lower=lower,upper=upper, lift_mm=1.5,
                                       maximum_overlap_mm2=maximum,intervals=intervals))
                if maximum > .005:
                    errors.append(side+':'+lower+':'+upper+': vertical insertion collision')
    joins = []
    for lower in ('normal','magnetic'):
        for upper in ('mx','choc_v1','deep_sea'):
            left = world(projections['left:'+lower].union(projections['left:'+upper]),'left')
            right = world(projections['right:'+lower].union(projections['right:'+upper]),'right')
            distance = max(1.,left.bounds[2]-right.bounds[0]+1.)
            overlap = left.intersection(sweep_right(right,distance)).area
            joins.append(dict(lower=lower,upper=upper, horizontal_travel_mm=distance,
                              swept_projection_overlap_mm2=overlap))
            if overlap > .005:
                errors.append(lower+':'+upper+': central horizontal path not certified')
    for name in ('tools/review_kc2_wrap_motion.py','tools/test_review_kc2_wrap_motion.py',
                 'tools/review_kc2_wrap_housings.py','tools/kc2_pcb_seating.py','tools/kc2_wrap_native.py'):
        bindings[name] = digest(ROOT/name)
    check_bindings(ROOT,bindings)
    result = dict(requirements=['CON-ARCH-006'],status='pass' if not errors else 'failed',
                  rows=rows,assemblies=assemblies,joins=joins,ab=ab,errors=errors,
                  source_sha256=bindings,physical_qualified=False,
                  scope='Continuous nominal vertical insertion in certified Z bands; conservative A/B projection separation and central horizontal sweep. No print deformation, force or arbitrary rotations.')
    (STAGE/'motion-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],errors,flush=True)
    return result


if __name__ == '__main__':
    raise SystemExit(review()['status'] != 'pass')
