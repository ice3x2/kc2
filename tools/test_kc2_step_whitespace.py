"""CON-ARCH-006 AC-9 lexical-only canonical STEP whitespace contract."""
import hashlib
import unittest
from tools.kc2_step_whitespace import normalize


def step(body=b"#1=POINT('name',(1.,2.,3.)); \t\r\n"):
    return b"ISO-10303-21;\r\nHEADER;\r\nENDSEC;\r\nDATA;\r\n"+body+b"ENDSEC;\r\nEND-ISO-10303-21;\r\n"


class StepWhitespace(unittest.TestCase):
    def test_only_trailing_ascii_space_tab_and_newlines_preserved(self):
        raw=step();out,r=normalize(raw)
        self.assertEqual(out,raw.replace(b'; \t\r\n',b';\r\n'))
        self.assertEqual(r['removed_bytes'],2);self.assertEqual(r['removed_lines'],1)
        self.assertEqual(r['raw_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(r['normalized_sha256'],hashlib.sha256(out).hexdigest())
        self.assertFalse(r['step_has_trailing_whitespace']);self.assertTrue(r['lexical_equivalence'])
        self.assertEqual(normalize(out)[0],out)

    def test_escaped_strings_binary_comments_and_numeric_tokens_unchanged(self):
        raw=step(b"#1=THING('it''s /*literal*/',\"0ABC\",1.E-5); \n/* comment */\t\r")
        out,_=normalize(raw)
        self.assertEqual(out,raw.replace(b'; \n',b';\n').replace(b'*/\t\r',b'*/\r'))
        for original,altered in ((b'1.E-5',b'1.E-4'),(b'#1=',b'#2='),(b"it''s",b"IT''s")):
            changed=raw.replace(original,altered)
            self.assertNotEqual(normalize(changed)[1]['normalized_sha256'],normalize(raw)[1]['normalized_sha256'])

    def test_protected_trailing_whitespace_cannot_be_stripped(self):
        for body in (b"#1=THING('abc \nend');\n",b'/* header \n comment */\n',b'#1=BITS("0A \nB");\n'):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):normalize(step(body))

    def test_unterminated_and_non_step_framing_rejected(self):
        for raw in (b'not STEP \n',step(b"#1='open;\n"),step(b'/* open\n'),step(b'#1="0AB\n'),
                    step().replace(b'DATA;',b'BOGUS;'),step()+b'junk',b''):
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(ValueError):normalize(raw)


if __name__=='__main__':unittest.main()
