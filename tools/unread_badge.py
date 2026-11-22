"""Bind the authored unread badge to red without changing other row icons."""
import hashlib
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE, ORIGIN, BRIDGE, HOOK = 0x08000000, 0xE28000, 0x36D3B8, 0x17802
sha = lambda b: hashlib.sha256(b).hexdigest()


def prepare(reference, image, args, output):
    if image[0x17734:0x1784c] != reference[0x17734:0x1784c] or reference[HOOK:HOOK+4] != bytes.fromhex('d0263602'):
        raise ValueError('Unread badge native palette writer differs')
    output.mkdir(parents=True, exist_ok=False)
    sources = [ROOT/'engine/unread_badge.c', ROOT/'engine/unread_badge.s']
    objects=[]
    for source in sources:
        obj=output/(source.suffix[1:]+'.o')
        subprocess.run([args.clang,'--target=arm-none-eabi','-mcpu=arm7tdmi','-mthumb','-Os',
            '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
            '-Wall','-Wextra','-Werror','-Wno-unused-command-line-argument','-c',str(source),'-o',str(obj)],check=True)
        objects.append(obj)
    elf,script=output/'badge.elf',output/'badge.ld'
    script.write_text(f'''SECTIONS {{
 .bridge {BASE+BRIDGE:#x} : {{ *(.bridge) }}
 .text {BASE+ORIGIN:#x} : {{ *(.text*) *(.rodata*) }}
 .data : {{ *(.data*) }} .bss : {{ *(.bss*) *(COMMON) }}
 /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }}
}}
ASSERT(SIZEOF(.bridge)<=0x40 && SIZEOF(.text)<=0x1000 && SIZEOF(.data)==0 && SIZEOF(.bss)==0, "Unread badge reservation")
''')
    prefix=args.tool_prefix
    subprocess.run([prefix+'ld','-T',str(script),*map(str,objects),'-o',str(elf)],check=True)
    symbols={}
    for row in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
        parts=row.split()
        if len(parts)==3: symbols[parts[2]]=int(parts[0],16)
    fragments=[]
    blobs=[]
    for section,at in (('bridge',BRIDGE),('text',ORIGIN)):
        path=output/(section+'.bin')
        subprocess.run([prefix+'objcopy','-O','binary','-j','.'+section,str(elf),str(path)],check=True)
        blobs.append((section,at,path.read_bytes(),True))
    delta=(symbols['UnreadBadgePaletteBridge'] & ~1)-(BASE+HOOK+4)
    if not -0x400000<=delta<0x400000: raise ValueError('Unread palette bridge out of range')
    blobs.append(('call',HOOK,struct.pack('<HH',0xf000|((delta>>12)&2047),0xf800|((delta>>1)&2047)),False))
    for name,at,blob,reserved in blobs:
        if image[at:at+len(blob)] != reference[at:at+len(blob)]:
            raise ValueError('Unread badge extension conflicts at '+hex(at))
        if reserved and reference[at:at+len(blob)] != b'\xff'*len(blob):
            raise ValueError('Unread badge ROM reservation occupied')
        path=output/(name+'.bin');path.write_bytes(blob)
        fragments.append(dict(path=str(path.resolve()),rom_offset=at,kind='code',
            sha256=sha(blob),reference_sha256=sha(reference[at:at+len(blob)])))
    return dict(sources=[dict(path=str(p.resolve()),sha256=sha(p.read_bytes())) for p in (*sources,Path(__file__))],
        fragments=fragments),dict(palette_bank=14,unread_logic='native unchanged',hook=HOOK,
            match='Exact authored badge tile; all other row icons keep palette 13',ram_reserved_bytes=0)
