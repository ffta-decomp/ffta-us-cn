"""Native HP/gate/option contracts, independent of copyrighted game assets."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/fastskip'


class FastskipTests(unittest.TestCase):
    def test_plugin_is_declared_with_explicit_sources_and_default_off(self):
        declaration = next(p for p in json.loads((ROOT / 'plugins/plugins.json').read_text())['plugins']
                           if p['id'] == 'fastskip')
        self.assertEqual(declaration['feature'], 'fastskip')
        self.assertEqual(declaration['name'], 'Options')
        self.assertIn('fastskip/build.py', declaration['files'])
        settings = json.loads((PLUGIN / 'config.json').read_text())
        self.assertFalse(settings['default_enabled'])
        self.assertEqual(settings['option_ram_bytes'], 16)
        self.assertEqual({h['name'] for h in settings['hooks']}, {'frame', 'scene', 'heap'})

    @unittest.skipUnless(shutil.which('clang'), 'Host clang required')
    def test_hp_signatures_scene_gate_and_runtime_switch(self):
        source = r'''
#include <assert.h>
#include <string.h>
#include "opening_battle_hp.h"
#include "opening_scene_gate.h"
#include "runtime_option.h"
int main(void) {
  union { unsigned short aligned; unsigned char bytes[264*9]; } pool;
  unsigned char *u=pool.bytes, *m=u+264*5;
  struct OpeningOption option={0,0,0,0};
  unsigned i;
  assert(sizeof(option)==16 && !OpeningOptionRead(&option));
  OpeningOptionWrite(&option,1); assert(OpeningOptionRead(&option));
  option.inverse=0; assert(!OpeningOptionRead(&option));
  OpeningOptionWrite(&option,0); assert(!OpeningOptionRead(&option));
  memset(u,0,sizeof(pool.bytes));
  m[4]=0x10; *(unsigned short *)(m+24)=8;
  RgOpeningLimitHp(7,u); assert(*(unsigned short *)(m+24)==8);
  RgOpeningLimitHp(6,u); assert(*(unsigned short *)(m+24)==1);
  *(unsigned short *)(m+24)=0;
  RgOpeningLimitHp(6,u); assert(*(unsigned short *)(m+24)==0);
  *(unsigned short *)(m+24)=8; *(unsigned short *)(m+40)=0x8000;
  RgOpeningLimitHp(6,u); assert(*(unsigned short *)(m+24)==8);
  *(unsigned short *)(m+40)=0; m[4]=0x11;
  RgOpeningLimitHp(6,u); assert(*(unsigned short *)(m+24)==8);
  for(i=0;i<2;i++) {
    unsigned char *e=u+264*i;
    e[4]=1; e[5]=i?0x0d:0x11;
    *(unsigned short *)(e+24)=i?50:33;
    *(unsigned short *)(e+40)=0x8000;
  }
  *(unsigned short *)(u+264*2+24)=44;
  RgOpeningLimitHp(11,u);
  assert(*(unsigned short *)(u+24)==1);
  assert(*(unsigned short *)(u+264+24)==1);
  assert(*(unsigned short *)(u+264*2+24)==44);
  *(unsigned short *)(u+24)=20;u[5]=0;
  RgOpeningLimitHp(11,u); assert(*(unsigned short *)(u+24)==20);
  assert(RgOpeningSceneGate(1,0x101,2,2,1,0,0x0200f4e8));
  assert(!RgOpeningSceneGate(0,0x101,2,2,1,0,0x0200f4e8));
  assert(!RgOpeningSceneGate(1,0x202,2,2,1,0,0x0200f4e8));
  assert(!RgOpeningSceneGate(1,0x101,3,2,1,0,0x0200f4e8));
  assert(!RgOpeningSceneGate(1,0x101,2,3,1,0,0x0200f4e8));
  assert(!RgOpeningSceneGate(1,0x101,2,2,2,0,0x0200f4e8));
  assert(!RgOpeningSceneGate(1,0x101,2,2,1,9,0x0200f4e8));
  assert(!RgOpeningSceneGate(1,0x101,2,2,1,0,0));
  return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='fastskip-native-') as tmp:
            out = Path(tmp)
            (out / 'test.c').write_text(source)
            subprocess.run(['clang', '-std=c99', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-I', str(PLUGIN),
                            str(out / 'test.c'), '-o', str(out / 'test')], check=True)
            subprocess.run([str(out / 'test')], check=True)


if __name__ == '__main__':
    unittest.main()
