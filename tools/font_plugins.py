"""Resolve plugin font ownership and append styled native glyphs.

Standard-library-only build extension. Original cells, widths and indices stay
unchanged; style namespaces select appended tokens rather than replacing text.
"""
import hashlib
import json
from pathlib import Path
import struct

from plugin_info import ROOT, load_pages, load_catalogue, enabled

FONT, WIDTHS, COUNT = 0x433330, 0x4966b0, 3175
ORIGIN = 0xd00000
FONT_POINTERS = (0x13474,)
WIDTH_POINTERS = (0x13480, 0x13a7c)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(Path(path).read_bytes()))


def resolve(features, path=None):
    path = ROOT / 'plugins.json' if path is None else Path(path)
    load_pages(features, path)  # Validate the shared catalogue before resolving.
    catalogue = load_catalogue(path)
    uscn = next((p for p in catalogue if p['id'] == 'uscn'), None)
    if uscn is None or type(uscn.get('priority')) is not int:
        raise ValueError('Font catalogue requires an explicit uscn priority')
    for plugin in catalogue:
        priority = plugin.get('priority', 0)
        if type(priority) is not int or priority < 0:
            raise ValueError('Plugin priority must be a nonnegative integer')
        if plugin['id'] != 'uscn' and priority >= uscn['priority']:
            raise ValueError('uscn must have the highest plugin priority')
    fonts = sorted((p for p in catalogue if enabled(p, features) and 'font' in p and
                    ('when' not in p['font'] or features.get(p['font']['when'], False))),
                   key=lambda p: (-p.get('priority', 0), p['id']))
    if not fonts:
        return None, [], []
    bases = [p for p in fonts if p['font'].get('mode') == 'base']
    if not bases or bases[0]['id'] != 'uscn':
        raise ValueError('Font extensions require the uscn base font')
    claims, selected, ignored = {}, [], []
    for plugin in fonts:
        spec = plugin['font']
        if spec.get('mode') == 'base':
            if plugin['id'] != 'uscn':
                ignored.append(dict(plugin=plugin['id'], reason='uscn owns base glyphs'))
            continue
        if spec.get('mode') != 'append' or spec.get('style') in (None, '', 'default'):
            raise ValueError('Extra fonts must append a named style')
        if not isinstance(spec['style'], str) or not spec['style'].isascii() or not spec['style'].isidentifier():
            raise ValueError('Invalid style name')
        if spec.get('transform') != 'row_shear' or \
           type(spec.get('baseline')) is not int or not 0 <= spec['baseline'] < 16 or \
           type(spec.get('rows_per_pixel')) is not int or spec['rows_per_pixel'] <= 0:
            raise ValueError('Unsupported glyph transform')
        characters = spec.get('characters')
        if not isinstance(characters, str) or not characters or \
           any(ord(c) < 33 or 0xd800 <= ord(c) <= 0xdfff for c in characters):
            raise ValueError('Font extension needs Unicode scalar characters')
        for character in sorted(set(characters)):
            key = spec['style'], character
            if key in claims:
                owner = claims[key]
                if owner.get('priority', 0) == plugin.get('priority', 0):
                    raise ValueError('Equal-priority font style conflict: ' + character)
                ignored.append(dict(plugin=plugin['id'], style=key[0], character=character,
                                    owner=owner['id'], reason='higher-priority style owns this character'))
                continue
            claims[key] = plugin
            selected.append((plugin, character))
    return bases[0], selected, ignored


