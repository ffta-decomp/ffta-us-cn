"""Synthetic assets exercise detection, bounded writes and packaging order."""
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import splash_author as splash
from package_rom import package
from ips_patch import encode_patch, apply_patch


class SplashAuthorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = bytearray(0x1000000)
        self.image[0xec:0xf0] = splash.ENTRY
        self.image[splash.STARTUP] = 0x12
        rows = []
        for i, c in enumerate('开发者：bhe'):
            cell = bytearray(128)
            cell[8] = 0x23  # Native foreground and shadow, one row.
            self.image[splash.FONT + i * 128:splash.FONT + (i + 1) * 128] = cell
            self.image[splash.WIDTHS + i] = 8
            rows.append(dict(index=i, unicode=c, advance=8, glyph_sha256=splash.sha(cell)))
        self.table = self.root / 'table.json'
        self.table.write_text(json.dumps(dict(glyphs=rows)))
        self.author = self.root / 'author.txt'
        self.author.write_text('开发者：bheeee\n', encoding='utf-8')
        x, y, w, h = splash.CAPTION
        bitmap = self.image[splash.BITMAP:splash.BITMAP + splash.BITMAP_BYTES]
        protected = b''.join(bitmap[row * 480:row * 480 + x * 2] +
            bitmap[row * 480 + (x + w) * 2:(row + 1) * 480]
            if y <= row < y + h else bitmap[row * 480:(row + 1) * 480]
            for row in range(160))
        for name, value in [('TABLE', self.table), ('STARTUP_SHA', splash.sha(
                self.image[splash.STARTUP:splash.STARTUP + splash.STARTUP_BYTES])),
                ('PROTECTED_SHA', splash.sha(protected))]:
            mock = patch.object(splash, name, value)
            mock.start(); self.addCleanup(mock.stop)

    def test_detect_and_change_only_caption_pixels_with_native_glyphs(self):
        image, report = splash.stamp(self.image, self.author)
        self.assertTrue(report['applied'])
        self.assertEqual(report['text'], '开发者：bheeee')
        self.assertEqual(image[:splash.BITMAP], self.image[:splash.BITMAP])
        end = splash.BITMAP + splash.BITMAP_BYTES
        self.assertEqual(image[end:], self.image[end:])
        x, y, w, h = splash.CAPTION
        for i in range(splash.BITMAP, end, 2):
            pixel = (i - splash.BITMAP) // 2
            if image[i:i + 2] != self.image[i:i + 2]:
                self.assertTrue(x <= pixel % 240 < x + w and y <= pixel // 240 < y + h)
        foreground = splash.BITMAP + ((y + 4) * 240 + x + 4) * 2
        self.assertEqual(struct.unpack_from('<H', image, foreground)[0], 0)
        self.assertEqual(struct.unpack_from('<H', image, foreground + 2)[0], 0x7fff)
        self.assertEqual(struct.unpack_from('<H', image, foreground + 4)[0], 0x7fff)
        # A distant point inside the reserved caption area keeps its artwork.
        untouched = splash.BITMAP + ((y + 15) * 240 + x + w - 3) * 2
        self.assertEqual(image[untouched:untouched + 2], self.image[untouched:untouched + 2])

    def test_repeated_packaging_with_same_author_is_idempotent(self):
        first, _ = splash.stamp(self.image, self.author)
        repeated, _ = splash.stamp(first, self.author)
        self.assertEqual(first, repeated)

    def test_english_and_disabled_paths_do_not_read_author(self):
        english = bytes(0x1000000)
        for image, enabled in [(english, True), (self.image, False)]:
            result, report = splash.stamp(image, self.root / 'missing.txt', enabled=enabled)
            self.assertEqual(result, image)
            self.assertFalse(report['applied'])

    def test_corrupt_patch_and_modified_group_credits_fail(self):
        for offset in [0xec, splash.STARTUP, splash.BITMAP]:
            broken = bytearray(self.image); broken[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, 'CN'):
                splash.stamp(broken, self.author)

    def test_invalid_text_and_unknown_glyphs_fail_without_output(self):
        rom = self.root / 'input.gba'; rom.write_bytes(self.image)
        for text in ['', 'bhe\ne', '🙂', 'e' * 40]:
            self.author.write_text(text, encoding='utf-8')
            out = self.root / 'rejected'
            with self.subTest(text=text), self.assertRaises(ValueError):
                package(rom, out, self.author)
            self.assertFalse(out.exists())

    def test_ips_applied_before_detection_and_zip_is_deterministic(self):
        english = bytes(0x1000000)
        rom = self.root / 'english.gba'; rom.write_bytes(english)
        ips = self.root / 'cn.ips'; ips.write_bytes(encode_patch(english, bytes(self.image)))
        first, report = package(rom, self.root / 'first', self.author, ips)
        second, _ = package(rom, self.root / 'second', self.author, ips)
        self.assertTrue(report['splash_author']['applied'])
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with zipfile.ZipFile(first) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('author.txt', archive.namelist())
            self.assertEqual(splash.sha(archive.read('ffta-us-cn.gba')), report['output_sha256'])

    def test_build_stamps_before_generating_ips_and_final_hash(self):
        import build
        import joint_build
        from types import SimpleNamespace
        retail = self.root / 'retail.gba'; retail.write_bytes(bytes(0x1000000))
        out = self.root / 'build'
        args = SimpleNamespace(output_dir=out, author_file=self.author, author=True,
                               patch_output=self.root / 'out.ips', retail=retail)
        report = dict(build_mode='test', cjk_enabled=True, pinyin_enabled=True,
                      link_fix_enabled=True, info_enabled=True, italic_font_enabled=True,
                      output_bytes=len(self.image), output_sha256=splash.sha(self.image))
        with patch.object(build, 'options', return_value=args), patch.object(
                joint_build, 'build', return_value=(bytes(self.image), report)), contextlib.redirect_stdout(io.StringIO()):
            build.main()
        final = (out / 'ffta-us-cn.gba').read_bytes()
        self.assertEqual(apply_patch(retail.read_bytes(), args.patch_output.read_bytes()), final)
        features = json.loads((out / 'features.json').read_text())
        self.assertTrue(features['splash_author']['applied'])
        self.assertEqual(features['output_sha256'], splash.sha(final))
        self.assertNotEqual(final, self.image)


class SplashVersionTests(unittest.TestCase):
    def fixture(self):
        config = json.loads(splash.VERSION_CONFIG.read_text())
        bitmap = bytearray(b'\xff\x7f' * (240 * 160))
        bitmap[2:4] = b'\x34\x12'
        x, y, width, height = config['bounds']
        for row, mask in enumerate(config['versions']['1.1']):
            for col, value in enumerate(mask):
                if value == '#':
                    struct.pack_into('<H', bitmap, ((y+row)*240+x+col)*2,
                                     config['foreground_rgb555'])
        return bytes(bitmap), config

    def test_version_change_is_bounded_and_round_trips(self):
        before, config = self.fixture()
        after, current = splash.version_pixels(before, config, '1.2')
        self.assertEqual(current, '1.1')
        x, y, width, height = config['bounds']
        allowed = {((y+j)*240+x+i)*2+k for j in range(height)
                   for i in range(width) for k in range(2)}
        changes = {i for i,(a,b) in enumerate(zip(before,after)) if a != b}
        self.assertTrue(changes)
        self.assertLessEqual(changes, allowed)
        restored, current = splash.version_pixels(after, config)
        self.assertEqual(current, '1.2')
        self.assertEqual(restored, before)

    def test_unknown_version_artwork_fails_closed(self):
        before, config = self.fixture()
        altered = bytearray(before)
        x, y, _, _ = config['bounds']
        struct.pack_into('<H', altered, (y*240+x)*2, 0x1234)
        with self.assertRaisesRegex(ValueError, 'preimage'):
            splash.version_pixels(altered, config, '1.2')


if __name__ == '__main__':
    unittest.main()
