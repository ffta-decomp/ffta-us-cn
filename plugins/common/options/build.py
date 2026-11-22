"""Install CN2026 native Options rows and guarded gameplay enhancements."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

PLUGIN = Path(__file__).resolve().parent
BASE = 0x08000000
ORIGIN = 0xE10000
BRIDGE = 0x36D454


def sha(data):
    return hashlib.sha256(data).hexdigest()


def thumb_call(offset, target):
    delta = (target & ~1) - (BASE + offset + 4)
    if not -0x400000 <= delta < 0x400000 or delta & 1:
        raise ValueError('Enhancement bridge outside Thumb BL range')
    return struct.pack('<HH', 0xf000 | ((delta >> 12) & 0x7ff), 0xf800 | ((delta >> 1) & 0x7ff))


def load_options(catalogue, features, project):
    from plugin_info import enabled
    registrations = []
    registration_sources = []
    used = set()
    for plugin in catalogue:
        declaration = plugin.get('options')
        if not declaration or not enabled(plugin, features):
            continue
        relative = Path(declaration)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Options declaration must stay within the plugin project')
        path = project / relative
        spec = json.loads(path.read_text())
        if spec['schema'] != 'ffta-common-options-v1' or spec['storage_byte'] != 3:
            raise ValueError('Unsupported common Options declaration')
        registration_sources.append(path)
        for row in spec['options']:
            if type(row['bit']) is not int or row['bit'] in used or not 0 <= row['bit'] < 8:
                raise ValueError('Duplicate or invalid persistent Options bit')
            used.add(row['bit'])
            registrations.append(row)
    if len({r["id"] for r in registrations}) != len(registrations):
        raise ValueError("Duplicate common Options ID")
    if not registrations:
        raise ValueError('No registered common Options')
    return registrations, registration_sources, used


def prepare(reference, image, args, output, config):
    if not args.cjk or not args.cn2026:
        raise ValueError('Enhancements require CN2026')
    output.mkdir(parents=True, exist_ok=False)
    root = PLUGIN.parents[2]
    charset = root / 'config/charsets/us-cn-v1.1/unicode-to-tokens.json'
    tokens = json.loads(charset.read_text())

    def text(value):
        result = bytearray()
        for c in value:
            if c in tokens:
                code = int(tokens[c][0], 16)
            elif 'A' <= c <= 'Z':
                code = 0x80B0 + ord(c)-ord('A')
            else:
                raise ValueError('Missing native option glyph: ' + c)
            result.extend(code.to_bytes(2, 'big'))
        return bytes(result) + b'\0'

    sys.path.insert(0, str(root / 'tools'))
    from plugin_info import load_catalogue, enabled
    features = dict(vars(args))
    registrations, registration_sources, used = load_options(load_catalogue(), features, PLUGIN.parents[1])
    labels = [r['label'] for r in registrations]
    hints = [r['hint'] for r in registrations]
    count = 10 + len(registrations)
    rows = [image[0x36d4d4+i*20:0x36d4d4+(i+1)*20] for i in range(10)]
    rows += [struct.pack('<10H', 2, 16, 766, 765, 0, 0, 0, 0, 0, 0)] * len(registrations)
    header = output / 'bindings.h'
    data = [f'#define COMMON_OPTION_COUNT {count}', f'const unsigned char CommonOptionCount = {count};', 'extern unsigned int NativeQuery(unsigned int, unsigned int);']
    data.append('const unsigned short EnhancedDefinitions[] = {' +
                ','.join(str(n) for n in struct.unpack('<'+str(count*10)+'H', b''.join(rows))) + '};')
    for i, value in enumerate(labels):
        data.append(f'static const unsigned char Label{i}[] __attribute__((aligned(2))) = {{' + ','.join(map(str, text(value))) + '};')
    pointers = [f'(const unsigned char *){struct.unpack_from("<I", image, 0x5567f0+(745+i)*4)[0]:#x}' for i in range(10)]
    data.append('const unsigned char * const EnhancedLabels[] = {' + ','.join(pointers + [f'Label{i}' for i in range(len(registrations))]) + '};')
    sys.path.insert(0, str(root / 'tools'))
    from us_cn_text_layout import page_layout, decode_record, encode_record
    page = struct.unpack_from('<I', image, 0x94b8)[0] - BASE
    _, offsets = page_layout(image, page)
    if len(offsets) != 11:
        raise ValueError('Unexpected native Options hint count')
    records = [encode_record(decode_record(image, page+at)) for at in offsets[:10]]
    records += [b'\0\0' + text(value) for value in hints]
    records.append(b'\0\0\0')
    cursor = (count+2)*2
    offsets = []
    for record in records:
        offsets.append(cursor)
        cursor += len(record)
    hints_blob = struct.pack('<'+str(count+2)+'H', *offsets, 65535) + b''.join(records)
    data.append('const unsigned char EnhancedHints[] __attribute__((aligned(2))) = {' + ','.join(map(str, hints_blob)) + '};')
    data.append('static const unsigned char CommonOptionBits[] = {' + ','.join(str(r['bit']) for r in registrations) + '};')
    header.write_text('\n'.join(data)+'\n')
    objects = []
    for source in (PLUGIN / 'options.c', PLUGIN / 'bridges.s'):
        obj = output / (source.stem+'.o')
        subprocess.run([args.clang, '--target=arm-none-eabi', '-mcpu=arm7tdmi', '-mthumb', '-Os',
            '-ffreestanding', '-fno-builtin', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
            '-Wall', '-Wextra', '-Werror', '-Wno-unused-command-line-argument', '-I', str(output), '-c', str(source), '-o', str(obj)], check=True)
        objects.append(obj)
    script, elf = output / 'enhancements.ld', output / 'enhancements.elf'
    script.write_text(f'''SECTIONS {{
 .bridge {BASE+BRIDGE:#x} : {{ *(.bridge) }}
 .text {BASE+ORIGIN:#x} : {{ *(.text*) *(.rodata*) }}
 .data : {{ *(.data*) }}
 .bss : {{ *(.bss*) *(COMMON) }}
 /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }}
}}
ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0, "Unexpected static RAM")
ASSERT(SIZEOF(.bridge)<=0x1c && SIZEOF(.text)<=0x8000, "Enhancement ROM reservation")
''')
    prefix = args.tool_prefix
    subprocess.run([prefix+'ld', '-T', str(script), *map(str, objects), '-o', str(elf)], check=True)
    symbols = {}
    for row in subprocess.check_output([prefix+'nm', '-n', str(elf)], text=True).splitlines():
        parts = row.split()
        if len(parts)==3:
            symbols[parts[2]] = int(parts[0], 16)
    fragments = []

    def add(name, at, blob, reservation=False):
        if image[at:at+len(blob)] != reference[at:at+len(blob)] and not (at == 0x94b8 and image[at:at+4] == struct.pack('<I', BASE+page)):
            raise ValueError(f'Enhancement conflict at {at:#x}')
        if reservation and reference[at:at+len(blob)] != b'\xff'*len(blob):
            raise ValueError('Enhancement reservation not erased')
        path = output / (name+'.bin')
        path.write_bytes(blob)
        fragments.append(dict(path=str(path.resolve()), sha256=sha(blob), rom_offset=at,
                              kind='code', reference_sha256=sha(reference[at:at+len(blob)])))

    def call(name, at, symbol):
        add(name, at, thumb_call(at, symbols[symbol]))

    def jump(symbol):
        return struct.pack('<HHI', 0x4b00, 0x4718, symbols[symbol] | 1)

    for section, at in (('bridge', BRIDGE), ('text', ORIGIN)):
        path = output / (section+'.object')
        subprocess.run([prefix+'objcopy', '-O', 'binary', '-j', '.'+section, str(elf), str(path)], check=True)
        add(section, at, path.read_bytes(), True)
    add('constructor', 0x8818, struct.pack('<4HI', 0x469c, 0x4b01, 0x4718, 0x46c0, symbols['OptionsInitBridge'] | 1))
    add('clear', 0x8938, jump('EnhancedOptionsClear'))
    add('query', 0x94bc, jump('EnhancedQuery'))
    for at, register in ((0x88de,1),(0x8fea,1),(0x9046,3),(0x91d4,1),(0x959e,0)):
        if reference[at:at+4] != struct.pack('<HH', 0x20ce | (register << 8), 0x0080 | (register << 3) | register):
            raise ValueError(f'Unexpected Options cell base at {at:#x}')
        add('cells-'+hex(at), at, struct.pack('<HH', 0x20e0 | (register << 8), 0x0140 | (register << 3) | register))
    call('list-count', 0x8eee, 'ListCountBridge')
    for at in (0x8fd2, 0x91ae, 0x9592, 0x93fc):
        if reference[at:at+4] != thumb_call(at, 0x08017b68):
            raise ValueError('Unexpected native Options row read')
        call('display-order-'+hex(at),at,'ReadDisplayedOptionBridge')
    if reference[0x892e:0x8930] != b'\x09\x2d':
        raise ValueError('Unexpected Options loop')
    add('row-count', 0x892e, bytes((count-1, 0x2d)))
    for name, at, symbol in (('defs-init',0x8914,'EnhancedDefinitions'),('defs-render',0x9128,'EnhancedDefinitions'),('labels',0x9028,'EnhancedLabels'),('hints',0x94b8,'EnhancedHints')):
        add(name, at, struct.pack('<I', symbols[symbol]))
    add('label-base', 0x902c, bytes(4))
    manifest = output/'extension.json'
    sources = [PLUGIN/'build.py', PLUGIN/'options.c', PLUGIN/'bridges.s', PLUGIN/'options.h', charset, header, *registration_sources]
    manifest.write_text(json.dumps(dict(schema='build-extension-v1',reference_sha256=sha(reference),
        sources=[dict(path=str(p.resolve()),sha256=sha(p.read_bytes())) for p in sources],fragments=fragments),indent=2)+'\n')
    return manifest, dict(id='options', settings_byte=0x2fc3, settings_mask=sum(1 << bit for bit in used),
        original_settings_bytes=4, rows=count, symbols={k:hex(v) for k,v in symbols.items()})
