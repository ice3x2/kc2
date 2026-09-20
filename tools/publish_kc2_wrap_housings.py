"""CON-ARCH-006/OPS-ARCH-006 source-bound complete sleeve publication.

Baseline CAD inputs remain in Git, not a second active model directory.
Portable evidence aliases retain their original source identities.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import re
from tools.kc2_wrap_native import jobs
from tools.kc2_pcb_seating import digest
from tools.kc2_step_whitespace import normalize

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT/'.codex-tmp/wrap-housing-20260920-r1'
REPORT = ROOT/'docs/reports/wrap-housings-20260920'
MANIFEST = ROOT/'hardware/MODELS/kc2_wrap_housing_manifest.json'
PARENT = ROOT/'hardware/MODELS/kc2_smooth_central_housing_manifest.json'
BASELINE = 'e0e8686'
LABELS = set(jobs())
RECORDS = ('mesh-review.json', 'cad-review.json', 'native-generation.json', 'native-review.json',
           'motion-review.json')
DOCUMENTS = ('hardware/MODELS/PRINT-wrap-housings.md', 'hardware/MODELS/README.md',
             'hardware/README.md', 'order.md', 'docs/reports/wrap-housings-20260920/README.md',
             'docs/reports/wrap-housings-20260920/REPRODUCE.md',
             'docs/reports/wrap-housings-20260920/assembly-section-left-mx.png',
             'docs/reports/wrap-housings-20260920/left-sleeve-preview.png')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def prepare_step(raw):
    return normalize(raw)


def source_bindings(record):
    value = record.get('source_sha256', {})
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value):
        # Per-job Fusion record: source STEP identity, not a path/hash map.
        # The enclosing native report and checkpoint bind this record's bytes.
        return {}
    raise ValueError('Malformed evidence source binding')


def incidental_local_inventory(name):
    """Unused local files swept up by make_plan's PCB preservation inventory.

    These were hashed, not parsed as geometry; do not publish private local
    Git configuration or autosaves as if they were CAD dependencies.
    Actual boards/projects and every unknown input remain hard-bound.
    """
    match = re.fullmatch(r'hardware/PCB/kc2_(left|right)/(.+)', name)
    if not match:
        return False
    side, tail = match.groups()
    return (tail in (f'kc2_{side}.kicad_prl', f'~kc2_{side}.kicad_pro.lck', 'fp-info-cache')
            or tail.startswith('.history/')
            or re.fullmatch(r'kc2_'+side+r'\.kicad_pcb\.bak-\d{8}-\d{6}', tail) is not None
            or re.fullmatch(r'kc2_'+side+r'-backups/kc2_'+side+r'-\d{4}-\d{2}-\d{2}_\d{6}\.zip', tail) is not None)


def validate_step(raw, canonical, record):
    expected, proof = prepare_step(raw)
    if expected != canonical or proof != record:
        raise ValueError('Canonical STEP differs from its lexical-only raw proof')


def validate_records(records):
    for name in RECORDS:
        row = records.get(name, {})
        field = 'outputs' if name == 'native-generation.json' else 'rows'
        if row.get('status') != 'pass' or row.get('errors') != [] or set(row.get(field, {})) != LABELS:
            raise ValueError('Incomplete actual sleeve evidence: '+name)
        if any(r.get('errors', []) for r in row[field].values()):
            raise ValueError('Failed job in '+name)
    for row in records['native-generation.json']['outputs'].values():
        if row.get('status') != 'pass' or row.get('round_trip_verified') is not True:
            raise ValueError('Missing F3D round trip')


def check_current(bindings):
    for name, sha in bindings.items():
        path = ROOT/name
        if not path.is_file() or digest(path) != sha:
            raise ValueError('Changed or missing release input: '+name)


def validate_tests(record):
    required = {'tools.test_kc2_wrap_wall_plan', 'tools.test_review_kc2_wrap_cad',
                'tools.test_review_kc2_wrap_housings', 'tools.test_review_kc2_wrap_native',
                'tools.test_publish_kc2_wrap_housings', 'tools.test_kc2_stl_tjunction',
                'tools.test_review_kc2_wrap_motion', 'tools.test_kc2_step_whitespace'}
    if (record.get('status') != 'pass' or record.get('tests', 0) <= 0 or
            record.get('failures') != 0 or record.get('errors') != 0 or
            not required.issubset(record.get('modules', []))):
        raise ValueError('Missing or failed regression evidence')


def validate_guide(text):
    if '<!-- kc2-wrap-guide: ready -->' not in text or '<!-- kc2-wrap-guide: pending -->' in text:
        raise ValueError('Current print guide is not finalized')


def publish():
    records = {name:read(STAGE/name) for name in RECORDS}
    validate_records(records)
    tests = read(STAGE/'tests.json')
    validate_tests(tests)
    validate_guide((ROOT/DOCUMENTS[0]).read_text(encoding='utf-8'))
    documents = {name:digest(ROOT/name) for name in DOCUMENTS}
    parent = read(PARENT)
    baseline = parent['outputs']
    check_current(baseline)
    preserved = parent['preserved_pcb_gerber_sha256']
    if len(baseline) != 35 or len(preserved) != 16:
        raise ValueError('Unexpected baseline inventory')
    check_current(preserved)
    commit = subprocess.check_output(['git','rev-parse',BASELINE], cwd=ROOT, text=True).strip()
    # Ensure Git is an exact recoverable baseline before any canonical writes.
    for name, sha in baseline.items():
        blob = subprocess.check_output(['git','show',commit+':'+name], cwd=ROOT)
        if hashlib.sha256(blob).hexdigest() != sha:
            raise ValueError('Git baseline does not match current model: '+name)
    evidence = {STAGE/name:REPORT/name for name in (*RECORDS, 'plan.json', 'board-envelopes.json', 'tests.json')}
    copies, outputs, aliases, step_publication, normalized_steps = {}, {}, {}, {}, {}
    proof_records = list(records.values())+[read(STAGE/'plan.json'),read(STAGE/'board-envelopes.json'),tests]
    observations = {name:sha for name,sha in source_bindings(read(STAGE/'plan.json')).items()
                    if incidental_local_inventory(name)}
    for label, job in jobs().items():
        folder = STAGE/job['folder']
        generation = read(folder/'generation.json')
        native = read(folder/'native-generation.json')
        if (generation.get('errors') != [] or generation.get('body_count') != job['body_count'] or
                generation.get('status') != 'generated_pending_independent_review' or
                native != records['native-generation.json']['outputs'][label]):
            raise ValueError('Incomplete generation chain: '+label)
        if (digest(folder/'generation.json') != native['generation_sha256'] or
                generation['outputs'][job['step']] != native['source_sha256'] or
                digest(folder/native['readback_step']) != native['readback_sha256']):
            raise ValueError('Stale native source chain: '+label)
        for name, sha in {**generation['outputs'],native['f3d']:native['f3d_sha256']}.items():
            source = folder/name
            if digest(source) != sha:
                raise ValueError('Changed staged model: '+name)
            target = ROOT/'hardware/MODELS'/name
            copies[target] = source
            outputs[target.relative_to(ROOT).as_posix()] = sha
            aliases[source.relative_to(ROOT).as_posix()] = target.relative_to(ROOT).as_posix()
            if target.suffix == '.step':
                normalized, proof = prepare_step(source.read_bytes())
                raw_target = REPORT/'raw-step'/(name+'.raw')
                evidence[source] = raw_target
                normalized_steps[target] = normalized
                outputs[target.relative_to(ROOT).as_posix()] = proof['normalized_sha256']
                step_publication[target.relative_to(ROOT).as_posix()] = dict(
                    raw_path=raw_target.relative_to(ROOT).as_posix(), proof=proof)
        for name in ('generation.json','native-generation.json',native['readback_step']):
            evidence[folder/name] = REPORT/job['folder']/name
        checkpoint = STAGE/'native-checkpoints'/(label.replace(':','-')+'.json')
        if not checkpoint.is_file():
            raise ValueError('Missing independent native checkpoint: '+label)
        evidence[checkpoint] = REPORT/'native-checkpoints'/checkpoint.name
        proof_records.append(generation)
    if set(outputs) != set(baseline) or len(copies) != 35:
        raise ValueError('Must replace all 35 housing outputs, not a partial set')
    for row in proof_records:
        check_current(source_bindings(row))
    evidence_hashes = {}
    for source, target in evidence.items():
        aliases[source.relative_to(ROOT).as_posix()] = target.relative_to(ROOT).as_posix()
        evidence_hashes[target.relative_to(ROOT).as_posix()] = digest(source)
    # No canonical file is touched before all inputs and evidence pass above.
    for source, target in evidence.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for target, source in copies.items():
        if target in normalized_steps:
            target.write_bytes(normalized_steps[target])
        else:
            shutil.copy2(source, target)
    manifest = dict(status='digitally_verified_physical_pending', physical_qualified=False,
        requirement_ids=['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'], baseline_revision=commit,
        baseline_outputs=baseline, outputs=outputs, preserved_pcb_gerber_sha256=preserved,
        evidence_sha256=evidence_hashes, logical_aliases=aliases,
        step_publication=step_publication,
        incidental_local_preservation_observations=observations,
        source_sha256={name:digest(ROOT/name) for name in
            ('tools/publish_kc2_wrap_housings.py','tools/test_publish_kc2_wrap_housings.py',
             'tools/kc2_step_whitespace.py','tools/test_kc2_step_whitespace.py')},
        documents_sha256=documents,
        dimensions=dict(pcb_bottom_mm=2.5, pcb_top_mm=4.1, wall_top_mm=5.6,
                        wall_thickness_mm=1.2, nominal_side_gap_mm=.3, upper_overlap_mm=1.2),
        magnets=parent['magnets'])
    MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return verify()


def verify():
    manifest = read(MANIFEST)
    if (manifest.get('status') != 'digitally_verified_physical_pending' or
            manifest.get('physical_qualified') is not False or len(manifest.get('outputs', {})) != 35 or
            len(manifest.get('preserved_pcb_gerber_sha256', {})) != 16):
        raise ValueError('Incomplete release manifest')
    for field in ('outputs','preserved_pcb_gerber_sha256','evidence_sha256','source_sha256','documents_sha256'):
        check_current(manifest[field])
    validate_guide((ROOT/DOCUMENTS[0]).read_text(encoding='utf-8'))
    validate_records({name:read(REPORT/name) for name in RECORDS})
    validate_tests(read(REPORT/'tests.json'))
    steps = {name for name in manifest['outputs'] if name.endswith('.step')}
    if len(steps) != 10 or set(manifest.get('step_publication', {})) != steps:
        raise ValueError('Missing canonical STEP normalization proofs')
    for name, row in manifest['step_publication'].items():
        validate_step((ROOT/row['raw_path']).read_bytes(), (ROOT/name).read_bytes(), row['proof'])
    baseline_cache = {}
    observations = manifest.get('incidental_local_preservation_observations', {})
    expected_observations = {name:sha for name,sha in source_bindings(read(REPORT/'plan.json')).items()
                             if incidental_local_inventory(name)}
    if observations != expected_observations:
        raise ValueError('Local preservation inventory classification differs')
    for name in manifest['evidence_sha256']:
        if not name.endswith('.json'):
            continue
        for source, sha in source_bindings(read(ROOT/name)).items():
            if source in observations:
                if observations[source] != sha:
                    raise ValueError('Historical local observation differs: '+source)
                continue
            resolved = ROOT/manifest['logical_aliases'].get(source, source)
            if resolved.is_file() and digest(resolved) == sha:
                continue
            if manifest['baseline_outputs'].get(source) != sha:
                raise ValueError('Portable evidence source differs: '+source)
            if source not in baseline_cache:
                blob = subprocess.check_output(['git','show',manifest['baseline_revision']+':'+source], cwd=ROOT)
                baseline_cache[source] = hashlib.sha256(blob).hexdigest()
            if baseline_cache[source] != sha:
                raise ValueError('Baseline source differs: '+source)
    return dict(status='pass', artifacts=len(manifest['outputs']), physical_qualified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    print(json.dumps(publish() if args.publish else verify()))
