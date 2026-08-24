from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.canonical_hash import HASH_POLICY, sha256_bytes, sha256_file


class CanonicalHashTests(unittest.TestCase):
    def test_policy_name_is_stable(self) -> None:
        self.assertEqual(HASH_POLICY, "lf-normalized-utf8-text-else-raw-v1")

    def test_utf8_text_line_endings_have_one_digest(self) -> None:
        expected = sha256_bytes(b"alpha\nbeta\n")
        self.assertEqual(sha256_bytes(b"alpha\r\nbeta\r\n"), expected)
        self.assertEqual(sha256_bytes(b"alpha\rbeta\r"), expected)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.txt"
            path.write_bytes(b"alpha\r\nbeta\r\n")
            self.assertEqual(sha256_file(path), expected)

    def test_binary_and_actual_text_mutations_remain_distinct(self) -> None:
        binary = b"prefix\x00line\r\n"
        self.assertEqual(sha256_bytes(binary), hashlib.sha256(binary).hexdigest())
        self.assertNotEqual(sha256_bytes(b"alpha\n"), sha256_bytes(b"alpHa\n"))
        self.assertNotEqual(sha256_bytes(b"alpha\n"), sha256_bytes(b"alpha\n\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
