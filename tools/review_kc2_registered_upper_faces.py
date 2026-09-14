"""CON-ARCH-006 same independent contract, actual face-wire section backend.

Historical classifier-based reviewer and its completed evidence stay unchanged.
This explicit runner freezes the additional backend before/after execution.
"""
from pathlib import Path
from contextlib import contextmanager
import argparse,json,hashlib
from tools.kc2_actual_sections import section_geometry,audit_prismatic_solid

ROOT=Path(__file__).resolve().parents[1]
@contextmanager
def use_backend(module):
    old=(module.section_geometry,module.audit_prismatic_solid)
    module.section_geometry=section_geometry;module.audit_prismatic_solid=audit_prismatic_solid
    try:yield
    finally:module.section_geometry,module.audit_prismatic_solid=old

def review(side,kind):
    from tools import review_kc2_registered_upper as contract
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    files=[Path(__file__),ROOT/'tools/test_review_kc2_registered_upper_faces.py',ROOT/'tools/kc2_actual_sections.py',ROOT/'tools/test_kc2_actual_sections.py']
    before={p.relative_to(ROOT).as_posix():digest(p) for p in files}
    with use_backend(contract):result=contract.review(side,kind)
    if before!={p.relative_to(ROOT).as_posix():digest(p) for p in files}:raise ValueError('Changed actual section backend')
    result['source_sha256'].update(before);result['section_backend']='actual BRep face outer/inner wire topology with kernel area cross-check'
    path=ROOT/'.codex-tmp/registered-housing-fit/upper'/(side+'-'+kind)/'brep-review.json'
    path.write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('side');p.add_argument('kind');a=p.parse_args()
    raise SystemExit(0 if review(a.side,a.kind)['status']=='pass' else 1)