def shear(cell, advance, baseline, rows_per_pixel):
    if len(cell) != 128 or not 1 <= advance <= 16:
        raise ValueError('Invalid source glyph')
    output, right = bytearray(128), -1
    for y in range(16):
        shift = max(0, baseline - y) // rows_per_pixel
        for x in range(16):
            shade = (cell[x // 8 * 64 + y * 4 + x % 8 // 2] >> (x % 2 * 4)) & 15
            if not shade:
                continue
            destination = x + shift
            if destination >= 16:
                raise ValueError('Italic glyph would clip; choose a smaller shear')
            offset = destination // 8 * 64 + y * 4 + destination % 8 // 2
            output[offset] |= shade << (destination % 2 * 4)
            right = max(right, destination)
    return bytes(output), max(advance, right + 1)


def extend(font, widths, rows, base, selected):
    count = len(rows)
    if len(font) != count * 128 or len(widths) != count or \
       [r['index'] for r in rows] != list(range(count)):
        raise ValueError('Base font/table dimensions differ')
    mapping = {}
    for row in rows:
        index = row['index']
        if sha(font[index * 128:(index + 1) * 128]) != row['glyph_sha256'] or widths[index] != row['advance']:
            raise ValueError('Base glyph table does not match the installed font')
        if row['unicode'] is not None:
            mapping.setdefault(row['unicode'], 0x8000 | index)
    expanded, advances = bytearray(font), bytearray(widths)
    table = [dict(row, style='default', owner=base['id'], priority=base['priority']) for row in rows]
    styles = {}
    for plugin, character in selected:
        if character not in mapping:
            raise ValueError('Styled character absent from base table: ' + character)
        source = mapping[character] & 0x7fff
        spec = plugin['font']
        cell, width = shear(font[source * 128:(source + 1) * 128], widths[source],
                            spec['baseline'], spec['rows_per_pixel'])
        index = len(table)
        if index >= 0x8000:
            raise ValueError('Glyph index exceeds the native token format')
        expanded.extend(cell); advances.append(width)
        styles.setdefault(spec['style'], {})[character] = 0x8000 | index
        table.append(dict(index=index, index_hex='%X' % index, token='0x%04X' % (0x8000 | index),
                          unicode=character, glyph_sha256=sha(cell), advance=width,
                          source_index=source, style=spec['style'], owner=plugin['id'],
                          priority=plugin['priority']))
    assert expanded[:len(font)] == font and advances[:len(widths)] == widths
    return bytes(expanded), bytes(advances), table, mapping, styles


def prepare(reference, image, features, output):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Generated font resources must stay outside the source tree')
    base, selected, ignored = resolve(features)
    if base is None or not selected:
        raise ValueError('No enabled appended font glyphs')
    spec = base['font']
    if (spec.get('rom_offset'), spec.get('widths_rom_offset'), spec.get('glyph_count'), spec.get('cell_bytes')) != \
       (FONT, WIDTHS, COUNT, 128):
        raise ValueError('Unexpected uscn font contract')
    table_path = (ROOT / spec['glyph_table']).resolve()
    if not table_path.is_relative_to(ROOT / 'config/charsets'):
        raise ValueError('Base table must be an explicit project character table')
    rows = json.loads(table_path.read_text())['glyphs']
    font, widths, table, mapping, styles = extend(
        image[FONT:WIDTHS], image[WIDTHS:WIDTHS + COUNT], rows, base, selected)
    payload = font + widths
    if ORIGIN + len(payload) > len(image) or image[ORIGIN:ORIGIN + len(payload)] != b'\xff' * len(payload) or \
       reference[ORIGIN:ORIGIN + len(payload)] != b'\xff' * len(payload):
        raise ValueError('Extended font requires verified erased ROM space')
    output.mkdir(parents=True, exist_ok=False)
    def write(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    (output / 'font-4bpp.bin').write_bytes(font)
    (output / 'font-widths.bin').write_bytes(widths)
    payload_path = output / 'font-payload.bin'; payload_path.write_bytes(payload)
    for row in table:
        row['rom_offset'] = '0x%06X' % (ORIGIN + row['index'] * 128)
    write('glyph-table.json', dict(schema=1, base_glyph_count=COUNT, glyph_count=len(table), glyphs=table))
    write('glyph-map.json', mapping)
    write('style-glyph-maps.json', styles)
    for style, values in styles.items():
        # Style names are keys, never caller-controlled output paths.
        if not style.isascii() or not style.isidentifier():
            raise ValueError('Invalid style name')
        write(style + '-glyph-map.json', values)
    for site, pointer in [(p, FONT) for p in FONT_POINTERS] + [(p, WIDTHS) for p in WIDTH_POINTERS]:
        if struct.unpack_from('<I', image, site)[0] != 0x08000000 + pointer:
            raise ValueError('Native font pointer already changed at ' + hex(site))
    fragments = [dict(pin(payload_path), rom_offset=ORIGIN, kind='resource',
                      reference_sha256=sha(reference[ORIGIN:ORIGIN + len(payload)]))]
    for site, offset in [(p, ORIGIN) for p in FONT_POINTERS] + [(p, ORIGIN + len(font)) for p in WIDTH_POINTERS]:
        path = output / ('pointer-%06x.bin' % site)
        path.write_bytes(struct.pack('<I', 0x08000000 + offset))
        fragments.append(dict(pin(path), rom_offset=site, kind='data', reference_sha256=sha(reference[site:site + 4])))
    manifest = dict(schema='build-extension-v1', reference_sha256=sha(reference),
                    sources=[pin(Path(__file__)), pin(ROOT / 'plugins.json'), pin(table_path),
                             pin(ROOT / 'config/plugin-projects.lock.json')],
                    source_replacements=[], fragments=fragments)
    write('extension.json', manifest)
    report = dict(schema=1, base_plugin=base['id'], base_priority=base['priority'],
                  original_glyph_count=COUNT, glyph_count=len(table), appended_glyph_count=len(table) - COUNT,
                  font_rom_offset=ORIGIN, widths_rom_offset=ORIGIN + len(font),
                  font_sha256=sha(font), widths_sha256=sha(widths),
                  styles=styles, ignored_claims=ignored, original_cells_unchanged=True,
                  original_widths_unchanged=True, original_tokens_unchanged=True,
                  pointer_sites=list(FONT_POINTERS + WIDTH_POINTERS),
                  native_font_sha256=sha(image[FONT:WIDTHS]), recovery_credit_eligible=False)
    report['glyph_table'] = pin(output / 'glyph-table.json')
    report['default_glyph_map'] = pin(output / 'glyph-map.json')
    report['style_glyph_maps'] = pin(output / 'style-glyph-maps.json')
    write('font-report.json', report)
    return output / 'extension.json', report
