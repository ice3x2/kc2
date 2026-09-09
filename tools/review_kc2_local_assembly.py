"""CON-ARCH-006/OPS-ARCH-006 full joined local-cover footprints and retained feet."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import trimesh
from shapely import affinity,wkt
from shapely.geometry import Point,MultiPoint
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/local-cover-build'
REPORT=ROOT/'docs/reports/local-covers-20260910'
BASELINE='cc854a3e0e0f25ab3d63e2916cb4b99a487b6536'


def original_transform(transform):
    return all(isinstance(transform.get(key),(int,float)) and math.isfinite(transform[key])
               and abs(transform[key]-expected)<1e-8 for key,expected in [('dx',124.625),('dy',0.)])


def check_join(left,right):
    gap=left.distance(right);overlap=left.intersection(right).area
    return {'minimum_gap_mm':gap,'overlap_mm2':overlap,
            'errors':[] if gap>=.30 and overlap<1e-8 else ['Joined covers collide or lack clearance']}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    REPORT.mkdir(parents=True,exist_ok=True)
    bound={};errors=[];global_shapes={};feet=[];intent=[];drawings={}
    def read(path):
        bound[path.relative_to(ROOT).as_posix()]=digest(path)
        return json.loads(path.read_text(encoding='utf8'))
    baseline_raw=subprocess.check_output(['git','show',BASELINE+':hardware/MODELS/kc2_housing_manifest.json'],cwd=ROOT)
    baseline=json.loads(baseline_raw)
    for side in ['left','right']:
        lower=read(STAGE/f'{side}-lower.json');upper=read(STAGE/f'{side}-upper.json')
        for group in ['lower','upper']:
            review=read(STAGE/f'{side}-{group}-review.json')
            if review['status']!='pass' or review['errors']:errors.append(side+group+' independent audit failed')
            for source,sha in review['source_sha256'].items():
                if digest(ROOT/source)!=sha:raise ValueError('Stale independent review: '+source)
                bound[source]=sha
        if not original_transform(upper['transform']):errors.append('Original joined transform changed')
        outline=wkt.loads(lower['outline_wkt'])
        local_lower=wkt.loads(lower['new_outline_wkt'])
        skirts=unary_union([wkt.loads(row['skirt_plan_wkt']) for row in upper['checks']])
        roofs=unary_union([wkt.loads(row['roof_plan_wkt']) for row in upper['checks']])
        whole=local_lower.union(skirts).union(roofs)
        raw=lower['raw_bounds']
        global_shapes[side]=affinity.translate(affinity.scale(whole,xfact=-1,yfact=1,origin=(0,0)),
            xoff=raw[2]+(124.625 if side=='right' else 0),yoff=raw[1])
        intent.append({'side':side,'local_lower_openings':lower['opening_count'],
            'lower_max_z_mm':2.5,'upper_skirt_min_z_mm':4.4,'pcb_bottom_top_mm':[2.5,4.1],
            'upper_skirt_clearance_above_pcb_mm':.3,'new_wall_to_wall_load_path':False,
            'lower_local_outline_added_mm2':local_lower.difference(outline).area,
            'upper_local_outline_added_mm2':roofs.difference(outline).area})
        for variant,row in lower['outputs'].items():
            for i,name in enumerate(sorted(row['meshes'])):
                path=STAGE/name;bound[path.relative_to(ROOT).as_posix()]=digest(path)
                if digest(path)!=row['meshes'][name]['sha256']:raise ValueError('Changed mesh')
                mesh=trimesh.load_mesh(path)
                positions=baseline['outputs'][side]['closed_floor']['printable_parts'][i]['silicone_feet']['centers_xy_mm']
                hull=MultiPoint(positions).convex_hull
                ok=hull.contains(Point(*mesh.center_mass[:2]))
                if not ok:errors.append(name+' bare housing centroid outside foot hull')
                feet.append({'stl':name,'centroid_mm':mesh.center_mass.tolist(),
                             'centers_xy_mm':positions,'inside_foot_hull':bool(ok)})
        # Plan comparison is an illustration of current actual-audited masks,
        # not a replacement for the independent STEP checks.
        x0,y0,x1,y1=whole.bounds
        svg=(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-2} {y0-2} {x1-x0+4} {y1-y0+9}">'
             +outline.svg(scale_factor=.15,fill_color='#dddddd')
             +wkt.loads(lower['floor_patch_wkt']).svg(scale_factor=.10,fill_color='#d87942')
             +roofs.svg(scale_factor=.08,fill_color='#348cba')
             +f'<text x="{x0}" y="{y1+5}" font-size="2">{side}: gray r5; orange lower local covers; blue upper local roof</text></svg>')
        target=REPORT/f'{side}-local-cover-plan.svg';target.write_text(svg,encoding='utf8')
        drawings[target.relative_to(ROOT).as_posix()]=digest(target)
    joined=check_join(global_shapes['left'],global_shapes['right']);errors.extend(joined['errors'])
    for path in [Path(__file__),ROOT/'tools/test_review_kc2_local_assembly.py']:
        bound[path.relative_to(ROOT).as_posix()]=digest(path)
    record={'requirements':['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],'status':'pass' if not errors else 'failed',
        'errors':errors,'physical_qualified':False,'new_fabrication_approval':False,'source_sha256':bound,
        'git_source_sha256':{BASELINE+':hardware/MODELS/kc2_housing_manifest.json':hashlib.sha256(baseline_raw).hexdigest()},
        'joined':joined,'original_right_transform_mm':{'dx':124.625,'dy':0},'intent':intent,'feet':feet,'drawings':drawings,
        'scope':'Combined independently audited local masks, original joined transform, bare-housing mesh centroid/retained feet. Exact cap/part, populated stability, print/strength/magnet and RF remain physical.'}
    (REPORT/'independent-review-final.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':record['status'],'joined':joined,'errors':errors}))
    return bool(errors)


if __name__=='__main__':raise SystemExit(main())
