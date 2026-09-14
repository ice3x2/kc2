"""OPS-ARCH-006 transaction tests use disposable directories only."""
import json
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch
from tools import publish_kc2_registered_housings as p
from tools.test_kc2_registered_step_publication import STEP
from tools.kc2_step_whitespace import normalize

class TransactionTests(unittest.TestCase):
    def fixture(self,root):
        from tools.test_kc2_registered_guide import guide
        for target,source in p.inventory().items():
            for name,data in ((target,b'old'),(source,STEP if target.endswith('.step') else b'new')):
                file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
        old=root/p.OLD_MANIFEST;old.write_bytes(b'old manifest')
        preserved={f'hardware/PCB/p{i}':p.sha_bytes(b'pcb') for i in range(16)}
        for name in preserved:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'pcb')
        source='.codex-tmp/perimeter-wall-plans.json';(root/source).write_bytes(b'plan')
        docs={};bindings={source:dict(kind='workspace',path=source,sha256=p.sha_bytes(b'plan'),destination=p.destination(source))}
        for name in p.STEP_CODE:
            file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(Path(name).read_bytes())
            bindings[name]=dict(kind='workspace',path=name,sha256=p.sha_bytes(file.read_bytes()),destination=name)
        for name in p.step_sources():
            bindings[name]=dict(kind='workspace',path=name,sha256=p.sha_bytes(STEP),destination=p.destination(name))
        for target,staged in p.PUBLICATION_DOCS.items():
            data=(guide() if target==p.NEW_GUIDE else '[Current](PRINT-registered-housings.md) '+p.VERIFY_COMMAND+' PCB 하판 받침 외벽' if target=='hardware/MODELS/README.md' else '[Current](MODELS/PRINT-registered-housings.md)').encode()
            path=root/staged;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);docs[target]=p.sha_bytes(data)
            bindings[staged]=dict(kind='workspace',path=staged,sha256=p.sha_bytes(data),destination=target)
        (root/p.OLD_GUIDE).write_bytes(b'old guide');(root/'hardware/README.md').write_bytes(b'old entry point')
        (root/'hardware/MODELS/README.md').write_bytes(b'old models entry point')
        return dict(status='pass',errors=[],publication_authorized=True,inventory=p.inventory(),
          staged_output_sha256={n:p.sha_bytes(STEP if n.endswith('.step') else b'new') for n in p.inventory()},
          step_normalization=p.step_publication(lambda name:(root/name).read_bytes()),
          original_canonical_sha256={n:p.sha_bytes(b'old') for n in p.inventory()},preserved_pcb_gerber_sha256=preserved,
          report_paths={},bindings=bindings,document_sha256=docs)
    def test_pending_preflight_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(p,'preflight',return_value=dict(status='blocked',errors=['pending'])):
                with self.assertRaises(ValueError):p.publish(tmp)
            self.assertFalse(list(Path(tmp).iterdir()))
    def test_success_maps_single_active_copy_and_retires_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);gate=self.fixture(root)
            with patch.object(p,'preflight',return_value=gate),patch.object(p,'check_baseline_bytes',return_value=(gate['original_canonical_sha256'],gate['preserved_pcb_gerber_sha256'])),patch.object(p,'verify',return_value=dict(status='pass',errors=[])):
                result=p.publish(root)
            self.assertEqual(result['status'],'pass')
            self.assertTrue(all((root/n).read_bytes()==(normalize(STEP)[0] if n.endswith('.step') else b'new') for n in p.inventory()))
            retired=json.loads((root/p.OLD_MANIFEST).read_text())
            self.assertEqual(retired['status'],'superseded')
            self.assertEqual(retired['historical_revision'],p.BASELINE)
            self.assertFalse(any((root/p.REPORT/'evidence').rglob('*.step')))
            shutil.rmtree(root/'.codex-tmp')
            manifest=json.loads((root/p.NEW_MANIFEST).read_text())
            with patch.object(p,'baseline_inventory',return_value=gate['preserved_pcb_gerber_sha256']):
                self.assertEqual(p.verify_bytes(root,manifest)['status'],'pass')
                (root/p.OLD_MANIFEST).write_text('{"status":"pass"}')
                self.assertEqual(p.verify_bytes(root,manifest)['status'],'blocked')
    def test_failed_postverification_rolls_back_all_exact_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);gate=self.fixture(root)
            with patch.object(p,'preflight',return_value=gate),patch.object(p,'check_baseline_bytes',return_value=(gate['original_canonical_sha256'],gate['preserved_pcb_gerber_sha256'])),patch.object(p,'verify',return_value=dict(status='blocked',errors=['corrupt native'])):
                with self.assertRaises(ValueError):p.publish(root)
            self.assertTrue(all((root/n).read_bytes()==b'old' for n in p.inventory()))
            self.assertEqual((root/p.OLD_MANIFEST).read_bytes(),b'old manifest')
            self.assertFalse((root/p.NEW_MANIFEST).exists())
            self.assertEqual((root/p.OLD_GUIDE).read_bytes(),b'old guide')
            self.assertEqual((root/'hardware/README.md').read_bytes(),b'old entry point')
            self.assertEqual((root/'hardware/MODELS/README.md').read_bytes(),b'old models entry point')
    def test_changed_staged_output_is_rejected_before_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);gate=self.fixture(root)
            (root/next(iter(p.inventory().values()))).write_bytes(b'changed output')
            with patch.object(p,'preflight',return_value=gate),patch.object(p,'check_baseline_bytes',return_value=(gate['original_canonical_sha256'],gate['preserved_pcb_gerber_sha256'])),patch.object(p,'verify',return_value=dict(status='pass',errors=[])):
                with self.assertRaises(ValueError):p.publish(root)
            self.assertTrue(all((root/n).read_bytes()==b'old' for n in p.inventory()))
    def test_portable_resolver_distinguishes_old_canonical_and_new_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target,source=next((t,s) for t,s in p.inventory().items() if t.endswith('.f3d'))
            file=root/target;file.parent.mkdir(parents=True);file.write_bytes(b'new')
            manifest=dict(outputs={target:p.sha_bytes(b'new')},bindings={target:dict(kind='git_blob',revision=p.BASELINE,path=target,sha256=p.sha_bytes(b'old'))})
            with patch.object(p,'git_blob',return_value=b'old'):
                self.assertEqual(p.portable_read(root,manifest,target),b'old')
                self.assertEqual(p.portable_read(root,manifest,source),b'new')
            with self.assertRaises(ValueError):p.portable_read(root,manifest,'.codex-tmp/unknown.json')
    def test_portable_verify_never_bypasses_semantic_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(p,'verify_bytes',return_value=dict(status='pass',errors=[])),patch.object(p,'preflight',return_value=dict(status='blocked',errors=['missing magnet actual proof'])) as check:
                result=p.verify(tmp,{})
                self.assertEqual(result['status'],'blocked')
                self.assertIn('missing magnet actual proof',result['errors'])
                check.assert_called_once()
    def test_midtransaction_replace_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);gate=self.fixture(root);real=p.os.replace;calls=0
            def fail_once(source,target):
                nonlocal calls
                calls+=1
                if calls==9:raise OSError('simulated disk error')
                return real(source,target)
            with patch.object(p,'preflight',return_value=gate),patch.object(p,'check_baseline_bytes',return_value=(gate['original_canonical_sha256'],gate['preserved_pcb_gerber_sha256'])),patch.object(p.os,'replace',side_effect=fail_once):
                with self.assertRaises(OSError):p.publish(root)
            self.assertTrue(all((root/n).read_bytes()==b'old' for n in p.inventory()))
            self.assertEqual((root/p.OLD_MANIFEST).read_bytes(),b'old manifest')

if __name__=='__main__':unittest.main()
