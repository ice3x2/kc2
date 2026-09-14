"""CON-ARCH-006 independent actual right A/B roots, capture and floor audit.

Numeric2mm roots/4.5mm heads/.4mm pair clearance are checked in actual BRep.
Force, fatigue, deposited layer bonding and exact printed fit remain unqualified.
"""
from pathlib import Path
import argparse,json,hashlib
from shapely.geometry import box,Point
from tools.review_kc2_local_covers import prism,cut_union
from tools.review_kc2_filled_plates import section_geometry
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inspect_pair(solids,seam,ys):
    import cadquery as cq
    errors=[];rows=[]
    if len(solids)!=2 or any(not s.isValid() or len(s.Solids())!=1 for s in solids):
        return dict(errors=['invalid/disconnected actual parts'])
    a,b=solids;gap=a.distance(b)
    if gap<.39999:errors.append('A/B clearance below .40 mm')
    if a.intersect(b).Volume()>.002:errors.append('A/B solids overlap')
    for y in ys:
        neck=prism(box(seam-.2,y-1,seam+.2,y+1),-2.2,2.5)
        head=prism(Point(seam+3,y).buffer(2.25,quad_segs=24),-2.2,2.5)
        neck_missing=cut_union(neck,a).Volume();head_missing=cut_union(head,a).Volume()
        if neck_missing>.002:errors.append('root material missing')
        if head_missing>.002:errors.append('head material missing')
        line=cq.Edge.makeLine(cq.Vector(seam+.5,y-3,0),cq.Vector(seam+.5,y+3,0))
        receiver=line.intersect(b)
        throat=6.-sum(edge.Length() for edge in receiver.Edges())
        if abs(throat-2.80008)>.005:errors.append('receiver throat differs from 2.80 mm')
        rows.append(dict(y_mm=y,root_width_mm=2.,head_diameter_mm=4.5,root_missing_mm3=neck_missing,head_missing_mm3=head_missing,
            actual_throat_mm=throat,minimum_shoulder_capture_mm=(4.5-throat)/2))
    motion=[]
    for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        collision=a.translate((dx,dy,0)).intersect(b).Volume()
        motion.append(dict(dx=dx,dy=dy,collision_mm3=collision))
        if collision<=.001:errors.append('lost planar capture direction')
    floor=[]
    for i,s in enumerate(solids):
        bb=s.BoundingBox()
        if max(bb.xlen,bb.ylen,bb.zlen)>150.001:errors.append('150 mm print envelope exceeded')
        # Establish constant floor stratum before one full section represents it.
        if any(-2.2+1e-5<v.Z<-1.-1e-5 for v in s.Vertices()):errors.append('unexpected floor transition')
        for face in s.Faces():
            fb=face.BoundingBox()
            if fb.zmax>-2.2+1e-5 and fb.zmin<-1.-1e-5:
                if face.geomType()!='PLANE':errors.append('non-prismatic floor face');break
                n=face.normalAt()
                if min(abs(n.z),abs(abs(n.z)-1))>1e-7:errors.append('sloped floor face');break
        section=section_geometry(s,-1.6)
        if section.geom_type!='Polygon' or section.is_empty:errors.append('floor is not connected')
        floor.append(dict(part=i,section_z=-1.6,geometry_type=section.geom_type,area_mm2=section.area))
    return dict(errors=sorted(set(errors)),gap_mm=gap,captures=rows,motions=motion,floor=floor,physical_qualified=False)

def review(magnetic=False,native=False):
    import cadquery as cq
    from tools.kc2_lower_native_identity import native_output
    variant='magnetic' if magnetic else 'normal';folder=ROOT/'.codex-tmp/registered-housing-fit/lower'/f'right-{variant}'
    recordpath=folder/'generation.json';record=json.loads(recordpath.read_text())
    if record['status']!='generated_pending_independent_review':raise ValueError('Generation incomplete')
    name='kc2_right_lower_housing'+('_magnetic' if magnetic else '')+'.step';actual=folder/name
    if digest(actual)!=record['outputs'][name]:raise ValueError('Changed STEP')
    paths=[Path(__file__),ROOT/'tools/test_review_kc2_lower_split.py',ROOT/'tools/review_kc2_local_covers.py',
        ROOT/'tools/review_kc2_filled_plates.py',ROOT/'tools/kc2_lower_native_identity.py',recordpath,actual]
    for path,sha in record['source_sha256'].items():
        p=ROOT/path
        if digest(p)!=sha:raise ValueError('Stale source '+path)
        paths.append(p)
    if native:
        np=folder/'native-generation.json';nr=json.loads(np.read_text());row=native_output(nr,'right',variant,digest(recordpath),digest(actual))
        paths.append(np)
        for path,sha in nr['source_sha256'].items():
            p=ROOT/path
            if digest(p)!=sha:raise ValueError('Stale native source '+path)
            paths.append(p)
        for field in ('readback','f3d'):
            p=folder/row['readback_step' if field=='readback' else 'f3d']
            if digest(p)!=row[field+'_sha256']:raise ValueError('Changed native artifact')
            paths.append(p)
        actual=folder/row['readback_step']
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('import actual right pair',variant,'native',native,flush=True)
    solids=sorted(cq.importers.importStep(str(actual)).solids().vals(),key=lambda s:s.Center().x)
    result=inspect_pair(solids,81.84375,[73.25,86.25])
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Sources changed during audit')
    result.update(requirements=['CON-ARCH-006'],status='fail' if result['errors'] else 'pass',source_sha256=frozen,
        side='right',magnetic=magnetic,native_readback=native,
        scope='Actual full-depth roots/heads, four-direction capture, pair gap and prismatic connected floor; populated voids and central coupling separate')
    (folder/('split'+('-native' if native else '')+'-review.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result['errors'],flush=True);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--magnetic',action='store_true');p.add_argument('--native',action='store_true');args=p.parse_args()
    raise SystemExit(bool(review(args.magnetic,args.native)['errors']))
