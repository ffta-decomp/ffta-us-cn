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
        self.assertEqual(args.cn_version, 'cn2025')
        self.assertFalse(args.cn2026)
        self.assertTrue(args.cjk)
        self.assertTrue(args.pinyin)
        self.assertTrue(args.link_fix)
        self.assertTrue(args.vbam_save_fix)
        self.assertTrue(args.info)
        self.assertTrue(args.italic_font)
        self.assertTrue(args.author)
        self.assertTrue(args.fastskip)
        self.assertEqual(args.author_file, ROOT / 'author.txt')

    def test_build_label_is_explicit_and_requires_info(self):
        args = options(self.base() + self.cn_inputs() + ['--build-label', '1.2 Test'])
        self.assertEqual(args.build_label, '1.2 Test')
        self.assertIsNone(options(self.base() + self.cn_inputs()).build_label)
        self.reject(self.base() + self.cn_inputs() + ['--build-label', 'bad\nlabel'])
        self.reject(self.base() + self.cn_inputs() + ['--build-label', 'Test', '--disable-info'])

    def test_english_automatically_disables_pinyin(self):
        args = options(self.base() + ['--disable-cjk'])
        self.assertFalse(args.cjk)
        self.assertFalse(args.pinyin)
        self.assertFalse(args.link_fix)
        self.assertFalse(args.vbam_save_fix)
        self.assertFalse(args.fastskip)

    def test_cn2026_requires_cn_base_and_explicit_external_images(self):
        args = options(self.base() + self.cn_inputs() + [
            '--cn-version', 'cn2026', '--image-enhancement-pack', '/outside/images'])
        self.assertTrue(args.cn2026)
        self.assertTrue(args.pinyin)
        self.assertEqual(args.image_enhancement_pack, Path('/outside/images'))
        self.reject(self.base() + self.cn_inputs() + ['--cn-version', 'cn2026'])
        self.reject(self.base() + self.cn_inputs() + ['--cn-version', 'cn2026',
                    '--image-enhancement-pack', '/outside/images', '--disable-pinyin'])
        self.reject(self.base() + self.cn_inputs() + ['--image-enhancement-pack', '/outside/images'])
        self.reject(self.base() + ['--disable-cjk', '--cn-version', 'cn2026',
                                  '--image-enhancement-pack', '/outside/images'])
        self.reject(self.base() + self.cn_inputs() + ['--cn-version', 'cn2026',
                    '--image-enhancement-pack', str(ROOT / 'images')])

    def test_exact_cn_does_not_require_pinyin_map(self):
        args = options(self.base() + ['--disable-pinyin', '--disable-link-fix', '--pack-dir', '/outside/pack'])
        self.assertTrue(args.cjk)
        self.assertFalse(args.pinyin)
        self.assertFalse(args.link_fix)
        self.assertFalse(args.vbam_save_fix)
        self.assertFalse(args.info)
        self.assertFalse(args.italic_font)
        self.assertFalse(args.author)
        self.assertFalse(args.fastskip)

    def test_vbam_save_fix_can_be_disabled_independently(self):
        args = options(self.base() + self.cn_inputs() + ['--disable-vbam-save-fix'])
        self.assertTrue(args.cjk)
        self.assertTrue(args.link_fix)
        self.assertFalse(args.vbam_save_fix)

    def test_fastskip_requires_the_cn_info_menu(self):
        args = options(self.base() + self.cn_inputs() + ['--disable-fastskip'])
        self.assertFalse(args.fastskip)
        self.reject(self.base() + self.cn_inputs() + ['--enable-fastskip', '--disable-info'])
        self.reject(self.base() + ['--disable-cjk', '--enable-fastskip'])

    def test_recruit_rename_is_opt_in_and_requires_flash(self):
        args = self.base() + self.cn_inputs()
        self.assertFalse(options(args).recruit_rename)
        self.assertTrue(options(args + ['--enable-recruit-rename']).recruit_rename)
        self.reject(args + ['--enable-recruit-rename', '--disable-vbam-save-fix'])

    def test_battle_speed_is_opt_in_and_independent_of_translation(self):
        args = self.base() + self.cn_inputs()
        self.assertFalse(options(args).battle_speed)
        self.assertTrue(options(args + ['--enable-battle-speed']).common_options)
        us = options(self.base() + ['--disable-cjk', '--enable-battle-speed'])
        self.assertTrue(us.battle_speed)
        self.assertTrue(us.common_options)
        self.assertFalse(us.cn2026)
        self.assertTrue(options(args + ['--cn-version', 'cn2026',
            '--cn2026-pack', '/outside/images', '--enable-battle-speed']).battle_speed)

    def test_recruit_rename_works_with_native_keyboard(self):
        us = options(self.base() + ['--disable-cjk', '--enable-recruit-rename'])
        self.assertTrue(us.recruit_rename)
        self.assertTrue(us.vbam_save_fix)
        for flag in (us.cjk, us.pinyin, us.link_fix, us.info, us.fastskip):
            self.assertFalse(flag)
        cn = options(self.base() + ['--pack-dir', '/outside/pack', '--disable-pinyin',
                                    '--disable-link-fix', '--enable-recruit-rename'])
        self.assertTrue(cn.recruit_rename)
        self.assertTrue(cn.vbam_save_fix)
        self.assertFalse(cn.pinyin)

    def test_author_can_be_selected_independently(self):
        args = options(self.base() + self.cn_inputs() + ['--disable-author'])
        self.assertFalse(args.author)
        args = options(self.base() + ['--disable-pinyin', '--disable-link-fix',
                       '--pack-dir', '/outside/pack', '--enable-author',
                       '--author-file', '/outside/author.txt'])
        self.assertTrue(args.author)
        self.assertEqual(args.author_file, Path('/outside/author.txt'))

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
