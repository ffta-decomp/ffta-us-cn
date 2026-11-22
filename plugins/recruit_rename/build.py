"""Compile and install the opt-in recruit editor for the pinned US image."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

PLUGIN = Path(__file__).resolve().parent
RETAIL_SHA = '43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19'
ORIGIN = 0xE02000
BRIDGE = 0x36D370
BASE = 0x08000000
STOCK_NAME_CALLBACK = 0x0812A085
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
    page, = struct.unpack_from('<I', image, 0x36d67c)
    page -= BASE
    first, end = struct.unpack_from('<HH', image, page + 21 * 2)
    original = image[page + first + 2:page + end]
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
    callback = STOCK_NAME_CALLBACK
    if args.pinyin:
        pinyin_report = output.parent.parent / 'cn-module-stage/build-report.json'
        callback = int(json.loads(pinyin_report.read_text())['callback_entry'], 16)
    vanilla_names = struct.unpack_from('<725I', image, 0x5680DC)
    messages, message_sources = recruit_messages(image, args.cjk)
    header = output / 'build_bindings.h'
    header.write_text(
        f"#define NAME_CALLBACK {callback:#x}u\n"
        f"#define USE_PINYIN {int(args.pinyin)}\n"
        f"#define NAME_ENCODING {'ENCODING_CN' if args.cjk else 'ENCODING_US'}\n"
        f"#define NAMES_FIRST {min(vanilla_names):#x}u\n"
        f"#define NAMES_END {max(vanilla_names) + 1:#x}u\n")
    with header.open('a') as bindings:
        for name, data in messages.items():
            bindings.write(f'static const u8 {name}[] __attribute__((aligned(2))) = {{' +
                           ', '.join(f'{value:#04x}' for value in data) + '};\n')
    source = PLUGIN / 'recruit.c'
    obj = output / 'recruit.o'
    subprocess.run([args.clang, '--target=arm-none-eabi', '-mcpu=arm7tdmi', '-mthumb',
        '-Os', '-std=c11', '-ffreestanding', '-fno-builtin', '-fno-unwind-tables',
        '-fno-asynchronous-unwind-tables', '-Wall', '-Wextra', '-Werror',
        '-I', str(output), '-c', str(source), '-o', str(obj)], check=True)
    bridge_source = PLUGIN / 'bridges.s'
    bridge_obj = output / 'bridges.o'
    subprocess.run([args.clang, '--target=arm-none-eabi', '-mcpu=arm7tdmi', '-mthumb',
                    '-c', str(bridge_source), '-o', str(bridge_obj)], check=True)
    prefix = args.tool_prefix
    script, elf = output / 'recruit.ld', output / 'recruit.elf'
    script.write_text(f'''
SECTIONS {{
    .bridge {BASE + BRIDGE:#x} : {{ *(.bridge) }}
    .text {BASE + ORIGIN:#x} : {{ *(.text*) *(.rodata*) }}
    .data : {{ *(.data*) }}
    .bss : {{ *(.bss*) *(COMMON) }}
    /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }}
}}
ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "Unexpected static RAM")
ASSERT(SIZEOF(.text) <= 0x2000 && SIZEOF(.bridge) <= 0x40, "Recruit ROM reservation")
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

    for section, offset in (('text', ORIGIN), ('bridge', BRIDGE)):
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
    add('flash-marker', 0x36CE28, b'FLASH1M_V103' + bytes(4))
    redirect('flash-probe', 0x141DAC, 'IdentifyRecruitFlash', 0x1418C0)
    redirect('recruit-dialog', 0x1181A, 'DialogBridge', 0x18028)
    for name, offset in (('party-card-name', 0x743F6), ('unit-detail-name', 0x7563C)):
        redirect(name, offset, 'RenderNameBridge', 0xC7EA4)
    for offset in (0x807D0, 0x8097E):
        redirect(f'recruit-accepted-{offset:x}', offset, 'AcceptBridge', 0x1443FC)
    for offset, name in ((0x227E8, 'MenuHeap'), (0x4CA00, 'MissionHeap'),
                         (0x13C064, 'SaveHeap')):
        if offset == 0x227E8 and args.fastskip:
            continue  # Fastskip builds the same lower heap bound.
        add(name, offset, jump(name))
    for offset in SAVE_CALLS:
        redirect(f'recruit-save-{offset:x}', offset, 'SaveBridge', 0x13B0D4)
    for offset in LOAD_CALLS:
        redirect(f'recruit-load-{offset:x}', offset, 'LoadBridge', 0x13B480)

    manifest = output / 'extension.json'
    manifest.write_text(json.dumps(dict(schema='build-extension-v1', reference_sha256=RETAIL_SHA,
        sources=[pin(path) for path in (PLUGIN / 'build.py', PLUGIN / 'native.h',
                                        source, bridge_source, *message_sources, header)],
        fragments=fragments), indent=2) + '\n')
    return manifest, dict(id='recruit_rename', rom_origin=ORIGIN, bridge=BRIDGE,
                          language='cn' if args.cjk else 'us',
                          keyboard='pinyin' if args.pinyin else 'native',
                          flash_capacity=131072, extension_offset=65536,
                          startup_flash_probe=0x141DAC,
                          symbols={name: hex(address) for name, address in symbols.items()})
