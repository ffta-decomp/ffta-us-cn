import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from plugin_info import load_pages
from font_plugins import resolve

spec = importlib.util.spec_from_file_location('cn2026_plugin', ROOT / 'plugins/cn2026/build.py')
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
sha = lambda data: hashlib.sha256(data).hexdigest()


class CN2026Tests(unittest.TestCase):
    def test_translation_glyphs_follow_the_active_appended_font(self):
        image = bytearray(0x100000)
        native, active, site, count = 0x10000, 0x80000, 16, 3175
        image[site:site+4] = (active+0x08000000).to_bytes(4, 'little')
        row = dict(file='glyph.bin', rom_offset=native+128, bytes=4, category='glyph',
                   kind='resource', preimage_sha256=sha(bytes(4)), sha256=sha(b'new!'))
        plan = dict(schema='ffta-cn2026-translation-revisions-v1', native_font_offset=native,
                    font_pointer_offset=site, glyph_slots=[1], fragments=[row])
        args = SimpleNamespace(font_extension_report=dict(font_rom_offset=active,
            glyph_count=count, font_sha256=sha(image[active:active+count*128])))
        rows, start, size = plugin.revision_rows(image, args, plan)
        self.assertEqual((start, size), (active, count))
        self.assertEqual([r['rom_offset'] for r in rows], [native+128, active+128])
        self.assertTrue(rows[1]['mirrored'])
        image[active] = 1
        with self.assertRaisesRegex(ValueError, 'Active font changed'):
            plugin.revision_rows(image, args, plan)

    def test_translation_appendix_avoids_the_pinyin_program(self):
        plan = json.loads((ROOT / 'plugins/cn2026/revisions.json').read_text())
        self.assertEqual(plan['source_segment_count'], 455)
        self.assertEqual(plan['skipped_residue_segments'], 1)
        for row in plan['fragments']:
            self.assertFalse(row['rom_offset'] < 0xB08000 and
                             0xB00000 < row['rom_offset'] + row['bytes'])
        self.assertEqual([r['index'] for r in plan['relocation']['pointer_rows']], [13, 62, 296, 694])

    def fixture(self, root, names=('8.bin', '24.bin')):
        pack = root / 'pack'
        pack.mkdir()
        before = bytes(64)
        rows = []
        for at, name in zip((8, 24), names, strict=True):
            data = bytes([at]) * 4
            (pack / name).write_bytes(data)
            rows.append(dict(file=name, rom_offset=at, bytes=4, kind='resource',
                             sha256=sha(data), preimage_sha256=sha(before[at:at+4])))
        plan = dict(schema='ffta-cn2026-image-pack-v1', base_translation='cn2025',
                    rom_bytes=64, version='test-images', fragments=rows,
                    included=[], deferred=[], validation_limits='fixture')
        (root / 'images.json').write_text(json.dumps(plan))
        args = SimpleNamespace(cjk=True, cn2026=True, image_enhancement_pack=pack)
        return before, args, plan

    def test_credit_replacement_preserves_four_pages_and_base_font(self):
        features = dict(cjk=True, cn2026=True, link_fix=True, info=True,
                        fastskip=True, italic_font=True)
        self.assertEqual([p['id'] for p in load_pages(features)],
                         ['cn2026', 'netfix', 'info', 'fastskip'])
        self.assertEqual(resolve(features)[0]['id'], 'cn2025')
        features['cn2026'] = False
        self.assertEqual([p['id'] for p in load_pages(features)],
                         ['cn2025', 'netfix', 'info', 'fastskip'])

    def test_manifest_is_image_only_and_writes_only_pinned_spans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, args, _ = self.fixture(root)
            with patch.object(plugin, 'PLUGIN', root):
                manifest, report = plugin.prepare(before, before, args, root / 'out', {})
            m = json.loads(manifest.read_text())
            self.assertTrue(report['image_only'])
            self.assertEqual(m['source_replacements'], [])
            image = bytearray(before)
            for f in m['fragments']:
                data = Path(f['path']).read_bytes()
                self.assertEqual(sha(data), f['sha256'])
                image[f['rom_offset']:f['rom_offset']+len(data)] = data
            self.assertEqual({i for i, (a, b) in enumerate(zip(before, image)) if a != b},
                             set(range(8, 12)) | set(range(24, 28)))

    def test_corrupt_later_fragment_does_not_emit_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, args, _ = self.fixture(root)
            (args.image_enhancement_pack / '24.bin').write_bytes(b'bad!')
            with patch.object(plugin, 'PLUGIN', root), self.assertRaisesRegex(ValueError, 'identity'):
                plugin.prepare(before, before, args, root / 'out', {})
            self.assertFalse((root / 'out').exists())

    def test_result_artwork_accepts_complete_pairs_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ('00f08000.bin', '00f10000.bin')
            before, args, plan = self.fixture(root, names)
            plan['result_artwork'] = 'result-artwork.json'
            (root / 'images.json').write_text(json.dumps(plan))
            artwork = dict(schema='ffta-cn2026-result-artwork-v1', version='test-bold',
                           style='bold', entries=[],
                           fragments={name: sha(b'bold') for name in names})
            (root / 'result-artwork.json').write_text(json.dumps(artwork))
            with patch.object(plugin, 'PLUGIN', root):
                _, legacy = plugin.prepare(before, before, args, root / 'legacy', {})
                self.assertEqual(legacy['version'], 'test-images')
                (args.image_enhancement_pack / names[0]).write_bytes(b'bold')
                with self.assertRaisesRegex(ValueError, 'same revision'):
                    plugin.prepare(before, before, args, root / 'mixed', {})
                self.assertFalse((root / 'mixed').exists())
                (args.image_enhancement_pack / names[1]).write_bytes(b'bold')
                _, updated = plugin.prepare(before, before, args, root / 'updated', {})
                self.assertEqual(updated['version'], 'test-bold')

    def test_incompatible_preimage_and_code_fragments_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, args, plan = self.fixture(root)
            image = bytearray(before)
            image[8] = 1
            with patch.object(plugin, 'PLUGIN', root), self.assertRaisesRegex(ValueError, 'preimage'):
                plugin.prepare(before, image, args, root / 'out', {})
            plan['fragments'][0]['kind'] = 'code'
            (root / 'images.json').write_text(json.dumps(plan))
            with patch.object(plugin, 'PLUGIN', root), self.assertRaisesRegex(ValueError, 'image-only'):
                plugin.prepare(before, before, args, root / 'out', {})

    def test_symlinked_and_missing_resources_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, args, _ = self.fixture(root)
            source = args.image_enhancement_pack / '8.bin'
            source.unlink()
            with patch.object(plugin, 'PLUGIN', root), self.assertRaisesRegex(ValueError, 'Missing'):
                plugin.prepare(before, before, args, root / 'out', {})
            source.symlink_to(args.image_enhancement_pack / '24.bin')
            with patch.object(plugin, 'PLUGIN', root), self.assertRaisesRegex(ValueError, 'symlinked'):
                plugin.prepare(before, before, args, root / 'out', {})


if __name__ == '__main__':
    unittest.main()
