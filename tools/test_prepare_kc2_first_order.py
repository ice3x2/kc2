"""OPS-ARCH-007 first-product release gate: physical pending is not digital pass."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import prepare_kc2_first_order as release

ROOT = Path(__file__).resolve().parents[1]


class FirstOrderGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for rel in release.required_inputs():
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dst)
        review = self.root / 'review.txt'
        review.write_text('Synthetic reviewed fixture; never production authorization.', encoding='utf-8')
        self.evidence = {
            'schema_version': 1, 'target': 'kc2-x3-v2',
            'selected_switch_assembly': 'mx_receptacle_with_plate',
            'known_blockers': [], 'digital_errors': [],
            'checks': dict.fromkeys(release.CHECKS, True),
            'reviews': {key: ['review.txt'] for key in release.REVIEWS},
            'bindings': {rel: release.sha256(self.root / rel) for rel in release.required_inputs()},
            'residual_risks': ['Supplier barrel and finished-hole tolerances unknown; nominal clearance 0.15 mm is not worst-case fit.'],
            'post_receipt_acceptance': ['Physical insertion, soldering, torque, powered scan and RF pending.'],
        }
        self.evidence['bindings']['review.txt'] = release.sha256(review)
        # Typed synthetic machine records; never actual physical qualification.
        self.evidence['digital_reports'] = {}
        for role in ('board', 'housing'):
            sources = {}
            for rel in release.digital_report_inputs(role):
                path = self.root / rel
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('Synthetic source fixture only', encoding='utf-8')
                sources[rel] = release.sha256(path)
                self.evidence['bindings'][rel] = sources[rel]
            report = {'requirement': 'CON-ARCH-004' if role == 'board' else 'CON-ARCH-006',
                      'errors': [], 'source_sha256': sources}
            if role == 'board':
                report.update(connectivity_errors={'left': [], 'right': []}, boards={
                    side: {'drc_violation_count': 0, 'drc_unconnected_count': 0}
                    for side in ('left', 'right')})
            else:
                report.update(digital_valid=True, native_archive_blockers=[],
                              qualification_blockers=['Synthetic physical acceptance pending'],
                              closed_floor={'digital_valid':True,'errors':[],
                                'floor_thickness_mm':1.2,'floor_top_z_mm':-1.0,'floor_bottom_z_mm':-2.2,
                                'bonding_pad_diameter_mm':8,'bonding_pad_count':12,'printable_part_count':3})
            rel = f'{role}-machine.json'
            path = self.root / rel
            path.write_text(json.dumps(report), encoding='utf-8')
            self.evidence['digital_reports'][role] = rel
            self.evidence['bindings'][rel] = release.sha256(path)
            self.evidence['reviews']['digital_verification'].append(rel)

    def test_reviewed_current_outputs_allow_build_with_physical_pending(self):
        result = release.validate(self.evidence, self.root)
        self.assertEqual([], result['errors'])
        self.assertTrue(result['eligible_to_build'])
        self.assertFalse(result['physical_qualification_complete'])
        self.assertFalse(result['first_order_ready'])
        self.assertEqual((62, 78), tuple(result['sides'][s]['bom']['mx_receptacles']['quantity'] for s in ('left', 'right')))

    def test_each_check_and_missing_review_ref_fail_closed(self):
        for key in release.CHECKS:
            with self.subTest(check=key):
                candidate = copy.deepcopy(self.evidence)
                candidate['checks'][key] = False
                self.assertFalse(release.validate(candidate, self.root)['eligible_to_build'])
        for key in release.REVIEWS:
            candidate = copy.deepcopy(self.evidence)
            candidate['reviews'][key] = []
            self.assertFalse(release.validate(candidate, self.root)['eligible_to_build'])

    def test_stale_source_or_output_or_review_blocks(self):
        for rel in (release.required_inputs()[0], release.raw_inputs('left')[0], 'review.txt'):
            with self.subTest(path=rel):
                candidate = copy.deepcopy(self.evidence)
                candidate['bindings'][rel] = '0' * 64
                self.assertFalse(release.validate(candidate, self.root)['eligible_to_build'])

    def test_missing_npth_and_known_fit_error_block_without_output(self):
        (self.root / release.RAW / 'left/kc2_left-NPTH.drl').unlink()
        self.evidence['known_blockers'] = ['Known pin interference']
        output = self.root / 'hardware/kicad/first_order/test'
        with self.assertRaises(ValueError):
            release.build(self.evidence, self.root, output)
        self.assertFalse(output.exists())

    def test_rebound_invalid_drill_and_drc_still_fail(self):
        for rel, payload in ((f'{release.RAW}/left/kc2_left-PTH.drl', b'M48\nMETRIC\n%\nM30\n'),
                             ('hardware/kicad/kc2_left/kc2_left.drc.json', b'{"violations":[{"severity":"error"}],"unconnected_items":[]}')):
            path = self.root / rel
            original = path.read_bytes()
            path.write_bytes(payload)
            candidate = copy.deepcopy(self.evidence)
            candidate['bindings'][rel] = release.sha256(path)
            self.assertFalse(release.validate(candidate, self.root)['eligible_to_build'])
            path.write_bytes(original)

    def test_fabrication_only_zip_bytes_and_no_overwrite(self):
        output = self.root / 'hardware/kicad/first_order/test'
        manifest = release.build(self.evidence, self.root, output)
        self.assertTrue(manifest['first_order_ready'])
        self.assertFalse(manifest['physical_qualification_complete'])
        self.assertFalse(manifest['bom_cpl_upload_authorization'])
        self.assertEqual([], release.verify_package(output))
        with self.assertRaises(FileExistsError):
            release.build(self.evidence, self.root, output)
        archive = output / 'kc2_left-pcb-fabrication-only.zip'
        archive.write_bytes(b'corrupted')
        self.assertTrue(release.verify_package(output))

    def test_empty_evidence_and_unsafe_paths_are_rejected(self):
        self.assertFalse(release.validate({}, self.root)['eligible_to_build'])
        self.evidence['bindings']['../outside'] = '0' * 64
        self.assertFalse(release.validate(self.evidence, self.root)['eligible_to_build'])

    def test_rebound_stale_drc_sidecar_is_not_accepted(self):
        rel = 'hardware/kicad/kc2_drc_evidence.json'
        path = self.root / rel
        data = json.loads(path.read_text(encoding='utf-8'))
        data['boards']['left']['board_sha256'] = '0' * 64
        path.write_text(json.dumps(data), encoding='utf-8')
        self.evidence['bindings'][rel] = release.sha256(path)
        self.assertFalse(release.validate(self.evidence, self.root)['eligible_to_build'])

    def test_package_cannot_relabel_extra_bom_as_fabrication(self):
        from zipfile import ZipFile
        output = self.root / 'hardware/kicad/first_order/test'
        manifest = release.build(self.evidence, self.root, output)
        archive = output / manifest['packages']['left']['file']
        with ZipFile(archive, 'a') as package:
            package.writestr('machine-assembly-bom.csv', 'not authorized')
        import hashlib
        manifest['packages']['left']['entries']['machine-assembly-bom.csv'] = hashlib.sha256(b'not authorized').hexdigest()
        manifest['packages']['left']['sha256'] = release.sha256(archive)
        manifest['output_sha256'][archive.name] = release.sha256(archive)
        (output / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(release.verify_package(output))

    def test_package_cannot_omit_manual_bom_binding(self):
        output = self.root / 'hardware/kicad/first_order/test'
        manifest = release.build(self.evidence, self.root, output)
        name = 'kc2_left-manual-mx-bom.json'
        del manifest['output_sha256'][name]
        (output / name).unlink()
        (output / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(release.verify_package(output))

    def test_package_rejects_machine_placement_claim(self):
        output = self.root / 'hardware/kicad/first_order/test'
        manifest = release.build(self.evidence, self.root, output)
        manifest['machine_placement_requested'] = True
        (output / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.assertTrue(release.verify_package(output))


if __name__ == '__main__':
    unittest.main()
