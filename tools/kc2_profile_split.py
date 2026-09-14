"""CON-ARCH-006 profile-aware two-key partition, plan only until CAD audit.

Adapted explicitly from historical MX split algorithm, but actual family
apertures and .40 mm clearance govern protected rings and receiver positions.
Historical bound generator is deliberately unchanged.
"""
import math
from shapely import voronoi_polygons,affinity
from shapely.geometry import MultiPoint,Point,box
from shapely.ops import unary_union


def profile_split(domain,openings,service,mounting_centers,*,head_diameter=4.0):
    if head_diameter not in [4.0,4.5]:raise ValueError('Unreviewed head diameter')
    head_radius=head_diameter/2
    centers=[(o.centroid.x,o.centroid.y) for o in openings.geoms]
    middle=(domain.bounds[0]+domain.bounds[2])/2
    cells=voronoi_polygons(MultiPoint(centers),extend_to=domain.envelope)
    groups=[[],[]]
    for cell in cells.geoms:
        center=next(c for c in centers if cell.covers(Point(*c)))
        groups[int(center[0]>=middle)].append(cell)
    a,b=[unary_union(g) for g in groups]
    for opening in openings.geoms:
        region=opening.buffer(1.01)
        if opening.centroid.x<middle:a,b=a.union(region),b.difference(region)
        else:a,b=a.difference(region),b.union(region)
    for center in mounting_centers:
        point=Point(*center);disk=point.buffer(2.61,quad_segs=64)
        if a.covers(point):a,b=a.union(disk),b.difference(disk)
        else:a,b=a.difference(disk),b.union(disk)
    seam=a.boundary.intersection(b.boundary).intersection(domain)
    a=domain.intersection(a.buffer(-.20002));b=domain.intersection(b.buffer(-.20002))
    plate=domain.difference(openings).difference(service)
    plate_buffer=plate.buffer(1e-6)
    bosses=unary_union([Point(*c).buffer(2.3,quad_segs=64) for c in mounting_centers])
    protected=bosses.buffer(.3).union(openings.buffer(.60002))
    regions=[o.buffer(.60002) for o in openings.geoms]+[Point(*c).buffer(2.3,quad_segs=64) for c in mounting_centers]
    capture=[];selected=[];candidates=[]
    free_centers=plate.difference(protected).buffer(-head_radius-.40005,quad_segs=64)
    head_points=[]
    for cell in getattr(free_centers,'geoms',[free_centers]):
        if cell.is_empty or cell.distance(seam)>6:continue
        head_points.extend([cell.representative_point(),cell.centroid])
        x0,y0,x1,y1=cell.bounds
        for ix in range(math.ceil(x0*5),math.floor(x1*5)+1):
            for iy in range(math.ceil(y0*5),math.floor(y1*5)+1):
                point=Point(ix/5,iy/5)
                if cell.covers(point):head_points.append(point)
    for head_point in head_points:
        for angle in range(0,360,15):
            radians=math.radians(angle)
            x=head_point.x-3*math.cos(radians);y=head_point.y-3*math.sin(radians)
            key=box(x-.9,y-1,x+3,y+1).union(Point(x+3,y).buffer(head_radius,quad_segs=24))
            key=affinity.rotate(key,angle,origin=(x,y))
            slot=key.buffer(.40004,quad_segs=128)
            if not plate.covers(slot) or slot.intersects(protected):continue
            receiver=affinity.rotate(Point(x+3,y).buffer(head_radius+1.00004,quad_segs=64),angle,origin=(x,y))
            if not plate_buffer.covers(receiver):continue
            zone=receiver.buffer(.40004,quad_segs=128).union(slot)
            for donor in [0,1]:
                source,target=(a,b) if donor==0 else (b,a)
                if key.intersection(source).area<.5 or key.intersection(target).area<8:continue
                target_buffer=target.buffer(1e-6)
                local_receiver=receiver
                transfers=[]
                for _ in range(len(regions)):
                    removal=local_receiver.buffer(.40004,quad_segs=128)
                    receiver_buffer=local_receiver.buffer(1e-6)
                    crossing=[r for r in regions if r.intersects(removal) and not target_buffer.covers(r)
                              and not receiver_buffer.covers(r)]
                    if not crossing:break
                    transfers.extend(crossing)
                    local_receiver=local_receiver.union(unary_union(crossing).buffer(.40004,quad_segs=128)).intersection(domain)
                if len(transfers)>2:continue
                source=source.difference(local_receiver.buffer(.40004,quad_segs=128)).union(key)
                target=target.union(local_receiver).difference(slot)
                aa,bb=(source,target) if donor==0 else (target,source)
                if aa.geom_type!='Polygon' or bb.geom_type!='Polygon':continue
                a_buffer,b_buffer=aa.buffer(1e-6),bb.buffer(1e-6)
                if any(not a_buffer.covers(r) and not b_buffer.covers(r) for r in regions):continue
                if aa.distance(bb)<.39999:continue
                if any(angle==c[2] and donor==c[7] and math.hypot(x-c[0],y-c[1])<.5 for c in candidates):continue
                motions=tuple(affinity.translate(aa,xoff=dx,yoff=dy).intersection(bb).area>1e-6
                              for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)])
                local_zone=local_receiver.buffer(.40004,quad_segs=128).union(slot)
                candidates.append((x,y,angle,aa,bb,motions,local_zone,donor,local_receiver,key,slot))
    found=False
    for i,one in enumerate(candidates):
        for two in candidates[i+1:]:
            if one[6].intersection(two[6]).area>1e-8:continue
            if not all(x or y for x,y in zip(one[5],two[5])):continue
            aa=one[3].difference(two[6]).union(two[3].intersection(two[6]))
            bb=one[4].difference(two[6]).union(two[4].intersection(two[6]))
            if aa.geom_type!='Polygon' or bb.geom_type!='Polygon':continue
            if any(affinity.translate(aa,xoff=dx,yoff=dy).intersection(bb).area<=1e-6
                   for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]):continue
            a,b=aa,bb;capture=[list(one[:3]),list(two[:3])];selected=[one,two];found=True;break
        if found:break
    if not found:
        counts=[sum(c[5][i] for c in candidates) for i in range(4)]
        raise ValueError(f'No retained pair: {len(candidates)} candidates/{len(head_points)} head seeds; +X,-X,+Y,-Y collision counts {counts}; points {[c[:3] for c in candidates]}')
    if a.distance(b)<.39999:raise ValueError('Actual plan gap below .40 mm')
    for opening in openings.geoms:
        ring=opening.buffer(.6).difference(opening)
        if not any(part.buffer(1e-6).covers(ring) for part in (a,b)):
            raise ValueError(f'Incomplete .60 mm clip ring at {opening.centroid.wkt}')
    for center in mounting_centers:
        disk=Point(*center).buffer(2.3,quad_segs=64)
        if not any(part.buffer(1e-6).covers(disk) for part in (a,b)):
            raise ValueError(f'Incomplete collar at {center}')
    clamp_counts=[sum(part.covers(Point(*c)) for c in mounting_centers) for part in [a,b]]
    if min(clamp_counts)<2:raise ValueError('Each part requires at least two complete mounting collars')
    features=[dict(point=list(c[:3]),donor='ab'[c[7]],zone_wkt=c[6].wkt,
                   receiver_wkt=c[8].wkt,key_wkt=c[9].wkt,slot_wkt=c[10].wkt) for c in selected]
    return a,b,dict(capture_count=2,capture_points=capture,clearance_mm=a.distance(b),
        capture_features=features,clamp_counts=clamp_counts,
        head_diameter_mm=head_diameter,neck_width_mm=2.0,receiver_nominal_wall_mm=.6,
        protected_ring_mm=.6,collar_diameter_mm=4.6,physical_qualified=False,
        status='profile_partition_plan_only',native_verified=False)
