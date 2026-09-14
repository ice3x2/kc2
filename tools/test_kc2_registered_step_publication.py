"""CON-ARCH-006 / OPS-ARCH-006 normalized delivery preserves raw CAD evidence."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import publish_kc2_registered_housings as p

STEP=b"ISO-10303-21;\r\nHEADER;\r\nENDSEC;\r\nDATA;\r\n#1=TEST(1.0,'unchanged'); \t\r\nENDSEC;\r\nEND-ISO-10303-21;\r\n"

class StepPublicationTests(unittest.TestCase):
    def fixture(self):
        mapping=p.step_sources()
        raw={source:STEP for source in mapping}
        for name in p.STEP_CODE:raw[name]=Path(name).read_bytes()
        return raw,p.step_publication(raw.__getitem__)

    def test_exact_ten_source_mapping_and_no_second_editable_step(self):
        mapping=p.step_sources()
        self.assertEqual(len(mapping),10)
        self.assertEqual(set(mapping),{s for t,s in p.inventory().items() if t.endswith('.step')})
        self.assertEqual(len({r['raw_destination'] for r in mapping.values()}),10)
        for source,row in mapping.items():
            self.assertTrue(row['raw_destination'].endswith('.step.raw'))
            self.assertEqual(p.destination(source),row['raw_destination'])
            self.assertEqual(p.inventory()[row['target']],source)

    def test_portable_raw_source_and_normalized_output_remain_distinct(self):
        from tools.kc2_step_whitespace import normalize
        raw,records=self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outputs={};bindings={}
            for source,row in records.items():
                normalized,_=normalize(raw[source])
                target=root/row['target'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(normalized)
                archive=root/row['raw_destination'];archive.parent.mkdir(parents=True,exist_ok=True);archive.write_bytes(raw[source])
                outputs[row['target']]=p.sha_bytes(normalized)
                bindings[source]=dict(kind='workspace',path=source,destination=row['raw_destination'],sha256=p.sha_bytes(raw[source]))
            for name in p.STEP_CODE:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw[name])
            manifest=dict(outputs=outputs,bindings=bindings,step_normalization=records)
            p.verify_step_publication(root,manifest)
            source=next(iter(records));row=records[source]
            self.assertEqual(p.portable_read(root,manifest,source),STEP)
            self.assertNotEqual((root/row['target']).read_bytes(),STEP)
            # Editing a number and updating only the advertised hash is rejected.
            changed=(root/row['target']).read_bytes().replace(b'1.0',b'2.0')
            (root/row['target']).write_bytes(changed)
            manifest['outputs'][row['target']]=p.sha_bytes(changed)
            with self.assertRaises(ValueError):p.verify_step_publication(root,manifest)

    def test_missing_row_wrong_mapping_and_raw_tamper_rejected(self):
        raw,records=self.fixture()
        source=next(iter(records))
        for mutate in ('missing','mapping','raw','boolean-count','boolean-proof'):
            bad=copy.deepcopy(records);data=dict(raw)
            if mutate=='missing':del bad[source]
            elif mutate=='mapping':bad[source]['raw_destination']='hardware/MODELS/other.step'
            elif mutate=='boolean-count':bad[source]['removed_lines']=True
            elif mutate=='boolean-proof':bad[source]['lexical_equivalence']=1
            else:data[source]=STEP.replace(b'1.0',b'2.0')
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                p.check_step_records(bad,data.__getitem__)

if __name__=='__main__':unittest.main()
