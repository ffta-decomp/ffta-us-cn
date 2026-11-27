"""Optional fastskip plugin, delivered through the pinned extension API."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

import plugin_memory as memory

PLUGIN = Path(__file__).resolve().parent
HOST = PLUGIN.parents[1]
RETAIL_SHA = '43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    return dict(path=str(path.resolve()), sha256=sha(path.read_bytes()))


def prepare(reference, image, args, output, config):
    if not (args.cjk and args.info):
        raise ValueError('fastskip Options requires the CN Info menu')
    if len(reference) != 0x1000000 or sha(reference) != RETAIL_SHA:
        raise ValueError('fastskip requires the authenticated US reference')
    settings = json.loads((PLUGIN / 'config.json').read_text())
    if (settings['schema'], settings['default_enabled'], settings['option_ram_address'],
        settings['option_ram_bytes'], settings['arena_rom_offset'], settings['arena_bytes']) != (
            1, False, '0x0203fff0', 16, '0x00e00000', 8192):
        raise ValueError('Unsupported fastskip memory/option contract')
    origin, capacity = int(settings['arena_rom_offset'], 16), settings['arena_bytes']
    erased = b'\xff' * capacity
    if reference[origin:origin + capacity] != erased or image[origin:origin + capacity] != erased:
        raise ValueError('fastskip ROM reservation conflicts with existing resources or plugins')
    for hook in settings['hooks']:
        offset, size = hook['rom_offset'], hook['envelope_bytes']
        if sha(reference[offset:offset + size]) != hook['sha256']:
            raise ValueError('fastskip native envelope mismatch: ' + hook['name'])
        if image[offset:offset + size] != reference[offset:offset + size]:
            raise ValueError('fastskip hook conflicts with another extension: ' + hook['name'])
    output = Path(output).resolve()
    if output.is_relative_to(HOST):
        raise ValueError('fastskip outputs must stay outside the source tree')
    output.mkdir(parents=True, exist_ok=False)
    objects = []
    end = memory.menu_heap_end(recruit=getattr(args, 'recruit_rename', False), fastskip=True)
    heap_bound = [f'-DMENU_HEAP_END={end:#010x}u',
                  f'-DEXPECTED_OPTION_ADDRESS={memory.FASTSKIP_RAM[0]:#010x}u',
                  f'-DEXPECTED_OPTION_BYTES={memory.FASTSKIP_RAM[1] - memory.FASTSKIP_RAM[0]}u']
    for filename in ['frame.c', 'opening_scene.c', 'heap.c']:
        obj = output / (Path(filename).stem + '.o')
        subprocess.run([args.clang, '--target=arm-none-eabi', '-mcpu=arm7tdmi', '-mthumb',
            '-Os', '-std=c99', '-ffreestanding', '-fno-builtin', '-ffunction-sections',
            '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
            '-Wall', '-Wextra', '-Werror', *heap_bound, '-c', str(PLUGIN / filename), '-o', str(obj)], check=True)
        objects.append(obj)
    script = output / 'fastskip.ld'
    script.write_text('SECTIONS { . = 0x%08x; .text : { *(.text.OpeningBattleFrameTask) *(.text*) *(.rodata*) } '
        '.data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } '
        '/DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }\n'
        'ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "Unexpected static RAM")\n' % (config['rom_base'] + origin))
    elf, binary = output / 'fastskip.elf', output / 'fastskip.bin'
    subprocess.run([args.tool_prefix + 'ld', '-T', str(script), *map(str, objects), '-o', str(elf)], check=True)
    subprocess.run([args.tool_prefix + 'objcopy', '-O', 'binary', '-j', '.text', str(elf), str(binary)], check=True)
    symbols = {}
    for row in subprocess.check_output([args.tool_prefix + 'nm', '-n', str(elf)], text=True).splitlines():
        parts = row.split()
        if len(parts) == 3:
            symbols[parts[2]] = int(parts[0], 16)
    payload = binary.read_bytes()
    if not payload or len(payload) > capacity:
        raise ValueError('fastskip payload exceeds its reserved ROM arena')
    targets = dict(frame='OpeningBattleFrameTask', scene='OpeningSceneService', heap='OpeningInitializeMenuHeap')
    fragments = [dict(pin(binary), kind='code', rom_offset=origin,
                      reference_sha256=sha(reference[origin:origin + len(payload)]))]
    sources = [p for p in sorted(PLUGIN.iterdir()) if p.is_file()]
    for hook in settings['hooks']:
        target = symbols[targets[hook['name']]] | 1
        if not config['rom_base'] + origin <= target < config['rom_base'] + origin + len(payload):
            raise ValueError('fastskip service outside its reservation')
        stub = output / (hook['name'] + '-entry.bin')
        # Thumb LDR/BX transfers control to the C replacement outside BL range.
        stub.write_bytes(struct.pack('<HHI', 0x4b00, 0x4718, target))
        offset = hook['rom_offset']
        fragments.append(dict(pin(stub), kind='code', rom_offset=offset,
                              reference_sha256=sha(reference[offset:offset + 8])))
    manifest = dict(schema='build-extension-v1', reference_sha256=sha(reference),
                    sources=[pin(p) for p in (*sources, Path(memory.__file__))], source_replacements=[], fragments=fragments)
    path = output / 'extension.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    report = dict(id='fastskip', default_enabled=False, toggle='Info > Options',
                  settings_persisted_to_save=False, rom_reservation=[origin, origin + capacity],
                  ram_reservation=memory.FASTSKIP_RAM, menu_heap_end=end, payload_bytes=len(payload),
                  symbols={k: hex(symbols[v] | 1) for k, v in targets.items()},
                  hooks=settings['hooks'], source=settings['source'], recovery_credit_eligible=False)
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return path, report
