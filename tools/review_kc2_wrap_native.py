"""CON-ARCH-006 independent native BRep audit with source-identical checkpoints.

An available-job run is explicitly partial. Full release requires all ten
current archives and their actual source/readback geometry comparisons.
"""
import json
import argparse
from pathlib import Path
from tools.kc2_wrap_native import jobs, preflight, STAGE
from tools.kc2_pcb_seating import digest
from tools.kc2_flat_central_native import compare_cad_signatures, validate_native_output
from tools.review_kc2_flat_central_native import _signature

ROOT = Path(__file__).resolve().parents[1]


def review_status(labels, errors):
    return 'failed' if errors else 'pass' if set(labels) == set(jobs()) else 'partial'


def reusable_native(record, bindings, count):
    row = record.get('row', {})
    return (record.get('status') == 'pass' and record.get('source_sha256') == bindings and
            row.get('errors') == [] and len(row.get('parts', [])) == count and
            all(p.get('errors') == [] for p in row['parts']))


def review(available=False):
    import cadquery as cq
    root = ROOT
    sources = ('tools/review_kc2_wrap_native.py', 'tools/test_review_kc2_wrap_native.py',
               'tools/kc2_wrap_native.py', 'tools/test_kc2_wrap_native.py',
               'tools/fusion/KC2WrapHousings.py', 'tools/kc2_flat_central_native.py',
               'tools/review_kc2_flat_central_native.py',
               'tools/fusion/KC2FlatCentralToF3D/KC2FlatCentralToF3D.py')
    bindings = {name:digest(root/name) for name in sources}
    master_path = root/STAGE/'native-generation.json'
    master = json.loads(master_path.read_text())
    if (master.get('errors') or master.get('status') not in ('partial', 'pass') or
            not set(master.get('outputs', {})).issubset(jobs()) or
            (not available and (master['status'] != 'pass' or set(master['outputs']) != set(jobs())))):
        raise ValueError('Incomplete or running Fusion generation')
    code_bindings = dict(bindings)
    bindings[master_path.relative_to(root).as_posix()] = digest(master_path)
    rows, errors = {}, []
    for label in jobs():
        if available and label not in master['outputs']:
            continue
        job = preflight(root, label); folder = job['folder']
        native_path = folder/'native-generation.json'
        native = json.loads(native_path.read_text())
        if (native != master['outputs'][label] or native.get('status') != 'pass' or
                native.get('errors') or native.get('round_trip_verified') is not True):
            raise ValueError('Native record chain differs: '+label)
        f3d = folder/native['f3d']; readback = folder/native['readback_step']
        if (native['source_sha256'] != job['source_sha256'] or
                native['generation_sha256'] != job['generation_sha256'] or
                digest(f3d) != native['f3d_sha256'] or digest(readback) != native['readback_sha256']):
            raise ValueError('Stale native hash chain: '+label)
        identity_errors = validate_native_output(native['source_bodies'], native['reopened_bodies'])
        if identity_errors:
            raise ValueError('Native reopen identity failed: '+label)
        job_bindings = dict(code_bindings)
        for path in (job['source'],job['generation_path'],native_path,f3d,readback):
            job_bindings[path.relative_to(root).as_posix()] = digest(path)
        bindings.update(job_bindings)
        checkpoint = root/STAGE/'native-checkpoints'/(label.replace(':','-')+'.json')
        cached = json.loads(checkpoint.read_text()) if checkpoint.is_file() else {}
        if reusable_native(cached, job_bindings, job['body_count']):
            row = cached['row']
            print('source-identical native BRep checkpoint', label, flush=True)
        else:
            print('import actual native source/readback', label, flush=True)
            source = cq.importers.importStep(str(job['source'])).solids().vals()
            revised = cq.importers.importStep(str(readback)).solids().vals()
            if (len(source) != job['body_count'] or len(revised) != job['body_count'] or
                    any(not s.isValid() for s in source+revised)):
                raise ValueError('Native BRep body count/validity failed: '+label)
            unmatched = list(revised); parts = []
            for index, solid in enumerate(source):
                actual = min(unmatched, key=lambda other:(other.Center()-solid.Center()).Length)
                unmatched.remove(actual)
                before = _signature(solid); after = _signature(actual)
                part_errors = compare_cad_signatures(before, after)
                parts.append(dict(part=index, source=before, readback=after, errors=part_errors))
            part_errors = [message for p in parts for message in p['errors']]
            row = dict(status='pass' if not part_errors else 'failed', errors=part_errors,
                       parts=parts, f3d_sha256=digest(f3d), readback_sha256=digest(readback))
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps(dict(status=row['status'], source_sha256=job_bindings,
                                  row=row), indent=2)+'\n', encoding='utf-8')
        rows[label] = row
        errors.extend(label+': '+message for message in row['errors'])
        bindings[checkpoint.relative_to(root).as_posix()] = digest(checkpoint)
        print('independent native BRep', label, row['status'], flush=True)
    for name, sha in bindings.items():
        if digest(root/name) != sha:
            raise ValueError('Native auditor source changed: '+name)
    result = dict(status=review_status(rows, errors), errors=errors, rows=rows,
                  source_sha256=bindings, physical_qualified=False,
                  requirements=['CON-ARCH-006','OPS-ARCH-006'])
    filename = 'native-review.partial.json' if available else 'native-review.json'
    (root/STAGE/filename).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--available', action='store_true')
    args = parser.parse_args()
    result = review(args.available)
    raise SystemExit(result['status'] == 'failed' or (not args.available and result['status'] != 'pass'))
