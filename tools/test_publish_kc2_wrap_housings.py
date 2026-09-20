"""CON-ARCH-006/OPS-ARCH-006 reject incomplete sleeve releases."""
import copy
import unittest
from tools.publish_kc2_wrap_housings import validate_records, validate_tests, validate_guide, LABELS
from tools import publish_kc2_wrap_housings as publication


def complete_records():
    records = {name:dict(status='pass', errors=[], rows={k:{} for k in LABELS})
               for name in ('mesh-review.json','cad-review.json','native-review.json','motion-review.json')}
    records['native-generation.json'] = dict(status='pass', errors=[], outputs={
        k:dict(status='pass', errors=[], round_trip_verified=True) for k in LABELS})
    return records


class PublicationTests(unittest.TestCase):
    def test_local_preservation_inventory_cannot_exclude_design_inputs(self):
        for name in ('hardware/PCB/kc2_left/kc2_left.kicad_prl',
                     'hardware/PCB/kc2_right/~kc2_right.kicad_pro.lck',
                     'hardware/PCB/kc2_left/kc2_left.kicad_pcb.bak-20260906-095947',
                     'hardware/PCB/kc2_left/.history/.git/config'):
            self.assertTrue(publication.incidental_local_inventory(name))
        for name in ('hardware/PCB/kc2_left/kc2_left.kicad_pcb',
                     'hardware/PCB/kc2_left/kc2_left.kicad_pro',
                     'tools/something.py', 'hardware/GERBER/manifest.json',
                     'hardware/PCB/kc2_left/new_unknown_input.json'):
            self.assertFalse(publication.incidental_local_inventory(name))

    def test_native_scalar_source_hash_is_not_a_binding_map(self):
        self.assertEqual(publication.source_bindings({'source_sha256':'a'*64}), {})
        self.assertEqual(publication.source_bindings({'source_sha256':{'file':'b'*64}}), {'file':'b'*64})
        with self.assertRaises(ValueError):
            publication.source_bindings({'source_sha256':42})

    def test_step_publication_retains_raw_and_rejects_changed_geometry_or_proof(self):
        raw = b"ISO-10303-21; \nHEADER;ENDSEC;DATA;\n#1=THING(1.0); \t\nENDSEC;END-ISO-10303-21;\n"
        canonical, record = publication.prepare_step(raw)
        self.assertNotEqual(raw, canonical)
        publication.validate_step(raw, canonical, record)
        for changed_raw, changed_canonical, changed_record in (
                (raw.replace(b'1.0', b'2.0'), canonical, record),
                (raw, canonical.replace(b'1.0', b'2.0'), record),
                (raw, raw, record),
                (raw, canonical, dict(record, removed_bytes=0))):
            with self.assertRaises(ValueError):
                publication.validate_step(changed_raw, changed_canonical, changed_record)

    def test_missing_continuous_motion_evidence_cannot_publish(self):
        records = complete_records()
        records.pop('motion-review.json')
        with self.assertRaises(ValueError):
            validate_records(records)

    def test_pending_print_guide_cannot_be_published(self):
        with self.assertRaises(ValueError):
            validate_guide('<!-- kc2-wrap-guide: pending -->')
        with self.assertRaises(ValueError):
            validate_guide('old guide')
        validate_guide('<!-- kc2-wrap-guide: ready -->')

    def test_empty_or_failed_regression_evidence_rejected(self):
        for row in ({}, dict(status='pass', tests=0, failures=0, errors=0, modules=[]),
                    dict(status='pass', tests=54, failures=1, errors=0, modules=[])):
            with self.assertRaises(ValueError):
                validate_tests(row)

    def test_all_ten_jobs_required_in_every_review(self):
        records = complete_records()
        validate_records(records)
        for name in records:
            bad = copy.deepcopy(records)
            field = 'outputs' if name == 'native-generation.json' else 'rows'
            bad[name][field].pop('left:mx')
            with self.assertRaises(ValueError):
                validate_records(bad)

    def test_native_reopen_and_full_cad_are_mandatory(self):
        records = complete_records()
        records['native-generation.json']['outputs']['right:magnetic']['round_trip_verified'] = False
        with self.assertRaises(ValueError):
            validate_records(records)
        records = complete_records()
        records['cad-review.json']['errors'] = ['missing wall']
        with self.assertRaises(ValueError):
            validate_records(records)


if __name__ == '__main__':
    unittest.main()
