import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import export_us_cn_glyph_table as glyphs
from export_us_cn import verify_export, verify_reference_components


class ExportTests(unittest.TestCase):
    def test_wrong_rom_is_rejected_before_glyph_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rom = root / 'input.gba'; rom.write_bytes(b'not a ROM')
            with self.assertRaisesRegex(ValueError, 'authenticated Chinese'):
                glyphs.export(rom, root / 'export')
            self.assertFalse((root / 'export').exists())

    def test_complete_native_inventory_and_unknown_unicode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = bytes(0x1000000)  # Synthetic blank cells, no game assets.
            rom = root / 'input.gba'; rom.write_bytes(image)
            with patch.object(glyphs, 'CN_SHA256', hashlib.sha256(image).hexdigest()):
                result = glyphs.export(rom, root / 'export')
            self.assertEqual(result['glyph_count'], 3175)
            self.assertEqual(result['unknown_unicode_glyphs'], 3175)
            self.assertTrue(all(row['unicode'] is None for row in result['glyphs']))
            self.assertEqual(len((root / 'export/font-4bpp.bin').read_bytes()), 3175 * 128)
            self.assertEqual(len((root / 'export/font-widths.bin').read_bytes()), 3175)

    def test_loader_and_first_screen_are_explicitly_checked(self):
        import struct
        reference = bytearray(0x1000000)
        for offset, value in [(0xa7fd40, 0x08a6d000), (0xa7fd48, 0x06000000),
                              (0xa7fd50, 0x84004b00)]:
            struct.pack_into('<I', reference, offset, value)
        layout = {'copy_calls': [], 'replacement_tables': {'identity_literals': {}, 'tables': []}}
        report = verify_reference_components(bytes(reference), bytes(reference), bytes(reference), layout)
        self.assertEqual(report['first_screen_bytes'], 76800)
        self.assertTrue(report['all_exact'])
        for offset, name in [(0x53bc, 'original-resource-loader'), (0xa6d000, 'first-screen-bitmap')]:
            changed = bytearray(reference); changed[offset] ^= 1
            with self.assertRaisesRegex(ValueError, name):
                verify_reference_components(bytes(reference), bytes(reference), bytes(changed), layout)

    def test_modified_export_is_rejected_before_rebuild(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'asset.bin').write_bytes(b'changed')
            (root / 'export-manifest.json').write_text(json.dumps({
                'files': {'asset.bin': hashlib.sha256(b'original').hexdigest()}}))
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                verify_export(root / 'unused.gba', root)


if __name__ == '__main__': unittest.main()
