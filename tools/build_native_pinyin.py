#!/usr/bin/env python3
"""Opt-in native pinyin naming, on the exact 16 MiB US Chinese reconstruction."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from migrate_us_cn import compose, thumb_bl
import decomp_formats

ROOT = Path(__file__).resolve().parents[1]
ENGINE = decomp_formats.DECOMP_ROOT
ORIGIN = 0x08b00000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(command):
    subprocess.run([str(item) for item in command], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['retail', 'pack-dir', 'glyph-map', 'map-report', 'output-dir']:
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--rime-dictionary', type=Path,
                        default=ROOT / 'vendor/rime-pinyin-simp/pinyin_simp.dict.yaml')
    parser.add_argument('--tool-prefix', default='arm-none-eabi-')
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--source-extensions', action='store_true',
                        help='Emit a module stage for joint source replacement; no raw name-site edits')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    for path in [out, args.glyph_map, args.map_report, args.rime_dictionary]:
        if path.resolve().is_relative_to(ENGINE):
            raise ValueError('Generated outputs and licensed inputs must be external')
    out.mkdir(parents=True, exist_ok=True)
    base, base_report = compose(args.retail.read_bytes(), args.pack_dir,
                                out / 'baseline', args.tool_prefix)
    if sha(base) != base_report['target_sha256']:
        raise ValueError('Feature requires the exact Chinese baseline')
    (out / 'baseline-report.json').write_text(json.dumps(base_report, indent=2) + '\n')
    glyph_map = json.loads(args.glyph_map.read_text())
    map_report = json.loads(args.map_report.read_text())
    if map_report['glyph_map_sha256'] != sha(args.glyph_map.read_bytes()) or \
       map_report['native_font_sha256'] != sha(base[0x433330:0x4966b0]) or \
       map_report['translated_sha256'] != sha(base):
        raise ValueError('Map provenance does not match installed font')
    for token in glyph_map.values():
        if not isinstance(token, int) or not 0x8000 <= token < 0x8000 + 3175:
            raise ValueError('Candidate outside installed font')
        cell = base[0x433330 + (token & 0x7fff) * 128:0x433330 + ((token & 0x7fff) + 1) * 128]
        if any(cell[column * 64 + y * 4 + pair] for column in range(2)
               for y in [14, 15] for pair in range(4)):
            raise ValueError('Candidate has ink in rows reserved for row compaction')
    table = out / 'table'
    run([sys.executable, ROOT / 'tools/generate_optional_pinyin.py',
         '--rime-dictionary', args.rime_dictionary, '--glyph-map', args.glyph_map,
         '--output-dir', table])
    # Keep full-syllable candidate order. Missing prefix rows contain the
    # union of valid continuations, so a useful prefix never displays zero
    # candidates and an impossible next letter can be rejected immediately.
    import generate_optional_pinyin as generator
    readings = generator.parse_dictionary(args.rime_dictionary, set(glyph_map))
    prefixes = {}
    for spelling, candidates in readings.items():
        for length in range(1, len(spelling)):
            prefix = spelling[:length]
            if prefix in readings:
                continue
            bucket = prefixes.setdefault(prefix, {})
            for character, weight in candidates.items():
                bucket[character] = max(weight, bucket.get(character, -1))
    merged = dict(readings, **prefixes)
    rows, tokens, covered = generator.make_table(glyph_map, merged, {})
    coverage = json.loads((table / 'coverage.json').read_text())
    coverage.update(valid_prefix_rows=len(prefixes), syllable_count=len(readings),
        row_count=len(rows), character_reading_pairs=len(tokens),
        index_bytes=len(rows) * 8, candidate_bytes=len(tokens) * 2,
        table_bytes_excluding_compiler_padding=len(rows) * 8 + len(tokens) * 2,
        max_candidates_per_syllable=max(row[2] for row in rows),
        prefix_policy='Exact syllables unchanged; otherwise valid continuations only')
    generator.write_outputs(table, rows, tokens, coverage)
    sources = [ROOT / 'engine/pinyin/optional_pinyin.c',
               ROOT / 'engine/pinyin/optional_name_pinyin_ui.c',
               ROOT / 'engine/native_name_pinyin.c', table / 'optional_pinyin_table.c']
    objects = []
    for source in sources:
        obj = out / (source.stem + '.o')
        run([args.clang, '--target=arm-none-eabi', '-mcpu=arm7tdmi', '-mthumb',
             '-Os', '-std=c11', '-ffreestanding', '-fno-builtin',
             '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
             '-I', ROOT / 'engine/pinyin/include', '-Wall', '-Wextra', '-Werror',
             '-c', source, '-o', obj])
        objects.append(obj)
    support = ROOT / 'engine/native_name_pinyin_support.s'
    obj = out / 'native_name_pinyin_support.o'
    assembly_flags = ['--defsym', 'CJK_SOURCE_EXTENSIONS=1'] if args.source_extensions else []
    run([args.tool_prefix + 'as', '-mcpu=arm7tdmi', '-mthumb', *assembly_flags, support, '-o', obj])
    objects.append(obj)
    linker = out / 'pinyin.ld'
    linker.write_text('SECTIONS { .pinyin_tabs_bridge 0x083b42e4 : { *(.pinyin_tabs_bridge) } '
        '.pinyin_cursor_bridge 0x083b4490 : { *(.pinyin_cursor_bridge) } '
        '. = 0x08b00000; .text : { *(.text*) *(.rodata*) } '
        '/DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } '
        '.data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } }\n'
        'ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "Unexpected static RAM")\n')
    elf = out / 'pinyin.elf'
    run([args.tool_prefix + 'ld', '-T', linker, *objects, '-o', elf])
    binary = out / 'pinyin.bin'
    run([args.tool_prefix + 'objcopy', '-O', 'binary', '-j', '.text', elf, binary])
    symbols = subprocess.check_output([args.tool_prefix + 'nm', '-n', str(elf)], text=True)
    (out / 'symbols.txt').write_text(symbols)
    callback = next(int(line.split()[0], 16) | 1 for line in symbols.splitlines()
                    if line.endswith(' NativePinyinCallback'))
    payload = binary.read_bytes()
    offset = ORIGIN - 0x08000000
    if not payload or offset + len(payload) > len(base) or \
       base[offset:offset + len(payload)] != b'\xff' * len(payload):
        raise ValueError('Feature payload does not fit verified erased 16 MiB region')
    image = bytearray(base)
    image[offset:offset + len(payload)] = payload
    # Original constructors: work 205<<2, callback literal 0812A085.
    # Extend the task-owned work tail; original task destruction owns its free.
    patches = []
    for section, site, size in [('pinyin_tabs_bridge', 0x3b42e4, 8 if args.source_extensions else 12),
                               ('pinyin_cursor_bridge', 0x3b4490, 8)]:
        file = out / (section + '.bin')
        run([args.tool_prefix + 'objcopy', '-O', 'binary', '-j', '.' + section, elf, file])
        data = file.read_bytes()
        if len(data) != size or base[site:site + size] != b'\xff' * size:
            raise ValueError('Bridge exceeds authenticated CN table padding')
        image[site:site + size] = data
        patches.append(dict(rom_offset=site, cpu_address=hex(0x08000000 + site),
                            purpose='temporary isolated Thumb bridge', bytes=size))
    if not args.source_extensions:
        for site, old, new in [(0x12a326, 0x0812a91c, 0x083b4490),
                               (0x12a502, 0x08001f34, 0x083b42e4)]:
            if base[site:site + 4] != thumb_bl(site, old):
                raise ValueError('Native name call-site identity differs')
            image[site:site + 4] = thumb_bl(site, new)
            patches.append(dict(rom_offset=site, cpu_address=hex(0x08000000 + site),
                                purpose='temporary opt-in name UI call redirect', target=hex(new)))
        for site in [0x12b21a, 0x12b240]:
            if struct.unpack_from('<H', base, site)[0] != 0x21cd:
                raise ValueError('Unexpected name task allocation instruction')
            data = struct.pack('<H', 0x21e8)  # 232<<2 = 0x3a0
            image[site:site + 2] = data
            patches.append(dict(rom_offset=site, cpu_address=hex(0x08000000 + site),
                                purpose='task-owned work tail', old_bytes='cd21', new_bytes=data.hex()))
        for site in [0x12b22c, 0x12b254]:
            if struct.unpack_from('<I', base, site)[0] != 0x0812a085:
                raise ValueError('Unexpected name task callback identity')
            struct.pack_into('<I', image, site, callback)
            patches.append(dict(rom_offset=site, cpu_address=hex(0x08000000 + site),
                                purpose='native pinyin callback adapter', target=hex(callback)))
    if image[0x433330:0x4966b0] != base[0x433330:0x4966b0] or \
       image[0x4966b0:0x497317] != base[0x4966b0:0x497317]:
        raise ValueError('Native font or advance table was changed')
    (out / 'ffta-zh-pinyin.gba').write_bytes(image)
    report = dict(schema=1, baseline_sha256=sha(base), output_sha256=sha(image),
        output_bytes=len(image), native_font_unchanged=True, native_widths_unchanged=True,
        feature_enabled=True, original_cn_byte_match=False,
        source_extensions_pending=args.source_extensions, callback_entry=hex(callback),
        payload=dict(rom_offset=offset, cpu_address=hex(ORIGIN), bytes=len(payload), sha256=sha(payload)),
        patches=patches, glyph_map_sha256=sha(args.glyph_map.read_bytes()),
        sources={str(p.relative_to(ENGINE)) if p.is_relative_to(ENGINE) else p.name:
                 sha(p.read_bytes()) for p in sources + [support]},
        candidate_coverage=json.loads((table / 'coverage.json').read_text()),
        policy='Installed native font tokens only; English and feature-off CN builders unchanged')
    (out / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output_sha256': sha(image), 'payload_bytes': len(payload),
                      'output_bytes': len(image)}))


if __name__ == '__main__':
    main()
