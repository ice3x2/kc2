from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cadquery as cq

from tools import generate_kc2_component_models as generator


class Kc2ComponentModelTests(unittest.TestCase):
    def assert_no_trailing_whitespace(self, path: Path) -> None:
        for line_number, line in enumerate(path.read_bytes().splitlines(), start=1):
            self.assertEqual(
                line,
                line.rstrip(b" \t"),
                f"{path} line {line_number} has trailing whitespace",
            )

    def assert_imms_bounds(self, path: Path) -> None:
        model = cq.importers.importStep(str(path))
        bounds = model.val().BoundingBox()
        self.assertEqual(
            (round(bounds.xlen, 3), round(bounds.ylen, 3), round(bounds.zlen, 3)),
            generator.IMMS_BODY_SIZE_MM,
        )
        self.assertEqual(round(bounds.zmin, 3), 0.0)

    def test_imms_model_is_reproducible_and_encodes_the_controlled_envelope(self) -> None:
        self.assertEqual(generator.IMMS_ACTUATOR_TRAVEL_MM, 1.6)
        tracked = generator.OUTPUT_DIR / generator.IMMS_MODEL_NAME
        self.assertTrue(tracked.is_file())
        self.assert_no_trailing_whitespace(tracked)
        self.assert_imms_bounds(tracked)
        with TemporaryDirectory() as directory:
            generated = generator.generate_imms_model(Path(directory))
            self.assert_no_trailing_whitespace(generated)
            self.assert_imms_bounds(generated)


if __name__ == "__main__":
    unittest.main()
