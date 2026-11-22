"""Committed battle updates, with the native input/render pass retained."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

PLUGIN = Path(__file__).resolve().parent
BASE, ORIGIN, BRIDGE, HOOK = 0x08000000, 0xE20000, 0x36D3B0, 0x21494
RETAIL_SHA = '43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19'
sha = lambda data: hashlib.sha256(data).hexdigest()


def prepare(reference, image, args, output, config):
    if sha(reference) != RETAIL_SHA or len(image) != len(reference):
        raise ValueError('Unexpected battle animation US revision')
    if image[0x210e4:0x2158c] != reference[0x210e4:0x2158c]:
        raise ValueError('Battle sprite animation engine already modified')
    # Pin every native update/queue contract used by the C implementation.
    for start,end in ((0x23f00,0x23fd0),(0x5a24,0x5afe),(0x9b88c,0x9c6b8),
                      (0xa8270,0xa827c),(0xa8958,0xa8968),(0xa8db8,0xa8e0c)):
        if image[start:end]!=reference[start:end]:
            raise ValueError(f'Battle presentation native dependency changed at {start:#x}')
    if reference[HOOK:HOOK+4] != bytes.fromhex('fff7fcfe'):
        raise ValueError('Unexpected native sprite animation call')
    output = Path(output).resolve()
    if output.is_relative_to(PLUGIN.parents[1]):
        raise ValueError('Battle animation outputs must stay outside source')
    output.mkdir(parents=True, exist_ok=False)
    obj, elf, script = output/'animation.o', output/'animation.elf', output/'animation.ld'
    subprocess.run([args.clang,'--target=arm-none-eabi','-mcpu=arm7tdmi','-mthumb','-Os',
        '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
        '-Wall','-Wextra','-Werror','-c',str(PLUGIN/'animation.c'),'-o',str(obj)],check=True)
    script.write_text(f'''SECTIONS {{
 .text {BASE+ORIGIN:#x} : {{ *(.text*) *(.rodata*) }}
 .data : {{ *(.data*) }} .bss : {{ *(.bss*) *(COMMON) }}
 /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }}
}}
ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0, "Unexpected animation static RAM")
ASSERT(SIZEOF(.text)<=0x4000, "Animation ROM reservation")
''')
    prefix = args.tool_prefix
    subprocess.run([prefix+'ld','-T',str(script),str(obj),'-o',str(elf)],check=True)
    symbols = {}
    for row in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
        parts = row.split()
        if len(parts)==3: symbols[parts[2]] = int(parts[0],16)
    binary = output/'animation.bin'
    subprocess.run([prefix+'objcopy','-O','binary','-j','.text',str(elf),str(binary)],check=True)
    payload = binary.read_bytes()
    target = symbols['BattleAnimationTick'] | 1
    delta = BRIDGE - (HOOK+4)
    frame_hook=0x23fa8
    if reference[frame_hook:frame_hook+4]!=bytes.fromhex('e2f724fd'):
        raise ValueError('Unexpected native scene group call')
    frame_delta=BRIDGE+8-(frame_hook+4)
    fragments = []
    for name,at,blob,reserved in (
        ('animation',ORIGIN,payload,True),
        ('bridge',BRIDGE,struct.pack('<HHI',0x4b00,0x4718,target),True),
        ('frame-bridge',BRIDGE+8,struct.pack('<HHI',0x4b00,0x4718,symbols['BattlePresentationFrame']|1),True),
        ('frame-call',frame_hook,struct.pack('<HH',0xf000|((frame_delta>>12)&2047),0xf800|((frame_delta>>1)&2047)),False),
        ('call',HOOK,struct.pack('<HH',0xf000|((delta>>12)&2047),0xf800|((delta>>1)&2047)),False),
    ):
        if image[at:at+len(blob)] != reference[at:at+len(blob)]:
            raise ValueError(f'Battle animation hook conflict at {at:#x}')
        if reserved and reference[at:at+len(blob)] != b'\xff'*len(blob):
            raise ValueError('Battle animation ROM reservation occupied')
        path = output/(name+'.bin'); path.write_bytes(blob)
        fragments.append(dict(path=str(path),rom_offset=at,kind='code',sha256=sha(blob),
                              reference_sha256=sha(reference[at:at+len(blob)])))
    sources = [PLUGIN/'build.py',PLUGIN/'animation.c',PLUGIN/'options.json',PLUGIN.parent/'common/options/options.h']
    manifest = output/'extension.json'
    manifest.write_text(json.dumps(dict(schema='build-extension-v1',reference_sha256=sha(reference),
        sources=[dict(path=str(p.resolve()),sha256=sha(p.read_bytes())) for p in sources],fragments=fragments),indent=2)+'\n')
    return manifest, dict(id='battle_speed',experimental=True,multipliers=[1,2,4,8],default_mode=0,
        setting_bits=[3,4],scope='Committed movement, action and reaction presentation; input remains at 1x',
        linked_battles_accelerated=False,scheduler_changed=True,render_submissions_per_visit=1,intermediate_sprite_dma=False,
        extra_task_groups=['battle effects'],opaque_action_states_deferred=[0,14,36],
        extra_update_phases=[43,60,67],static_ram_bytes=0,
        symbols={k:hex(v) for k,v in symbols.items()})
