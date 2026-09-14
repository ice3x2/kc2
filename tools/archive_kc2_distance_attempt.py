"""CON-ARCH-006 preserve interrupted pre-performance distance attempt, not approval."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def run():
    stage=ROOT/'.codex-tmp/registered-housing-fit'
    folder=stage/'lower-development/component-distance-attempt-1'
    folder.mkdir(parents=True,exist_ok=True)
    paths=[ROOT/'tools'/name for name in ('review_kc2_lower_component_distance.py','kc2_solid_clearance.py','test_kc2_solid_clearance.py')]
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    originals={};archives={}
    for source in paths:
        target=folder/source.name;sha=digest(source)
        if target.exists() and digest(target)!=sha:raise ValueError('Conflicting immutable attempt snapshot')
        if not target.exists():shutil.copy2(source,target)
        originals[source.relative_to(ROOT).as_posix()]=sha
        archives[target.relative_to(ROOT).as_posix()]=sha
    failed=stage/'lower/right-void-review.json'
    failure_sha=digest(failed)
    result=dict(requirements=['CON-ARCH-006'],status='interrupted_not_accepted',session_id=76514,process_id=29104,
        verified_process_command='"C:\\Python312\\python.exe" -B -m tools.review_kc2_lower_component_distance',
        original_source_sha256=originals,archived_source_sha256=archives,
        failed_boolean_report=failed.relative_to(ROOT).as_posix(),failed_boolean_sha256=failure_sha,
        observed_output=['construct exact required tool; no Boolean intersections','fresh actual solid-solid distance normal',
                         'normal 0 0 solid_solid_extrema 0.0251747721199914','normal 0 2 solid_solid_extrema 0.0'],
        observed_completed_pairs=[dict(variant='normal',part=0,tool=0,distance_mm=.0251747721199914),
                                  dict(variant='normal',part=0,tool=2,distance_mm=0.)],
        note='Only emitted progress is known; full612pair inventory never completed or approved. Exact owned PID stopped before performance-only solver-call correction.',
        physical_qualified=False,source_sha256={Path(__file__).relative_to(ROOT).as_posix():digest(Path(__file__)),**archives})
    report=folder/'interrupted.json'
    if report.exists():raise ValueError('Interrupted evidence already recorded')
    report.write_text(json.dumps(result,indent=2)+'\n')
    print(report.relative_to(ROOT).as_posix())
    return result


if __name__=='__main__':run()
