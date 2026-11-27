"""Compile and install the opt-in recruit editor for the pinned US image."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

import plugin_memory as memory

PLUGIN = Path(__file__).resolve().parent
RETAIL_SHA = '43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19'
ORIGIN = 0xE02000
BRIDGE = 0x36D370
OPENING_BRIDGE = 0x36D3D8
BASE = 0x08000000
STOCK_NAME_CALLBACK = 0x0812A085
CLAN_NAME_CALL = 0x12256E
CLAN_NAME_ENTRY = 0x12B230
OPENING_CLAN_COMMAND = 0x9A863E
RECRUIT_SCRIPT_PAGE_POINTER = 0x36D67C
RECRUIT_QUESTION_TEXT_INDEX = 21
NATIVE_NAME_POOL_OFFSET = 0x5680DC
NATIVE_NAME_POOL_COUNT = 725
FLASH_SIGNATURE_OFFSET = 0x36CE28
FLASH_PROBE_CALL = 0x141DAC
NATIVE_FLASH_ID_OFFSET = 0x1418C0
RECRUIT_DIALOG_CALL = 0x1181A
NATIVE_DIALOG_TEXT_OFFSET = 0x18028
NATIVE_UNIT_FIELD_TEXT_OFFSET = 0xC7EA4
NATIVE_RECRUIT_COPY_OFFSET = 0x1443FC
MENU_HEAP_ENTRY_OFFSET = 0x227E8
NATIVE_SAVE_OFFSET = 0x13B0D4
NATIVE_LOAD_OFFSET = 0x13B480
# The title previews and temporary copies keep their original direct calls.
SAVE_CALLS = (0x649F6, 0x64A82, 0x64B6E, 0xBD268, 0x13997A)
LOAD_CALLS = (0x13AA28, 0x13AAC2)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    return dict(path=str(path.resolve()), sha256=sha(path.read_bytes()))


def thumb_call(offset, target):
    delta = (target & ~1) - (BASE + offset + 4)
    if not -0x400000 <= delta < 0x400000 or delta & 1:
        raise ValueError('Recruit hook target outside Thumb BL range')
    return struct.pack('<HH', 0xf000 | ((delta >> 12) & 0x7ff), 0xf800 | ((delta >> 1) & 0x7ff))


def encode_english(text):
    alphabet = {character: 0x80B0 + index for index, character in
                enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')}
    alphabet.update({' ': 0x4073, '?': 0x80EA, '.': 0x80E4})
    return b''.join(alphabet[character].to_bytes(2, 'big') for character in text)


def recruit_messages(image, cjk):
    page, = struct.unpack_from('<I', image, RECRUIT_SCRIPT_PAGE_POINTER)
    page -= BASE
    text_start, text_end = struct.unpack_from('<HH', image, page + RECRUIT_QUESTION_TEXT_INDEX * 2)
    original = image[page + text_start + 2:page + text_end]
    choice = original[original.index(b'\x40\x6e\x40\x53'):]
    if cjk:
        charset = PLUGIN.parents[1] / 'config/charsets/us-cn-v1.1/unicode-to-tokens.json'
        tokens = json.loads(charset.read_text())

        def encode(text):
            return b''.join(int(tokens[character][0], 16).to_bytes(2, 'big') for character in text)

        prefix, question, joined = '要招募', '吗？', '加入了社团！'
        sources = [charset]
    else:
        encode = encode_english
        prefix, question, joined = 'Welcome ', ' to clan?', ' joined the clan.'
        sources = []
    return {
        'recruit_question_prefix': encode(prefix) + b'\x00',
        'recruit_question_suffix': encode(question) + choice,
        'recruit_joined_suffix': encode(joined) + b'\x40\x77\x40\x63\x00',
    }, sources


def prepare(reference, image, args, output, config):
    if sha(reference) != RETAIL_SHA or config['rom_base'] != BASE:
        raise ValueError('Recruit naming requires the pinned US image')
    output.mkdir(parents=True, exist_ok=False)
    opening_roster_naming = getattr(args, 'opening_roster_naming', True)
    callback = STOCK_NAME_CALLBACK
    if args.pinyin:
        pinyin_report = output.parent.parent / 'cn-module-stage/build-report.json'
        callback = int(json.loads(pinyin_report.read_text())['callback_entry'], 16)
    native_name_pointers = struct.unpack_from(f'<{NATIVE_NAME_POOL_COUNT}I', image, NATIVE_NAME_POOL_OFFSET)
    messages, message_sources = recruit_messages(image, args.cjk)
    header = output / 'build_bindings.h'
    header.write_text(
        f"#define STATE_ADDRESS {memory.menu_heap_end(recruit=True):#x}u\n"
        f"#define RESIDENT_END {memory.RECRUIT_RAM[1]:#x}u\n"
        f"#define FLASH_STACK_MIN {memory.FLASH_STACK_MIN:#x}u\n"
        f"#define NAME_CALLBACK {callback:#x}u\n"
        f"#define USE_PINYIN {int(args.pinyin)}\n"
        f"#define OPENING_ROSTER_NAMING {int(opening_roster_naming)}\n"
        f"#define NAME_ENCODING {'ENCODING_CN' if args.cjk else 'ENCODING_US'}\n"
        f"#define NAMES_FIRST {min(native_name_pointers):#x}u\n"
        f"#define NAMES_END {max(native_name_pointers) + 1:#x}u\n")
    with header.open('a') as bindings:
        for name, data in messages.items():
            bindings.write(f'static const u8 {name}[] __attribute__((aligned(2))) = {{' +
                           ', '.join(f'{value:#04x}' for value in data) + '};\n')
    source = PLUGIN / 'recruit.c'
    obj = output / 'recruit.o'
    subprocess.run([args.clang, '--target=arm-none-eabi', '-mcpu=arm7tdmi', '-mthumb',
        '-Os', '-std=c11', '-ffreestanding', '-fno-builtin', '-fno-unwind-tables',
        '-fno-asynchronous-unwind-tables', '-Wall', '-Wextra', '-Werror',
        '-fstack-usage', '-I', str(output), '-c', str(source), '-o', str(obj)], check=True)
    usage = output / 'memory-usage.bin'
    subprocess.run([args.tool_prefix + 'objcopy', '-O', 'binary', '-j', '.recruit_memory',
                    str(obj), str(usage)], check=True)
    start, resident, editor, page = struct.unpack('<4I', usage.read_bytes())
    stack_rows = [row.split('\t') for row in obj.with_suffix('.su').read_text().splitlines()]
    writers = [(int(size), kind) for site, size, kind in stack_rows if site.endswith(':write_sector')]
    if len(writers) != 1 or writers[0][1] != 'static':
        raise ValueError('Expected a single statically bounded Recruit Flash writer')
    writer_stack = writers[0][0]
    memory.check_recruit_memory(start, resident, editor, page, writer_stack)
    bridge_source = PLUGIN / 'bridges.s'
    bridge_obj = output / 'bridges.o'
    subprocess.run([args.clang, '--target=arm-none-eabi', '-mcpu=arm7tdmi', '-mthumb',
                    '-c', str(bridge_source), '-o', str(bridge_obj)], check=True)
    prefix = args.tool_prefix
    script, elf = output / 'recruit.ld', output / 'recruit.elf'
    script.write_text(f'''
SECTIONS {{
    .bridge {BASE + BRIDGE:#x} : {{ *(.bridge) }}
    .opening_bridge {BASE + OPENING_BRIDGE:#x} : {{ *(.opening_bridge) }}
    .text {BASE + ORIGIN:#x} : {{ *(.text*) *(.rodata*) }}
    .data : {{ *(.data*) }}
    .bss : {{ *(.bss*) *(COMMON) }}
    /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) *(.recruit_memory) }}
}}
ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "Unexpected static RAM")
ASSERT(SIZEOF(.text) <= 0x2000 && SIZEOF(.bridge) <= 52 &&
       SIZEOF(.opening_bridge) <= 8, "Recruit ROM reservation")
''')
    subprocess.run([prefix + 'ld', '-T', str(script), str(obj), str(bridge_obj), '-o', str(elf)], check=True)
    symbols = {}
    for row in subprocess.check_output([prefix + 'nm', '-n', str(elf)], text=True).splitlines():
        parts = row.split()
        if len(parts) == 3:
            symbols[parts[2]] = int(parts[0], 16) | 1

    fragments = []
    def add(name, offset, data):
        old = reference[offset:offset+len(data)]
        if image[offset:offset+len(data)] != old:
            raise ValueError(f'Recruit hook conflicts at {offset:#x} ({name})')
        path = output / f'{name}.bin'
        path.write_bytes(data)
        fragments.append(dict(pin(path), kind='code', rom_offset=offset,
                              reference_sha256=sha(old)))

    sections = [('text', ORIGIN), ('bridge', BRIDGE)]
    if opening_roster_naming:
        sections.append(('opening_bridge', OPENING_BRIDGE))
    for section, offset in sections:
        path = output / f'{section}.object'
        subprocess.run([prefix + 'objcopy', '-O', 'binary', '-j', f'.{section}', str(elf), str(path)], check=True)
        blob = path.read_bytes()
        if not blob or reference[offset:offset+len(blob)] != b'\xff' * len(blob):
            raise ValueError(f'Recruit {section} needs an erased reservation')
        add(section, offset, blob)

    def jump(symbol):
        return struct.pack('<HHI', 0x4b00, 0x4718, symbols[symbol])

    def redirect(name, offset, symbol, original):
        if reference[offset:offset + 4] != thumb_call(offset, BASE + original):
            raise ValueError(f'Unexpected native call at {offset:#x} ({name})')
        add(name, offset, thumb_call(offset, symbols[symbol]))

    for offset in (0x70E10, 0x70F58):
        add(f'recruit-step-{offset:x}', offset, struct.pack('<I', symbols['RecruitStep']))
    add('flash-marker', FLASH_SIGNATURE_OFFSET, b'FLASH1M_V103' + bytes(4))
    redirect('flash-probe', FLASH_PROBE_CALL, 'IdentifyRecruitFlash', NATIVE_FLASH_ID_OFFSET)
    redirect('recruit-dialog', RECRUIT_DIALOG_CALL, 'DialogBridge', NATIVE_DIALOG_TEXT_OFFSET)
    if opening_roster_naming:
        command = slice(OPENING_CLAN_COMMAND, OPENING_CLAN_COMMAND + 2)
        if reference[command] != b'\x18\x0b' or image[command] != reference[command]:
            raise ValueError('Unexpected opening clan name command')
        redirect('opening-clan-name', CLAN_NAME_CALL, 'ClanNameBridge', CLAN_NAME_ENTRY)
    # Field 0 is the name. Redirect the battle and deployment cards as well as
    # the formation and detail cards, without altering native roster records.
    for name, offset in (('battle-card-name', 0x2C094), ('deployment-card-name', 0x2C9A4),
                         ('party-card-name', 0x743F6), ('unit-detail-name', 0x7563C)):
        redirect(name, offset, 'RenderNameBridge', NATIVE_UNIT_FIELD_TEXT_OFFSET)
    for offset in (0x807D0, 0x8097E):
        redirect(f'recruit-accepted-{offset:x}', offset, 'AcceptBridge', NATIVE_RECRUIT_COPY_OFFSET)
    for offset, name in ((MENU_HEAP_ENTRY_OFFSET, 'MenuHeap'), (0x4CA00, 'MissionHeap'),
                         (0x13C064, 'SaveHeap')):
        if offset == MENU_HEAP_ENTRY_OFFSET and args.fastskip:
            continue  # Fastskip builds the same lower heap bound.
        add(name, offset, jump(name))
    for offset in SAVE_CALLS:
        redirect(f'recruit-save-{offset:x}', offset, 'SaveBridge', NATIVE_SAVE_OFFSET)
    for offset in LOAD_CALLS:
        redirect(f'recruit-load-{offset:x}', offset, 'LoadBridge', NATIVE_LOAD_OFFSET)

    manifest = output / 'extension.json'
    manifest.write_text(json.dumps(dict(schema='build-extension-v1', reference_sha256=RETAIL_SHA,
        sources=[pin(path) for path in (PLUGIN / 'build.py', PLUGIN / 'native.h',
                                        source, bridge_source, *message_sources, Path(memory.__file__), header)],
        fragments=fragments), indent=2) + '\n')
    return manifest, dict(id='recruit_rename', rom_origin=ORIGIN, bridge=BRIDGE,
                          language='cn' if args.cjk else 'us',
                          keyboard='pinyin' if args.pinyin else 'native',
                          flash_capacity=131072, extension_offset=65536,
                          ram_reservation=memory.RECRUIT_RAM, resident_bytes=resident,
                          editor_heap_request_bytes=editor, flash_page_bytes=page,
                          flash_writer_stack_bytes=writer_stack, menu_heap_end=start,
                          startup_flash_probe=FLASH_PROBE_CALL,
                          opening_roster_naming=opening_roster_naming,
                          symbols={name: hex(address) for name, address in symbols.items()})
