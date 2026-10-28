#!/usr/bin/env python3
"""Local mutation checks using explicitly supplied authenticated resource inputs."""
import argparse
import copy
import hashlib
import json
import unittest
from pathlib import Path
from build_us_cn_native import build
from scene_text_codec import encode_tokens
from validate_us_cn_native import validate

class NativeLocalizationTests(unittest.TestCase):
    def test_disabled_is_exact_english(self):
        image,_=build(self.retail,b'',{},False)
        self.assertEqual(image,self.retail)

    def test_wrong_revision_is_rejected(self):
        broken=bytearray(self.retail);broken[0x100]^=1
        with self.assertRaisesRegex(ValueError,'baseline'):
            build(bytes(broken),b'',{},False)

    def test_self_consistent_forged_token_is_rejected(self):
        bundle=copy.deepcopy(self.bundle)
        entry=next(e for g in bundle['groups'] for e in g['entries'] if any(t['type']=='full_glyph' for t in e['tokens']))
        token=next(t for t in entry['tokens'] if t['type']=='full_glyph')
        token['code']^=1
        decoded=encode_tokens(entry,verify_hash=False)
        entry['decoded_hex']=decoded.hex();entry['decoded_sha256']=hashlib.sha256(decoded).hexdigest()
        with self.assertRaisesRegex(ValueError,'authenticated source'):
            build(self.retail,self.cn,bundle,True)

    def test_unsafe_retail_fallback_is_rejected(self):
        bundle=copy.deepcopy(self.bundle)
        bundle['groups'][0]['entries'][0]['source_variant']='retail'
        with self.assertRaisesRegex(ValueError,'Unsafe English fallback'):
            build(self.retail,self.cn,bundle,True)

    def test_every_linked_pointer_and_payload(self):
        result=validate(self.image,self.bundle,self.report)
        self.assertEqual(result['linked_text_ids_checked'],15201)

    def test_linked_pointer_corruption_is_rejected(self):
        image=bytearray(self.image)
        binding=next(b for b in self.report['bindings'] if b['family'].startswith('words:'))
        site=binding['linked_rom_offset'];image[site:site+4]=bytes(4)
        report=copy.deepcopy(self.report);report['output_sha256']=hashlib.sha256(image).hexdigest()
        with self.assertRaisesRegex(ValueError,'outside ROM'):
            validate(bytes(image),self.bundle,report)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['retail','translated','bundle','image','report']:p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args()
    NativeLocalizationTests.retail=a.retail.read_bytes();NativeLocalizationTests.cn=a.translated.read_bytes()
    NativeLocalizationTests.bundle=json.loads(a.bundle.read_text());NativeLocalizationTests.image=a.image.read_bytes()
    NativeLocalizationTests.report=json.loads(a.report.read_text())
    unittest.main(argv=['test_us_cn_native.py'])
