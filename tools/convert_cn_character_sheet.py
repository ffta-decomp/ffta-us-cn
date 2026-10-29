#!/usr/bin/env python3
"""Convert the supplied CN character workbook using only Python's standard library.

Preserve blank labels and duplicate Unicode aliases. The comparison establishes
only the supplied reviewed samples, not semantic correctness of every label.
"""
import argparse
import csv
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
import zipfile

from export_us_cn_glyph_table import CN_SHA256, COUNT, FONT, WIDTHS, ROOT

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_sheet(path):
    with zipfile.ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in item.findall('.//s:t', NS))
                       for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        sheets = workbook.findall('s:sheets/s:sheet', NS)
        if len(sheets) != 1:
            raise ValueError('Expected exactly one worksheet')
        relation = sheets[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        relations = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        target = next(item.get('Target') for item in relations if item.get('Id') == relation)
        member = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        xml = ET.fromstring(archive.read(member))
        rows = []
        for row in xml.findall('s:sheetData/s:row', NS):
            values = {}
            for cell in row.findall('s:c', NS):
                column = ''.join(c for c in cell.get('r') if c.isalpha())
                value = cell.find('s:v', NS)
                text = value.text if value is not None else ''
                if cell.get('t') == 's':
                    text = strings[int(text)]
                elif cell.get('t') == 'inlineStr':
                    text = ''.join(t.text or '' for t in cell.findall('s:is//s:t', NS))
                values[column] = text
            rows.append(values)
    if [rows[0].get(c) for c in 'ABC'] != ['编号', '对应Hex', '文本']:
        raise ValueError('Unexpected character worksheet header')
    result = []
    for row in rows[1:]:
        index = int(row['A'])
        if int(row['B'], 16) != index:
            raise ValueError('Decimal/hex index mismatch at ' + str(index))
        character = row.get('C') or None
        if character is not None and len(character) != 1:
            raise ValueError('Expected one Unicode character at ' + str(index))
        result.append(dict(index=index, index_hex='%X' % index,
                           token='0x%04X' % (0x8000 | index), unicode=character))
    if [row['index'] for row in result] != list(range(COUNT)):
        raise ValueError('Expected all 3175 native indices in order, without duplicates')
    return sheets[0].get('name'), result


def convert(workbook, translated, known_map, output):
    workbook, translated, known_map, output = map(Path, (workbook, translated, known_map, output))
    if output.resolve().is_relative_to(ROOT) and not output.resolve().is_relative_to(ROOT / 'config/charsets'):
        raise ValueError('In-project character tables belong under config/charsets')
    image = translated.read_bytes()
    if len(image) != 0x1000000 or sha(image) != CN_SHA256:
        raise ValueError('Expected the authenticated v1.1 Chinese ROM')
    sheet, rows = read_sheet(workbook)
    known = json.loads(known_map.read_text())
    comparisons = []
    for character, token in sorted(known.items()):
        index = token - 0x8000
        if not 0 <= index < COUNT:
            raise ValueError('Reviewed token out of range')
        actual = rows[index]['unicode']
        comparisons.append(dict(character=character, index=index, token='0x%04X' % token,
                                spreadsheet_character=actual, match=actual == character))
    aliases = defaultdict(list)
    for row in rows:
        index = row['index']
        cell = image[FONT + index * 128:FONT + (index + 1) * 128]
        row['glyph_sha256'] = sha(cell)
        row['advance'] = image[WIDTHS + index]
        if row['unicode'] is not None:
            aliases[row['unicode']].append(row['token'])
    report = dict(schema=1, source_workbook_sha256=sha(workbook.read_bytes()), sheet=sheet,
                  translated_sha256=sha(image), native_font_sha256=sha(image[FONT:WIDTHS]),
                  reviewed_map_sha256=sha(known_map.read_bytes()), native_entries=len(rows),
                  labelled_entries=sum(row['unicode'] is not None for row in rows),
                  blank_entries=sum(row['unicode'] is None for row in rows),
                  unique_unicode_characters=len(aliases),
                  duplicate_unicode_labels={c: tokens for c, tokens in sorted(aliases.items()) if len(tokens) > 1},
                  reviewed_samples=len(comparisons), matched_samples=sum(r['match'] for r in comparisons),
                  all_reviewed_samples_match=all(r['match'] for r in comparisons), comparisons=comparisons,
                  validation_scope='Only the reviewed samples are semantically compared. Other labels retain third-party provenance; blank labels remain unknown. No OCR or alternate charset order is used.')
    output.mkdir(parents=True, exist_ok=False)
    def write(name, data):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write('character-table.json', dict(schema=1, glyphs=rows))
    write('index-to-unicode.json', {str(r['index']): r['unicode'] for r in rows})
    write('unicode-to-tokens.json', dict(sorted(aliases.items())))
    write('comparison-report.json', report)
    with (output / 'character-table.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    write('manifest.json', dict(schema=1, resource_role='third-party-character-map',
          source_workbook_sha256=report['source_workbook_sha256'], translated_sha256=CN_SHA256,
          files={p.name: sha(p.read_bytes()) for p in sorted(output.iterdir())}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workbook', 'translated', 'known-map', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = convert(args.workbook, args.translated, args.known_map, args.output_dir)
    print(json.dumps({key: report[key] for key in ('native_entries', 'labelled_entries', 'blank_entries',
                     'unique_unicode_characters', 'reviewed_samples', 'matched_samples', 'all_reviewed_samples_match')}))
    if not report['all_reviewed_samples_match']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
