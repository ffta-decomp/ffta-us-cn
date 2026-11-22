"""Install gameplay hooks; native menu and persistence live in common/options."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

PLUGIN = Path(__file__).resolve().parent
BASE, ORIGIN, BRIDGE = 0x08000000, 0xE18000, 0x36D438


def prepare(reference, image, args, output, config):
    output.mkdir(parents=True, exist_ok=False)
    prefix = args.tool_prefix
    groups = max(image[0x51d180+i*32+0x1d] for i in range(0x178)) + 1
    bindings = output/'bindings.h'
    bindings.write_text(f'#define ABILITY_GROUP_COUNT {groups}u\n')
    objects = []
    for source in (PLUGIN/'gameplay.c', PLUGIN/'bridges.s'):
        obj = output/(source.stem+'.o')
        subprocess.run([args.clang,'--target=arm-none-eabi','-mcpu=arm7tdmi','-mthumb','-Os',
            '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
            '-Wall','-Wextra','-Werror','-Wno-unused-command-line-argument','-I',str(output),'-c',str(source),'-o',str(obj)],check=True)
        objects.append(obj)
    script, elf = output/'gameplay.ld', output/'gameplay.elf'
    script.write_text(f'''SECTIONS {{
 .bridge {BASE+BRIDGE:#x} : {{ *(.bridge) }}
 .text {BASE+ORIGIN:#x} : {{ *(.text*) *(.rodata*) }}
 .data : {{ *(.data*) }} .bss : {{ *(.bss*) *(COMMON) }}
 /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }}
}}
ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0, "Unexpected gameplay static RAM")
ASSERT(SIZEOF(.bridge)<=0x28 && SIZEOF(.text)<=0x4000, "Gameplay reservation")
''')
    subprocess.run([prefix+'ld','-T',str(script),*map(str,objects),'-o',str(elf)],check=True)
    symbols = {}
    for row in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
        parts = row.split()
        if len(parts)==3: symbols[parts[2]] = int(parts[0],16)
    fragments = []
    sha = lambda b: hashlib.sha256(b).hexdigest()

    def add(name,at,blob,reservation=False):
        if image[at:at+len(blob)] != reference[at:at+len(blob)] or (reservation and set(reference[at:at+len(blob)])!={255}):
            raise ValueError(f'Gameplay hook conflict at {at:#x}')
        path=output/(name+'.bin');path.write_bytes(blob)
        fragments.append(dict(path=str(path.resolve()),sha256=sha(blob),rom_offset=at,
            kind='code',reference_sha256=sha(reference[at:at+len(blob)])))

    def call(at,symbol):
        delta=(symbols[symbol]&~1)-(BASE+at+4)
        if not -0x400000<=delta<0x400000: raise ValueError('Gameplay bridge outside Thumb BL range')
        return struct.pack('<HH',0xf000|((delta>>12)&2047),0xf800|((delta>>1)&2047))

    for section,at in (('bridge',BRIDGE),('text',ORIGIN)):
        path=output/(section+'.object')
        subprocess.run([prefix+'objcopy','-O','binary','-j','.'+section,str(elf),str(path)],check=True)
        add(section,at,path.read_bytes(),True)
    for at in (0x3896e,0x389b2,0x389e6,0x38a2e):
        if reference[at:at+2]!=b'\xfe\x29': raise ValueError('Unexpected growth counter')
        add('growth-'+hex(at),at,call(at,'GrowthBridge'))
    add('shop',0x44b22,call(0x44b22,'ShopBridge')+b'\xc0\x46'*3)
    if reference[0x48f30:0x48f34] != bytes.fromhex('00f06efd'):
        raise ValueError('Unexpected AP-page entry transition')
    add('party-ap',0x48f30,call(0x48f30,'PartyAPBridge'))
    manifest=output/'extension.json'
    sources=[PLUGIN/'build.py',PLUGIN/'gameplay.c',PLUGIN/'bridges.s',PLUGIN/'options.json',PLUGIN.parent/'common/options/options.h',bindings]
    manifest.write_text(json.dumps(dict(schema='build-extension-v1',reference_sha256=sha(reference),
        sources=[dict(path=str(p.resolve()),sha256=sha(p.read_bytes())) for p in sources],fragments=fragments),indent=2)+'\n')
    return manifest,dict(id='enhancements',symbols={k:hex(v) for k,v in symbols.items()})
