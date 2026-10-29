import ctypes
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from plugin_info import load_pages, ROOT
from build_plugin_info import generate_assets, prepare, sha, title_label, FONT_START, FONT_END, WIDTHS


class PluginInfoTests(unittest.TestCase):
    def test_entry_retains_native_ink_outline_and_shadow(self):
        mask = bytearray(240 * 160)
        mask[7 * 240 + 3] = 2
        styled, width = title_label(mask)
        self.assertEqual(styled[7 * 240 + 3], 1)  # Native title ink.
        self.assertEqual(styled[6 * 240 + 3], 8)  # Light outline remains visible.
        self.assertEqual(styled[9 * 240 + 3], 6)  # Lower shadow.
        self.assertEqual(width, 5)
        self.assertEqual(set(styled), {0, 1, 6, 8})

    def test_selected_metadata_and_explicit_newlines(self):
        pages = load_pages({'cjk': True, 'link_fix': True})
        self.assertEqual([p['name'] for p in pages], ['uscn', 'netfix'])
        self.assertEqual(pages[0]['lines'], ['美版汉化v1.1 集成', '作者 美版汉化v1.1 汉化组', '开发者bhe'])
        self.assertEqual(pages[1]['lines'], ['联机补丁', '作者闲王小周周'])
        self.assertEqual(load_pages({}), [])
        self.assertEqual(load_pages({'link_fix': True}), [pages[1]])

    def test_spaces_are_preserved_and_unknown_features_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plugins.json'
            data = {'schema': 1, 'plugins': [{'id': 'a', 'feature': 'cjk',
                                            'name': 'a', 'content': 'one two\nthree\n'}]}
            path.write_text(json.dumps(data))
            self.assertEqual(load_pages({'cjk': True}, path)[0]['lines'], ['one two', 'three', ''])
            data['plugins'][0]['feature'] = 'typo'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Unknown plugin feature'):
                load_pages({}, path)

    def fixture(self, out):
        pages = load_pages({'cjk': True, 'link_fix': True})
        needed = set('InfoB: Closea' + ''.join(p['name'] + ''.join(p['lines']) for p in pages))
        # Artificial cells with simple marks; these contain no game resources.
        image = bytearray(b'\xff' * 0x1000000)
        needed.discard(' ')
        mapping = {character: 0x8000 + i for i, character in enumerate(sorted(needed))}
        for token in mapping.values():
            i = token & 0x7fff
            cell = bytearray(128)
            for y in range(2, 12): cell[y * 4] = 3
            image[FONT_START + i * 128:FONT_START + (i + 1) * 128] = cell
            image[WIDTHS + i] = 6
        glyph_map, map_report = out / 'map.json', out / 'report.json'
        glyph_map.write_text(json.dumps(mapping))
        map_report.write_text(json.dumps({'glyph_map_sha256': sha(glyph_map.read_bytes()),
                                         'native_font_sha256': sha(image[FONT_START:FONT_END])}))
        args = SimpleNamespace(cjk=True, link_fix=True, glyph_map=glyph_map,
            map_report=map_report, clang='clang', output_dir=out,
            tool_prefix='/opt/homebrew/bin/arm-none-eabi-')
        return bytes(image), args, pages

    @unittest.skipUnless(shutil.which('clang'), 'Host clang required')
    def test_assets_and_provenance_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            image, args, pages = self.fixture(out)
            _, _, report = generate_assets(image, args, out, pages)
            self.assertEqual(len(report['views']), 2)
            self.assertTrue(all(v['bytes'] == 20480 for v in report['views']))
            before = (out / 'plugin_info_assets.c').read_bytes()
            generate_assets(image, args, out, pages)
            self.assertEqual(before, (out / 'plugin_info_assets.c').read_bytes())
            altered = bytearray(image); altered[FONT_START] ^= 1
            with self.assertRaisesRegex(ValueError, 'provenance'):
                generate_assets(altered, args, out, pages)

    @unittest.skipUnless(shutil.which('clang'), 'Host clang required')
    def test_long_content_wraps_into_additional_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            image, args, pages = self.fixture(out)
            pages[0]['lines'] = ['a' * 160]
            _, _, report = generate_assets(image, args, out, pages)
            self.assertEqual([v['first_line'] for v in report['views'] if v['plugin'] == 'uscn'], [0, 4])

    @unittest.skipUnless(Path('/opt/homebrew/bin/arm-none-eabi-ld').exists() and shutil.which('clang'),
                         'ARM binutils and clang required')
    def test_source_extension_has_one_module_and_one_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            image, args, _ = self.fixture(out)
            (out / 'decomp-build/generated').mkdir(parents=True)
            config = json.loads((ROOT / 'vendor/fftadecomp/config/completed-build.json').read_text())
            manifest_path, report = prepare(image, image, image, args, out / 'info', config)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(len(manifest['source_replacements']), 1)
            self.assertEqual(manifest['source_replacements'][0]['module'], 'Registered39_00136084')
            self.assertEqual(len(manifest['fragments']), 1)
            self.assertEqual(manifest['fragments'][0]['rom_offset'], 0xc00000)
            self.assertFalse(report['recovery_credit_eligible'])


if __name__ == '__main__': unittest.main()
