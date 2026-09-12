import sys,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import trimesh
from shapely import wkt,affinity
from shapely.ops import unary_union
from tools import generate_kc2_magnetic_housings as base
from tools.verify_kc2_filled_plate_contract import contract_plan,check_record
from tools.review_kc2_filled_mesh import audit_mesh
stage=root/'.codex-tmp/solid-filled-plates'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bindings={};records={};expected={};errors=[];results={};footprints={}
for side in ['left','right']:
 for kind in ['mx','choc_v1','deep_sea']:
  path=stage/f'{side}-{kind}.json';r=json.loads(path.read_text());records[side,kind]=r
  bindings.update(r['source_sha256']);bindings[path.relative_to(root).as_posix()]=digest(path)
  for name,sha in r['outputs'].items():bindings[(stage/name).relative_to(root).as_posix()]=sha
for p in [Path(__file__)]+[root/'tools'/n for n in ['review_kc2_filled_mesh.py','test_review_kc2_filled_mesh.py','verify_kc2_filled_plate_contract.py','test_verify_kc2_filled_plate_contract.py']]:
 bindings[p.relative_to(root).as_posix()]=digest(p)
for name,sha in bindings.items():assert digest(root/name)==sha,name
boards,_,transform=base.load_plans()
for (side,kind),record in records.items():
 print('Contract and actual mesh:',side,kind,flush=True)
 p=contract_plan(side,boards[side],kind);e=check_record(record,p);errors.extend(e)
 result=[]
 for part,rows in zip(record['parts'],p['parts']):
  mesh=trimesh.load_mesh(stage/part['stl'],process=True);item=audit_mesh(mesh,rows)
  item['stl']=part['stl'];result.append(item);errors.extend(item['errors'])
 footprints[side,kind]=unary_union([wkt.loads(item['footprint_wkt']) for item in result])
 gap=None
 if side=='right':
  gap=wkt.loads(result[0]['footprint_wkt']).distance(wkt.loads(result[1]['footprint_wkt']))
  if gap<.1997:errors.append(kind+' right split gap')
 results[side+'-'+kind]=dict(contract_errors=e,parts=result,right_split_gap_mm=gap)
joined={}
for kind in ['mx','choc_v1','deep_sea']:
 transformed={}
 for side in ['left','right']:
  raw=boards[side]['raw_bounds']
  transformed[side]=affinity.translate(affinity.scale(footprints[side,kind],xfact=-1,yfact=1,origin=(0,0)),xoff=raw[2]+(124.625 if side=='right' else 0),yoff=raw[1])
 gap=transformed['left'].distance(transformed['right']);overlap=transformed['left'].intersection(transformed['right']).area
 joined[kind]=dict(gap_mm=gap,overlap_mm2=overlap)
 if gap<.3 or overlap>1e-8:errors.append(kind+' joined gap')
for name,sha in bindings.items():assert digest(root/name)==sha,name
report=dict(status='failed' if errors else 'pass',requirements=['CON-ARCH-006','CON-ARCH-007'],
 errors=errors,source_sha256=bindings,results=results,joined=joined,physical_qualified=False,
 scope='Actual nine STL complete sections and independent six design contracts; STEP/native gates separate')
(stage/'mesh-contract-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(status=report['status'],errors=errors,joined=joined)),flush=True)
