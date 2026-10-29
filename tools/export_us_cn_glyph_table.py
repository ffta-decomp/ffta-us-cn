#!/usr/bin/env python3
"""Export persistent native glyph resources from the authenticated Chinese ROM.

The ROM owns glyph order, pixels and widths. Unicode labels are optional,
separately authenticated annotations; unknown labels remain null. Outputs are
private source resources, never disposable compiler caches or Git members.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CN_SHA256 = 'ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03'
FONT = 0x433330
WIDTHS = 0x4966B0
COUNT = 3175


def sha(data):
    return hashlib.sha256(data).hexdigest()


def export(rom_path, output_dir, glyph_map=None, map_report=None):
    rom_path, output_dir = Path(rom_path).resolve(), Path(output_dir).resolve()
    if output_dir.is_relative_to(ROOT):
        raise ValueError('Private glyph resources must remain outside the source repository')
    rom = rom_path.read_bytes()
    if sha(rom) != CN_SHA256 or len(rom) != 0x1000000:
        raise ValueError('Expected the authenticated Chinese reference ROM')
    if (glyph_map is None) != (map_report is None):
        raise ValueError('Unicode annotations require both glyph map and provenance report')
    font = rom[FONT:WIDTHS]
    labels, provenance = {}, None
    if glyph_map is not None:
        glyph_map, map_report = Path(glyph_map), Path(map_report)
        mapping = json.loads(glyph_map.read_text())
        provenance = json.loads(map_report.read_text())
        if provenance.get('translated_sha256') != CN_SHA256 or \
           provenance.get('native_font_sha256') != sha(font) or \
           provenance.get('glyph_map_sha256') != sha(glyph_map.read_bytes()):
            raise ValueError('Unicode annotations are not bound to this Chinese ROM/font')
        for character, token in mapping.items():
            if len(character) != 1 or type(token) is not int or not 0x8000 <= token < 0x8000 + COUNT:
                raise ValueError('Invalid native Unicode annotation')
            if token in labels:
                raise ValueError('Ambiguous Unicode annotation for one native token')
            labels[token] = character
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / 'font-4bpp.bin').write_bytes(font)
    (output_dir / 'font-widths.bin').write_bytes(rom[WIDTHS:WIDTHS + COUNT])
    rows = []
    for index in range(COUNT):
        cell = font[index * 128:(index + 1) * 128]
        rows.append(dict(index=index, token='0x%04X' % (0x8000 + index),
                         rom_offset='0x%06X' % (FONT + index * 128),
                         advance=rom[WIDTHS + index], unicode=labels.get(0x8000 + index),
                         glyph_sha256=sha(cell)))
    document = dict(schema=1, translated_sha256=CN_SHA256, native_font_sha256=sha(font),
                    glyph_count=COUNT, labelled_glyphs=len(labels),
                    unknown_unicode_glyphs=COUNT - len(labels), glyphs=rows)
    (output_dir / 'glyph-table.json').write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
    if glyph_map is not None:
        (output_dir / 'glyph-map.json').write_bytes(glyph_map.read_bytes())
        (output_dir / 'map-report.json').write_bytes(map_report.read_bytes())
    # Complete original 4bpp cells, including outline/shadow; not a new font.
    colors = ((0, 16, 104), (0, 0, 0), (80, 80, 80), (255, 255, 255)) + \
             tuple((index * 17, 0, 255 - index * 17) for index in range(4, 16))
    for page in range((COUNT + 511) // 512):
        pixels = bytearray(bytes(colors[0]) * (512 * 256))
        for ordinal in range(512):
            index = page * 512 + ordinal
            if index >= COUNT:
                break
            cell = font[index * 128:(index + 1) * 128]
            for y in range(16):
                for x in range(16):
                    shade = (cell[x // 8 * 64 + y * 4 + x % 8 // 2] >> (x % 2 * 4)) & 15
                    position = ((ordinal // 32 * 16 + y) * 512 + ordinal % 32 * 16 + x) * 3
                    pixels[position:position + 3] = bytes(colors[shade])
        (output_dir / ('native-atlas-%02d.ppm' % page)).write_bytes(b'P6\n512 256\n255\n' + pixels)
    manifest = dict(schema=1, resource_role='persistent-private-native-glyph-resources',
        cleanup_policy='Retain as build input; never classify this directory as compiler cache.',
        translated_sha256=CN_SHA256, unicode_provenance=provenance,
        files={p.name: sha(p.read_bytes()) for p in sorted(output_dir.iterdir()) if p.is_file()})
    (output_dir / 'resource-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--translated', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--glyph-map', type=Path)
    parser.add_argument('--map-report', type=Path)
    args = parser.parse_args()
    result = export(args.translated, args.output_dir, args.glyph_map, args.map_report)
    print(json.dumps({key: result[key] for key in ('glyph_count', 'labelled_glyphs', 'unknown_unicode_glyphs',
                                                   'translated_sha256', 'native_font_sha256')}))


if __name__ == '__main__':
    main()
