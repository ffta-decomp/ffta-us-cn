"""Registration safety for the shared native Options module."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
spec = importlib.util.spec_from_file_location('common_options', ROOT/'plugins/common/options/build.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CommonOptionsTests(unittest.TestCase):
    def load(self, rows, enabled=True, storage=3):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'options.json').write_text(json.dumps(dict(
                schema='ffta-common-options-v1',storage_byte=storage,options=rows)))
            return module.load_options([dict(id='fixture',feature='fixture',
                options='options.json')],dict(fixture=enabled),root)

    def row(self, name, bit):
        return dict(id=name,bit=bit,label='Label',hint='Hint')

    def test_stable_assignments_do_not_follow_registration_order(self):
        rows, _, used = self.load([self.row('later',7),self.row('earlier',1)])
        self.assertEqual([r['bit'] for r in rows],[7,1])
        self.assertEqual(used,{7,1})

    def test_duplicate_bits_fail(self):
        with self.assertRaisesRegex(ValueError,'Duplicate or invalid'):
            self.load([self.row('first',1),self.row('second',1)])

    def test_multibit_values_reserve_their_full_range(self):
        speed = dict(self.row('speed',3),width=2,values=['1x','2x','4x','8x'])
        rows, _, used = self.load([speed])
        self.assertEqual(used,{3,4})
        with self.assertRaisesRegex(ValueError,'Duplicate or invalid'):
            self.load([speed,self.row('collision',4)])
        with self.assertRaisesRegex(ValueError,'complete stored bit range'):
            self.load([dict(speed,values=['1x','2x'])])

    def test_language_selection_and_native_latin_encoding(self):
        self.assertEqual(module.localized({'en':'Speed','zh-Hans':'速度'},'en'),'Speed')
        self.assertEqual(module.encode_text('2x'),bytes.fromhex('80a880e100'))
        self.assertEqual(module.encode_text(' '),bytes.fromhex('407300'))
        with self.assertRaisesRegex(ValueError,'Missing Options translation'):
            module.localized({'en':'Speed'},'zh-Hans')
        with self.assertRaisesRegex(ValueError,'Missing native option glyph'):
            module.encode_text('速度')

    def test_saved_bit_capacity_is_a_hard_build_boundary(self):
        rows=[self.row('flag'+str(n),n) for n in range(8)]
        self.assertEqual(self.load(rows)[2],set(range(8)))
        for extra in (self.row('ninth',8),dict(self.row('crosses_end',7),width=2,
                values=['1x','2x','4x','8x'])):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError,'Duplicate or invalid'):
                self.load(rows+[extra])

    def test_duplicate_ids_fail(self):
        with self.assertRaisesRegex(ValueError,'Duplicate common Options ID'):
            self.load([self.row('same',1),self.row('same',2)])

    def test_invalid_bit_and_storage_fail(self):
        for bit in [-1,8,True]:
            with self.subTest(bit=bit), self.assertRaises(ValueError):
                self.load([self.row('bad',bit)])
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            self.load([self.row('bad',0)],storage=2)

    def test_disabled_plugins_do_not_reserve_bits(self):
        with self.assertRaisesRegex(ValueError,'No registered'):
            self.load([self.row('hidden',0)],enabled=False)


if __name__ == '__main__':
    unittest.main()
