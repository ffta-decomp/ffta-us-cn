import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import link_timeout_fix as fix


class LinkTimeoutFixTests(unittest.TestCase):
    def fixture(self):
        # Synthetic code envelope; never distribute original ROM bytes in tests.
        data = bytearray(fix.END)
        data[fix.OFFSET:fix.OFFSET + 4] = bytes.fromhex('46 29 05 d9')
        return bytes(data)

    def test_unknown_function_rejected_before_assembly(self):
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(ValueError, 'function differs'):
                fix.prepare(self.fixture(), self.fixture(), Path(out) / 'build')

    def test_modified_function_rejected(self):
        data = self.fixture()
        changed = bytearray(data)
        changed[fix.ENTRY] ^= 1
        with patch.object(fix, 'FUNCTION_SHA256', fix.sha(data[fix.ENTRY:fix.END])):
            with tempfile.TemporaryDirectory() as out:
                with self.assertRaisesRegex(ValueError, 'already modified'):
                    fix.prepare(data, changed, Path(out) / 'build')

    @unittest.skipUnless(shutil.which('arm-none-eabi-as') and shutil.which('arm-none-eabi-objcopy'),
                         'ARM binutils required')
    def test_source_assembly_and_pinned_fragment(self):
        import json
        data = self.fixture()
        with patch.object(fix, 'FUNCTION_SHA256', fix.sha(data[fix.ENTRY:fix.END])):
            with tempfile.TemporaryDirectory() as out:
                path, report = fix.prepare(data, data, Path(out) / 'build')
                manifest = json.loads(path.read_text())
                fragment = manifest['fragments'][0]
                self.assertEqual(Path(fragment['path']).read_bytes(), bytes.fromhex('fe 29'))
                self.assertEqual(fragment['rom_offset'], 0x4d78)
                self.assertEqual(fragment['reference_sha256'], hashlib.sha256(bytes.fromhex('46 29')).hexdigest())
                self.assertEqual(report['new_maximum'], 254)
                self.assertFalse(report['recovery_credit_eligible'])
