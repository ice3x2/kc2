"""CON-ARCH-006: refresh source identity only after identical full extraction."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path

from tools import generate_kc2_x3_v2_housings as housing


def geometry_signature(data):
    normalized = copy.deepcopy(data)
    normalized.pop('path', None)
    battery = normalized.get('battery_above_carrier', {})
    battery.pop('source_board', None)
    battery.pop('source_board_sha256', None)
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def extract(paths, python):
    paths = {side:str(path.resolve()) for side,path in paths.items()}
    code = ('import json,pcbnew; from pathlib import Path; '
            'from tools import generate_kc2_x3_v2_housings as g; '
            f'g.BOARD_PATHS={{k:Path(v) for k,v in {paths!r}.items()}}; '
            'print(json.dumps({k:g.extract_board(pcbnew,v) for k,v in g.BOARD_PATHS.items()}))')
    result=subprocess.run([str(python),'-B','-c',code], cwd=housing.ROOT,
                          capture_output=True,text=True,check=True)
    return json.loads(result.stdout)


def rebind(old_paths, python, apply=False):
    scratch=housing.ROOT/'.codex-tmp'/f'housing-rebind-{uuid.uuid4().hex}'
    scratch.mkdir(parents=True)
    current={side:scratch/f'{side}.kicad_pcb' for side in housing.BOARD_PATHS}
    for side,path in current.items():
        shutil.copy2(housing.BOARD_PATHS[side],path)
    old,new=extract(old_paths,python),extract(current,python)
    manifest=json.loads(housing.MANIFEST_PATH.read_text(encoding='utf-8'))
    evidence={}
    for side in ('left','right'):
        old_hash=housing.sha256_file(old_paths[side])
        new_hash=housing.sha256_file(current[side])
        output=manifest['outputs'][side]
        if output['battery_above_carrier']['source_board_sha256'] != old_hash:
            raise RuntimeError(f'{side}: supplied old board does not bind the generated extraction')
        if geometry_signature(old[side]) != geometry_signature(new[side]):
            raise RuntimeError(f'{side}: geometric extraction changed; full regeneration required')
        if housing.sha256_file(housing.BOARD_PATHS[side]) != new_hash:
            raise RuntimeError(f'{side}: canonical board changed during comparison')
        evidence[side]=dict(old_source_sha256=old_hash,new_source_sha256=new_hash,
                            identical_full_extraction_sha256=geometry_signature(new[side]))
    if apply:
        shutil.copy2(housing.MANIFEST_PATH,scratch/housing.MANIFEST_PATH.name)
        for side,record in evidence.items():
            output=manifest['outputs'][side]
            output['source_board_sha256']=record['new_source_sha256']
            output['battery_above_carrier']['source_board_sha256']=record['new_source_sha256']
        manifest['source_rebinding_evidence']=evidence
        housing.MANIFEST_PATH.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    result=dict(requirement='CON-ARCH-006',applied=apply,order_ready=False,evidence=evidence,
                note='Only manifest source identities changed; STEP and STL bytes untouched')
    (scratch/'evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-left',type=Path,required=True)
    parser.add_argument('--old-right',type=Path,required=True)
    parser.add_argument('--kicad-python',type=Path,default=Path('C:/Program Files/KiCad/10.0/bin/python.exe'))
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(rebind({'left':args.old_left,'right':args.old_right},args.kicad_python,args.apply),indent=2))


if __name__=='__main__':
    main()
