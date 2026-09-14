"""CON-ARCH-006 independent actual floor-only right A/B capture audit.

CAD collision volumes are geometric evidence, not measured force/strength.
"""
import argparse
import hashlib
import json
from pathlib import Path
from shapely.geometry import box,Point
from tools.kc2_floor_capture import contiguous_throat
from tools.review_kc2_local_covers import prism,cut_union
from tools.review_kc2_filled_plates import section_geometry

ROOT=Path(__file__).resolve().parents[1]
VOLUME_TOLERANCE=1e-5

def intersect(a,b):
    import cadquery as cq
    pieces=[s.intersect(t) for s in a.Solids() for t in b.Solids()]
    return cq.Compound.makeCompound([s for p in pieces for s in p.Solids()])

def feature(seam,y):
    male=box(seam-.1,y-1,seam+3,y+1).union(Point(seam+3,y).buffer(2.25,quad_segs=24))
    void=male.buffer(.40004,quad_segs=128)
    ring=void.buffer(1.2,quad_segs=128).difference(void).intersection(box(seam+.30004,y-5,seam+8,y+5))
    return male,ring

def inspect_pair(solids,seam=81.84375,ys=(73.25,86.25)):
    errors=[];captures=[];floors=[]
    if len(ys)!=2 or len(set(ys))!=2:
        return dict(errors=['exactly two distinct features required'],physical_qualified=False)
    if len(solids)!=2 or any(not s.isValid() or len(s.Solids())!=1 for s in solids):
        return dict(errors=['two valid connected actual bodies required'],physical_qualified=False)
    a,b=sorted(solids,key=lambda s:s.Center().x)
    gap=a.distance(b);overlap=intersect(a,b).Volume()
    if gap<.39999:errors.append('full-body minimum gap below .40')
    if overlap>VOLUME_TOLERANCE:errors.append('full-body overlap')
    shapes=[];sections=[]
    for index,s in enumerate((a,b)):
        bb=s.BoundingBox();floorbox=prism(box(bb.xmin-1,bb.ymin-1,bb.xmax+1,bb.ymax+1),-2.2,-1)
        actual=intersect(s,floorbox);section=section_geometry(s,-1.6)
        local=[]
        if section.is_empty or section.geom_type!='Polygon':local.append('floor not connected')
        if any(-2.2+1e-6<v.Z<-1-1e-6 for v in s.Vertices()):local.append('floor has height transition')
        for f in s.Faces():
            fb=f.BoundingBox()
            if fb.zmax>-2.2+1e-6 and fb.zmin<-1-1e-6:
                if f.geomType()!='PLANE':local.append('floor non-planar face');continue
                nz=abs(f.normalAt().z)
                if min(nz,abs(nz-1))>1e-7:local.append('floor sloped face')
        missing=extra=float('inf')
        if not section.is_empty:
            expected=prism(section,-2.2,-1)
            missing=cut_union(expected,actual).Volume();extra=cut_union(actual,expected).Volume()
            if max(missing,extra)>VOLUME_TOLERANCE:local.append('floor not constant 1.2 mm prism')
        floors.append(dict(part=index,connected=section.geom_type=='Polygon',
                           constant_prism_missing_mm3=missing,constant_prism_extra_mm3=extra,
                           errors=sorted(set(local))))
        errors.extend('part%d: %s'%(index,e) for e in local)
        shapes.append(actual);sections.append(section)
    for y in ys:
        male,ring=feature(seam,y)
        ring_missing=cut_union(prism(ring,-2.2,-1),shapes[1]).Volume()
        if ring.geom_type!='Polygon':errors.append('required ring disconnected')
        if ring_missing>VOLUME_TOLERANCE:errors.append('y%s: complete 1.2 XY floor ring missing'%y)
        neck=prism(box(seam-.2,y-1,seam+.2,y+1),-2.2,2.5)
        head=prism(Point(seam+3,y).buffer(2.25,quad_segs=24),-2.2,2.5)
        neck_missing=cut_union(neck,a).Volume();head_missing=cut_union(head,a).Volume()
        if max(neck_missing,head_missing)>VOLUME_TOLERANCE:errors.append('y%s: full-height male stock missing'%y)
        throats=[]
        for dx in (.35,.5):
            try:
                width=contiguous_throat(sections[1],seam+dx,y)
                if abs(width-2.80008)>.00002:errors.append('y%s: floor throat differs'%y)
                throats.append(dict(x_mm=seam+dx,width_mm=width,shoulder_mm=(4.5-width)/2))
            except ValueError as exc:errors.append('y%s: %s'%(y,exc))
        # Ring/head extents plus full 1 mm displacement remain strictly inside
        # this ROI. Source crop edges cannot manufacture a local collision.
        roi=box(seam-3,y-6,seam+9,y+6)
        roi_tool=prism(roi,-2.2,-1)
        local_a=intersect(shapes[0],roi_tool);local_b=intersect(shapes[1],roi_tool)
        motions=[]
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            volume=intersect(local_a.translate((dx,dy,0)),local_b).Volume()
            motions.append(dict(dx_mm=dx,dy_mm=dy,collision_mm3=volume,
                                method='actual cropped floor BRep translation/intersection'))
            if volume<=VOLUME_TOLERANCE:errors.append('y%s: missing floor capture direction %s,%s'%(y,dx,dy))
        captures.append(dict(y_mm=y,ring_width_mm=1.2,ring_area_mm2=ring.area,
            ring_missing_mm3=ring_missing,root_missing_mm3=neck_missing,head_missing_mm3=head_missing,
            throats=throats,motions=motions,motion_roi_xy_mm=list(roi.bounds),motion_z_mm=[-2.2,-1]))
    return dict(errors=sorted(set(errors)),body_count=2,gap_mm=gap,overlap_mm3=overlap,
                floor_z_mm=[-2.2,-1],floor=floors,captures=captures,physical_qualified=False)

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def review(magnetic=False,native=False):
    import cadquery as cq
    variant='magnetic' if magnetic else 'normal'
    folder=ROOT/'.codex-tmp/registered-housing-fit/lower'/('right-'+variant)
    frozen={}
    def bind(path,expected=None):
        sha=digest(path);key=path.relative_to(ROOT).as_posix()
        if expected is not None and sha!=expected:raise ValueError('Changed source '+key)
        if key in frozen and frozen[key]!=sha:raise ValueError('Changed during audit '+key)
        frozen[key]=sha;return path
    recordpath=bind(folder/'generation.json');record=json.loads(recordpath.read_text())
    if record.get('status')!='generated_pending_independent_review' or record.get('side')!='right' or record.get('magnetic') is not magnetic or type(record.get('body_count')) is not int or record['body_count']!=2:
        raise ValueError('Wrong current generation')
    name='kc2_right_lower_housing'+('_magnetic' if magnetic else '')+'.step'
    actual=bind(folder/name,record['outputs'][name])
    for path,sha in record['source_sha256'].items():bind(ROOT/path,sha)
    for name in ('review_kc2_floor_receiver.py','test_review_kc2_floor_receiver.py','kc2_floor_capture.py',
                 'test_kc2_floor_capture.py','review_kc2_local_covers.py','review_kc2_filled_plates.py'):
        bind(ROOT/'tools'/name)
    if native:
        from tools.kc2_lower_native_identity import native_output
        bind(ROOT/'tools/kc2_lower_native_identity.py')
        nrpath=bind(folder/'native-generation.json');nr=json.loads(nrpath.read_text())
        row=native_output(nr,'right',variant,digest(recordpath),digest(actual))
        for path,sha in nr['source_sha256'].items():bind(ROOT/path,sha)
        bind(folder/row['f3d'],row['f3d_sha256'])
        actual=bind(folder/row['readback_step'],row['readback_sha256'])
    print('independent actual floor-only receiver',variant,'native',native,flush=True)
    result=inspect_pair(cq.importers.importStep(str(actual)).solids().vals())
    for name,sha in frozen.items():
        if digest(ROOT/name)!=sha:raise ValueError('Source changed during floor receiver audit')
    result.update(requirements=['CON-ARCH-006'],schema='right-floor-receiver-v1',side='right',
        magnetic=magnetic,native_readback=native,status='fail' if result['errors'] else 'pass',source_sha256=frozen,
        scope='Actual floor-only throat/ring/capture and full-height male stock; actual 3D floor-band motion, not force test. General floor sealing, STL limits, Z insertion, populated clearance, magnetic entry and central coupling remain separate.')
    output=folder/('floor-capture'+('-native' if native else '')+'-review.json')
    output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['errors'],flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--magnetic',action='store_true');p.add_argument('--native',action='store_true');a=p.parse_args()
    raise SystemExit(bool(review(a.magnetic,a.native)['errors']))
