import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from font_plugins import extend, resolve, shear
from plugin_info import ROOT
import decomp_formats
from scene_text_codec import encode_tokens
from extract_resources import decode_word


class FontPluginTests(unittest.TestCase):
    def test_info_inherits_font_declaration_and_respects_internal_flag(self):
        base, selected, _ = resolve({'cjk': True, 'info': True, 'italic_font': False})
        self.assertEqual(base['id'], 'uscn')
        self.assertEqual(selected, [])
        _, selected, _ = resolve({'cjk': True, 'info': True, 'italic_font': True})
        self.assertEqual(len(selected), 4)
        self.assertTrue(all(p['id'] == 'info' and p['priority'] < base['priority'] for p, _ in selected))

    def test_appended_tokens_round_trip_through_native_codec(self):
        tokens = [dict(type='full_glyph', code=i) for i in range(3175, 3179)]
        encoded = encode_tokens(dict(encoding='standard', tokens=tokens), verify_hash=False)
        self.assertEqual(decode_word(encoded, 0)['tokens'], tokens)
        self.assertEqual(encoded, bytes.fromhex('8c678c688c698c6a00'))
    def catalogue(self, plugins, features):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'plugins.json'
            path.write_text(json.dumps(dict(schema=1, plugins=plugins)))
            return resolve(features, path)

    def plugin(self, identifier, priority, mode='append'):
        return dict(id=identifier, feature='italic_font' if mode == 'append' else 'cjk',
                    name=identifier, content=identifier, priority=priority,
                    font=dict(mode=mode, style='italic', characters='I', transform='row_shear',
                              baseline=13, rows_per_pixel=3))

    def test_uscn_priority_and_order_independent_style_resolution(self):
        base = self.plugin('uscn', 1000, 'base')
        high, low = self.plugin('high', 100), self.plugin('low', 10)
        for plugins in ([low, base, high], [high, low, base]):
            owner, selected, ignored = self.catalogue(plugins, {'cjk': True, 'italic_font': True})
            self.assertEqual(owner['id'], 'uscn')
            self.assertEqual([(p['id'], c) for p, c in selected], [('high', 'I')])
            self.assertEqual(ignored[0]['owner'], 'high')
        high['priority'] = 1000
        with self.assertRaisesRegex(ValueError, 'highest'):
            self.catalogue([base, high], {'cjk': True, 'italic_font': True})

    def test_equal_priority_style_conflicts_and_missing_base_fail(self):
        plugins = [self.plugin('uscn', 1000, 'base'), self.plugin('a', 100), self.plugin('b', 100)]
        with self.assertRaisesRegex(ValueError, 'Equal-priority'):
            self.catalogue(plugins, {'cjk': True, 'italic_font': True})
        with self.assertRaisesRegex(ValueError, 'base font'):
            self.catalogue(plugins, {'italic_font': True})

    def test_shear_preserves_nibbles_and_rejects_clipping(self):
        cell = bytearray(128)
        cell[5 * 4] = 0x23
        cell[12 * 4] = 0x03
        result, width = shear(cell, 3, 13, 3)
        self.assertEqual(result[5 * 4 + 1], 0x23)  # Two pixels right at row 5.
        self.assertEqual(result[12 * 4], 0x03)  # Baseline stays in place.
        self.assertEqual(sum((b & 15 != 0) + (b >> 4 != 0) for b in result), 3)
        self.assertEqual(width, 4)
        cell[64 + 5 * 4 + 3] = 0x30
        with self.assertRaisesRegex(ValueError, 'clip'):
            shear(cell, 16, 13, 3)

    def test_appended_indices_preserve_base_cells_widths_and_aliases(self):
        cell = bytearray(128); cell[5 * 4] = 3
        font, widths = bytes(cell) * 2, bytes([3, 3])
        rows = [dict(index=i, unicode='I', glyph_sha256=hashlib.sha256(cell).hexdigest(), advance=3)
                for i in range(2)]
        base, plugin = self.plugin('uscn', 1000, 'base'), self.plugin('italic', 100)
        expanded, advances, table, normal, styles = extend(font, widths, rows, base, [(plugin, 'I')])
        self.assertEqual(expanded[:len(font)], font)
        self.assertEqual(advances[:2], widths)
        self.assertEqual(normal, {'I': 0x8000})
        self.assertEqual(styles, {'italic': {'I': 0x8002}})
        self.assertEqual(table[2]['source_index'], 0)
        rows[1]['advance'] = 9
        with self.assertRaisesRegex(ValueError, 'does not match'):
            extend(font, widths, rows, base, [(plugin, 'I')])


if __name__ == '__main__': unittest.main()
