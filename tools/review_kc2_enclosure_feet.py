"""CON-ARCH-006: retained silicone feet vs new actual STL mass centroids.

Floor masks are the source-bound floor sections verified by the main STEP audit.
This is housing-only static support geometry, not populated stability or adhesion.
"""
import hashlib,json,subprocess
from pathlib import Path
import trimesh
from shapely import wkt
from shapely.geometry import Point
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
MODELS=ROOT/'hardware/MODELS'
REPORTS=ROOT/'docs/reports/enclosed-housing-20260909'

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def check_feet(floor,centers,centroid):
    disks=[Point(c).buffer(4,quad_segs=64) for c in centers]
    hull=unary_union(disks).convex_hull
    errors=[]
    if any(not floor.buffer(1e-7).covers(d) for d in disks):errors.append('foot disk crosses edge or seam')
    if not hull.covers(Point(centroid)):errors.append('centroid outside foot contact hull')
    if any(a.intersection(b).area>1e-7 for i,a in enumerate(disks) for b in disks[i+1:]):errors.append('foot disks overlap')
    return {'errors':errors,'centers_xy_mm':centers,'centroid_xy_mm':list(centroid),
        'minimum_disk_to_edge_or_seam_mm':min(d.distance(floor.boundary) for d in disks),
        'centroid_inside_contact_hull':hull.covers(Point(centroid)),
        'centroid_to_contact_hull_boundary_mm':Point(centroid).distance(hull.boundary)}

def svg_document(shapes,body,label):
    bounds=unary_union(shapes).bounds
    x0,y0,x1,y1=bounds
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{x1-x0+4}mm" height="{y1-y0+14}mm" '
            f'viewBox="{x0-2} {y0-12} {x1-x0+4} {y1-y0+14}">'
            f'<text x="{x0}" y="{y0-7}" font-size="2">{label}</text>'
            f'<text x="{x0}" y="{y0-3}" font-size="2">CON-ARCH-006; mm / housing-local XY; physical qualification pending</text>{body}</svg>')

def main():
    old_bytes=subprocess.check_output(['git','show','cc854a3:hardware/MODELS/kc2_housing_manifest.json'],cwd=ROOT)
    old=json.loads(old_bytes)
    report={'requirements':['CON-ARCH-006','OPS-ARCH-006'],'status':'incomplete','errors':[],
        'physical_qualified':False,'scope':'Retained D8 bonding disks vs verified new floor masks, actual normal/magnetic STL mass centroids; housing-only static contact hull.',
        'baseline':{'revision':'cc854a3','path':'hardware/MODELS/kc2_housing_manifest.json','raw_sha256':hashlib.sha256(old_bytes).hexdigest()},
        'parts':{},'source_sha256':{},'drawings':{}}
    for side in ['left','right']:
        genpath=REPORTS/f'{side}-generation.json'
        g=json.loads(genpath.read_text())
        floors=[wkt.loads(p) for p in g['lower_masks_wkt']]
        records=old['outputs'][side]['closed_floor']['printable_parts']
        assert len(floors)==len(records)
        body=''.join(p.svg(scale_factor=.1,fill_color=c) for p,c in zip(floors,['#dce6ed','#e7dfcf']))
        for floor,record in zip(floors,records):
            centers=record['silicone_feet']['centers_xy_mm']
            part='' if side=='left' else '_'+record['name']
            for suffix in ['', '_magnetic']:
                file=MODELS/f'kc2_{side}_lower_housing{part}{suffix}.stl'
                assert digest(file)==g['outputs'][side+'_lower'+suffix]['meshes'][file.name]['sha256'], 'STL differs from verified floor generation'
                mesh=trimesh.load_mesh(file)
                assert mesh.is_watertight and mesh.body_count==1, 'Invalid mass centroid input'
                result=check_feet(floor,centers,mesh.center_mass[:2])
                report['parts'][file.name]=result
                report['errors'].extend(file.name+': '+e for e in result['errors'])
                report['source_sha256'][file.relative_to(ROOT).as_posix()]=digest(file)
            for i,(x,y) in enumerate(centers,1):
                body+=f'<circle cx="{x}" cy="{y}" r="4" fill="none" stroke="blue" stroke-width=".2"/><text x="{x}" y="{y}" font-size="2">{record["name"]}-{i}</text>'
        footfile=MODELS/f'kc2_{side}_silicone_foot_layout.svg'
        footfile.write_text(svg_document(floors,body,'CURRENT enclosed floor; retained D8 bonding positions; underside Z=-2.20'),encoding='utf8')
        upperparts=[wkt.loads(p) for p in g['upper_part_plans_wkt']]
        upperbody=''.join(p.svg(scale_factor=.1,fill_color=c) for p,c in zip(upperparts,['#cfe5ed','#e7dfcf']))
        upperfile=MODELS/f'kc2_{side}_mx_upper_plan.svg'
        upperfile.write_text(svg_document(upperparts,upperbody,'CURRENT enclosed upper design mask; head recess see STEP; USB/POWER/RESET included'),encoding='utf8')
        report['source_sha256'][genpath.relative_to(ROOT).as_posix()]=digest(genpath)
        for path in [footfile,upperfile]:report['drawings'][path.relative_to(ROOT).as_posix()]=digest(path)
    section=MODELS/'kc2_mx_mounting_section.svg'
    original=subprocess.check_output(['git','show','cc854a3:hardware/MODELS/kc2_mx_mounting_section.svg'],cwd=ROOT).decode('utf8')
    note='<rect x="1" y="8" width="143" height="9" fill="#fff1aa"/><text x="3" y="11" font-size="2.3">HISTORICAL local receiver section only - NOT current wall/floor outline</text><text x="3" y="15" font-size="2.3">Current floor Z-2.20..-1.00; wall seat Z4.10. Use current STEP for enclosure.</text>'
    section.write_text(original.replace('</svg>',note+'</svg>'),encoding='utf8')
    report['drawings'][section.relative_to(ROOT).as_posix()]=digest(section)
    for path in [Path(__file__),ROOT/'tools/test_kc2_enclosure_feet.py']:
        report['source_sha256'][path.relative_to(ROOT).as_posix()]=digest(path)
    report['status']='pass' if not report['errors'] else 'failed'
    (REPORTS/'retained-feet-and-drawings.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
