"""CON-ARCH-006 / OPS-ARCH-006: legacy units never consume current CAD metadata."""
import unittest
from pathlib import Path
from unittest.mock import patch


class HistoricalHousingFixtureTests(unittest.TestCase):
    def test_historical_json_ignores_current_superseded_manifest(self):
        from tools import historical_housing_test_fixture as fixture
        with patch.object(Path, 'read_text', return_value='{"status":"superseded"}') as current_read:
            value = fixture.historical_json('kc2_housing_manifest.json')
        current_read.assert_not_called()
        self.assertEqual(set(value['outputs']), {'left', 'right'})
        self.assertEqual(fixture.BASELINE, 'cc854a3e0e0f25ab3d63e2916cb4b99a487b6536')
        self.assertFalse(value['order_ready'])


if __name__ == '__main__':
    unittest.main()
