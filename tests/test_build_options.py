import contextlib
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build import options, ROOT


class BuildOptionsTests(unittest.TestCase):
    def base(self):
        return ['--retail', '/outside/us.gba', '--output-dir', '/outside/output']

    def cn_inputs(self):
        return ['--pack-dir', '/outside/pack', '--glyph-map', '/outside/map.json',
                '--map-report', '/outside/map-report.json']

    def reject(self, arguments):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): options(arguments)

    def test_cn_and_pinyin_default_enabled(self):
        args = options(self.base() + self.cn_inputs())
        self.assertTrue(args.cjk)
        self.assertTrue(args.pinyin)
        self.assertTrue(args.link_fix)
        self.assertTrue(args.info)
        self.assertTrue(args.italic_font)

    def test_english_automatically_disables_pinyin(self):
        args = options(self.base() + ['--disable-cjk'])
        self.assertFalse(args.cjk)
        self.assertFalse(args.pinyin)
        self.assertFalse(args.link_fix)

    def test_exact_cn_does_not_require_pinyin_map(self):
        args = options(self.base() + ['--disable-pinyin', '--disable-link-fix', '--pack-dir', '/outside/pack'])
        self.assertTrue(args.cjk)
        self.assertFalse(args.pinyin)
        self.assertFalse(args.link_fix)
        self.assertFalse(args.info)
        self.assertFalse(args.italic_font)

    def test_appended_italic_font_is_independently_selectable(self):
        args = options(self.base() + self.cn_inputs() + ['--disable-italic-font'])
        self.assertFalse(args.italic_font)
        args = options(self.base() + self.cn_inputs() + ['--disable-pinyin',
                                     '--disable-link-fix', '--enable-info', '--enable-italic-font'])
        self.assertTrue(args.italic_font)
        self.assertTrue(args.info)
        self.reject(self.base() + self.cn_inputs() + ['--disable-info', '--enable-italic-font'])
        self.reject(self.base() + ['--disable-cjk', '--enable-italic-font'])

    def test_link_fix_is_independently_selectable(self):
        args = options(self.base() + ['--disable-cjk', '--enable-link-fix', '--disable-info'])
        self.assertFalse(args.cjk)
        self.assertTrue(args.link_fix)

    def test_info_is_independently_selectable(self):
        args = options(self.base() + self.cn_inputs() + ['--disable-info'])
        self.assertTrue(args.cjk)
        self.assertTrue(args.pinyin)
        self.assertFalse(args.info)
        self.reject(self.base() + ['--disable-cjk', '--enable-info'])
        args = options(self.base() + self.cn_inputs() + ['--disable-cjk', '--enable-link-fix'])
        self.assertTrue(args.info)

    def test_contradictory_explicit_flags_rejected(self):
        self.reject(self.base() + ['--disable-cjk', '--enable-pinyin'])

    def test_default_requires_explicit_private_inputs(self):
        self.reject(self.base())
        self.reject(self.base() + ['--pack-dir', '/outside/pack'])

    def test_source_tree_output_and_patch_rejected(self):
        self.reject(['--retail', '/outside/us.gba', '--disable-cjk',
                     '--output-dir', str(ROOT / 'build')])
        self.reject(self.base() + ['--disable-cjk', '--patch-output', str(ROOT / 'local.ips')])


if __name__ == '__main__': unittest.main()
