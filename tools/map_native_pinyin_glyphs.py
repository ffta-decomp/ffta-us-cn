#!/usr/bin/env python3
"""Derive conservative Unicode labels for already-installed CN glyph cells.

Only exact foreground stroke identities are accepted, modulo bbox translation.
No scaling, fuzzy match, new cells, or source charset/code ordering is assumed.
All ambiguous source labels and target cells are excluded.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CN_SHA = 'ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03'
FONT_SHA = '07ab9c83358aff167ab45c6b96b63c27f935819d409870af8e9e873f93c07e24'
CHARSET_SHA = '4f76f5e2a90c93f7b34faa987561492e6f361d75fb00b366ac7dceb88980b778'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stroke(cell):
    pixels = []
    for y in range(16):
        for x in range(16):
            value = cell[(x // 8) * 64 + y * 4 + (x % 8) // 2]
            if (value >> (4 * (x % 2))) & 15 == 3:
                pixels.append((x, y))
    if not pixels:
        return None
    left = min(x for x, _ in pixels)
    top = min(y for _, y in pixels)
    return tuple((x - left, y - top) for x, y in pixels)


def derive(rom, font, charset):
    if sha(rom) != CN_SHA or sha(font) != FONT_SHA or sha(charset) != CHARSET_SHA:
        raise ValueError('Unrecognized input identity')
    labels = json.loads(charset)[0]
    source, target = defaultdict(set), defaultdict(set)
    source_label_cells = defaultdict(set)
    for index in range(len(font) // 128):
        label = labels.get(str(index))
        if label and len(label) == 1 and '\u3400' <= label <= '\u9fff':
            source_label_cells[label].add(index)
            shape = stroke(font[index * 128:(index + 1) * 128])
            if shape:
                source[shape].add(label)
    installed = rom[0x433330:0x4966b0]
    for index in range(len(installed) // 128):
        shape = stroke(installed[index * 128:(index + 1) * 128])
        if shape:
            target[shape].add(index)
    mapping, ambiguous = {}, []
    for shape, characters in source.items():
        cells = target.get(shape, set())
        if len(characters) == len(cells) == 1 and \
           len(source_label_cells[next(iter(characters))]) == 1:
            mapping[next(iter(characters))] = 0x8000 | next(iter(cells))
        elif cells:
            ambiguous.append({'characters': sorted(characters), 'cells': sorted(cells)})
    # A label occurring in multiple source cells is also unsafe.
    inverse = defaultdict(list)
    for character, token in mapping.items():
        inverse[token].append(character)
    if any(len(items) != 1 for items in inverse.values()):
        raise ValueError('Non-injective native token map')
    return mapping, ambiguous, sha(installed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['translated', 'source-font', 'source-charset', 'output-dir']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    for path in vars(args).values():
        if path.resolve().is_relative_to(ROOT):
            raise ValueError('Licensed inputs and generated maps must remain external')
    mapping, ambiguous, font_sha = derive(args.translated.read_bytes(),
        args.source_font.read_bytes(), args.source_charset.read_bytes())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data = json.dumps(mapping, ensure_ascii=True, sort_keys=True).encode()
    (args.output_dir / 'glyph-map.json').write_bytes(data)
    report = dict(schema=1, translated_sha256=CN_SHA, source_font_sha256=FONT_SHA,
        source_charset_sha256=CHARSET_SHA, native_font_sha256=font_sha,
        glyph_map_sha256=sha(data), mapped_characters=len(mapping),
        excluded_ambiguities=ambiguous,
        proof='Exact shade-3 foreground stroke identity modulo bbox translation; pinned source Unicode labels',
        limitations='Not full 128-byte cell equality or independent manual semantic verification',
        native_font_unchanged=True, native_token_formula='0x8000 | original cell index')
    (args.output_dir / 'map-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'mapped_characters': len(mapping), 'glyph_map_sha256': sha(data)}))


if __name__ == '__main__':
    main()
