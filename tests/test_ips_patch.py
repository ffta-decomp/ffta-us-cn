from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ips_patch import encode_patch, apply_patch, EOF_OFFSET


class IpsPatchTests(unittest.TestCase):
    def test_disabled_patch_is_empty_and_exact(self):
        patch = encode_patch(b'English', b'English')
        self.assertEqual(patch, b'PATCHEOF')
        self.assertEqual(apply_patch(b'English', patch), b'English')

    def test_sparse_changes_and_determinism(self):
        before = bytes(100)
        after = b'CN' + bytes(96) + b'PY'
        patch = encode_patch(before, after)
        self.assertEqual(patch, encode_patch(before, after))
        self.assertEqual(apply_patch(before, patch), after)

    def test_long_record_is_split(self):
        before, after = bytes(70000), b'x' * 70000
        self.assertEqual(apply_patch(before, encode_patch(before, after)), after)

    def test_reserved_eof_offset_round_trip(self):
        before = bytes(EOF_OFFSET + 2)
        after = before[:EOF_OFFSET] + b'CN'
        self.assertEqual(apply_patch(before, encode_patch(before, after)), after)

    def test_resize_and_expansion_rejected(self):
        with self.assertRaises(ValueError): encode_patch(b'a', b'ab')
        with self.assertRaises(ValueError): encode_patch(bytes(0x1000001), bytes(0x1000001))

    def test_malformed_and_outside_patches_rejected(self):
        for patch in [b'bad', b'PATCH', b'PATCHEOFextra',
                      b'PATCH\0\0\x09\0\x02abEOF', b'PATCH\0\0\0\0\0EOF']:
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError): apply_patch(bytes(4), patch)


if __name__ == '__main__': unittest.main()
