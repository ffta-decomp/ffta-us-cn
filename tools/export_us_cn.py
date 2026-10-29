#!/usr/bin/env python3
"""Export pinned US v1.1 CN resources and prove a full 16 MiB byte match.

All outputs are persistent private resources. Rebuilding uses authenticated US
retail, the exported typed resource pack and readable compatibility assembly;
it does not consume the translated ROM or an opaque whole-ROM diff.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
from export_us_cn_glyph_table import export as export_glyphs, CN_SHA256
from ips_patch import encode_patch, apply_patch
from migrate_us_cn import ROOT, import_pack, compose
from us_cn_text_layout import encode_record
from verify_vendor import verify


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def preview(tokens, labels):
    """Annotations only. Native tokens remain the authoritative representation."""
    output = []
    for token in tokens:
        kind = token['type']
        if kind == 'full_glyph':
            code = token['code']
            output.append(labels.get(0x8000 | code, '@[U:%04X]' % code))
        elif kind == 'half_glyph':
            output.append('@[H:%02X]' % token['code'])
        elif kind == 'control_eos':
            output.append('@[EOS]')
        else:
            output.append('@[C:%02X:%s]' % (token['code'], token['parameters_hex']))
    return ''.join(output)


def verify_reference_components(retail, translated, rebuilt, layout):
    """Audit loader changes, runtime replacement tables and startup assets."""
    checked = []

    def check(name, start, size, role):
        if start < 0 or size <= 0 or start + size > len(rebuilt):
            raise ValueError('Reference component outside ROM: ' + name)
        actual = rebuilt[start:start + size]
        expected = translated[start:start + size]
        if actual != expected:
            raise ValueError('Reference component differs: ' + name)
        checked.append(dict(name=name, rom_offset=start, bytes=size, role=role,
                            original_us_sha256=sha(retail[start:start + size]),
                            translated_sha256=sha(expected), rebuilt_sha256=sha(actual),
                            exact=True))

    check('original-resource-loader-with-cn-modification', 0x5318, 0xbc,
          'Original loader, including its CN resource-override continuation')
    check('cn-resource-copy-function', 0x3b4220, 0x42,
          'Header-sized native resource copy function')
    check('cn-resource-override-function', 0x3b4270, 0x6c,
          'Runtime resource identity/key lookup and RAM copy')
    check('cn-startup-function', 0xa7fc00, 0x1b0,
          'Original Chinese splash/display startup compatibility source')
    check('cn-startup-entry-branch', 0xec, 4, 'Original startup redirection')
    for number, row in enumerate(layout['copy_calls']):
        check('resource-copy-call-%02d' % number, int(row['call_rom'], 16), 4,
              'Native call redirected to the CN copy loader')
    tables = layout['replacement_tables']
    for address in tables['identity_literals']:
        check('resource-identity-literal-' + address, int(address, 16), 4,
              'Native identity or replacement-table pointer')
    for number, table in enumerate(tables['tables']):
        begin = int(table['table_rom'], 16)
        check('resource-override-table-%d' % number, begin, (len(table['rows']) + 1) * 8,
              'Typed key/size/source entries plus original sentinel')
        for row in table['rows']:
            check('override-%d-key-%d-payload' % (number, row['key']),
                  int(row['source_rom'], 16), row['byte_count'],
                  'Original replacement graphics/resource payload')
    # The ARM startup routine's own source/length/DMA literals identify the
    # complete first-screen bitmap copied to VRAM, rather than a guessed asset.
    import struct
    source, destination, control = [struct.unpack_from('<I', rebuilt, offset)[0]
                                    for offset in (0xa7fd40, 0xa7fd48, 0xa7fd50)]
    if source != 0x08a6d000 or destination != 0x06000000 or control != 0x84004b00:
        raise ValueError('Chinese first-screen copy contract differs')
    check('cn-first-screen-bitmap', source - 0x08000000, (control & 0xffff) * 4,
          'Startup DMA source: complete first-screen bitmap, 240x160x16bpp')
    return dict(schema=1, all_exact=True, original_loader_entry='0x08005319',
                runtime_behavior='Original loader plus CN resource replacement into RAM',
                resources_replaced_at_runtime=True, rom_repatched_at_runtime=False,
                first_screen_bytes=(control & 0xffff) * 4, components=checked,
                recovery_credit_eligible=False)


def export(retail_path, translated_path, output_dir, tool_prefix='arm-none-eabi-',
           glyph_map=None, map_report=None):
    verify()
    output_dir = Path(output_dir).resolve()
    if output_dir.is_relative_to(ROOT):
        raise ValueError('Private exports must remain outside the source repository')
    if output_dir.exists():
        raise ValueError('Use a new persistent resource directory; existing exports are never overwritten')
    if (glyph_map is None) != (map_report is None):
        raise ValueError('Unicode annotations require both glyph map and provenance report')
    retail_path, translated_path = Path(retail_path).resolve(), Path(translated_path).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    pack = output_dir / 'pack'
    # This authenticates complete input hashes and reconstructs typed text,
    # pointers, compression operations, native glyphs and resource metadata.
    translated = import_pack(retail_path, translated_path, pack)
    retail = retail_path.read_bytes()
    glyphs = export_glyphs(translated_path, output_dir / 'glyphs', glyph_map, map_report)
    labels = {int(row['token'], 16): row['unicode'] for row in glyphs['glyphs'] if row['unicode']}
    text_manifest = json.loads((pack / 'text/manifest.json').read_text())
    count, stored_bytes = 0, 0
    with (output_dir / 'text-records.jsonl').open('w', encoding='utf-8') as stream:
        groups = [(segment['kind'], segment.get('role'), segment['records'])
                  for segment in text_manifest['segments'] if segment['records']]
        groups.append(('inline', 'native inline token streams',
                       json.loads((pack / 'inline-native-text.json').read_text())))
        for family, role, records in groups:
            for record in records:
                encoded = encode_record(record)
                offset = record['rom_offset']
                if encoded != translated[offset:offset + len(encoded)]:
                    raise ValueError('Text record is not byte-exact at 0x%X' % offset)
                item = dict(family=family, role=role, record=record,
                            stored_sha256=sha(encoded),
                            annotated_preview=preview(record['tokens'], labels))
                stream.write(json.dumps(item, ensure_ascii=False, separators=(',', ':')) + '\n')
                count += 1
                stored_bytes += len(encoded)
    # Compatibility assembly is compiled only inside a task-owned temporary
    # directory. The resulting ROM is compared in memory, never exported here.
    with tempfile.TemporaryDirectory(prefix='ffta-us-cn-bytecheck-') as temporary:
        rebuilt, rebuild_report = compose(retail, pack, Path(temporary), tool_prefix)
    mismatches = sum(a != b for a, b in zip(rebuilt, translated))
    if len(rebuilt) != len(translated) or mismatches:
        raise ValueError('Export reconstruction differs from Chinese reference')
    layout = json.loads((pack / 'layout.json').read_text())
    component_report = verify_reference_components(retail, translated, rebuilt, layout)
    write_json(output_dir / 'reference-components.json', component_report)
    patch = encode_patch(retail, rebuilt)
    reference_patch = encode_patch(retail, translated)
    if patch != reference_patch:
        raise ValueError('Canonical rebuilt IPS differs byte-for-byte from reference IPS')
    if apply_patch(retail, patch) != translated:
        raise ValueError('IPS round trip differs from Chinese reference')
    patch_name = 'ffta-us-cn-v1.1-reference.ips'
    (output_dir / patch_name).write_bytes(patch)
    (output_dir / 'plugins.json').write_bytes((ROOT / 'plugins.json').read_bytes())
    write_json(output_dir / 'patches.json', dict(
        schema=1, profile='exact-us-v1.1-cn-reference', enabled_plugins=['uscn'],
        pinyin_enabled=False, link_fix_enabled=False, info_enabled=False,
        catalogue_role='Available plugin metadata; not all entries are enabled in this reference.',
        ips=dict(path=patch_name, input_sha256=sha(retail), output_sha256=sha(rebuilt),
                 bytes=len(patch), sha256=sha(patch)),
        resource_components=rebuild_report['components'],
        compatibility_source='pack/engine/us_cn_hooks.s',
        layout_rules='pack/layout.json', recovery_credit_eligible=False))
    result = dict(schema=1, status='byte-match', rom_bytes=len(rebuilt),
        retail_sha256=sha(retail), translated_sha256=sha(translated),
        rebuilt_sha256=sha(rebuilt), differing_bytes=mismatches,
        ips_round_trip_exact=True, canonical_reference_ips_exact=True,
        canonical_reference_ips_sha256=sha(reference_patch),
        reference_components_exact=component_report['all_exact'],
        first_screen_bytes_checked=component_report['first_screen_bytes'],
        native_glyph_count=glyphs['glyph_count'],
        unicode_labelled_glyphs=glyphs['labelled_glyphs'],
        native_text_records_checked=count, stored_text_record_bytes=stored_bytes,
        scope='Pinned native text families, pointer tables, glyphs, widths, resources and compatibility code. '
              'Unknown Unicode labels stay explicit native codes. No physical/emulator acceptance is implied.',
        translated_rom_used_by_rebuild=False, opaque_rom_diff_used_by_rebuild=False,
        resource_role='persistent-private-build-inputs',
        cleanup_policy='Retain this export; it is not a build cache.')
    write_json(output_dir / 'byte-match.json', result)
    files = {str(p.relative_to(output_dir)): sha(p.read_bytes())
             for p in sorted(output_dir.rglob('*')) if p.is_file()}
    sources = ['tools/export_us_cn.py', 'tools/export_us_cn_glyph_table.py',
               'tools/migrate_us_cn.py', 'tools/us_cn_text_layout.py',
               'tools/us_cn_resource_layout.py', 'tools/assemble_us_cn_hooks.py',
               'tools/ips_patch.py', 'config/us-cn-reference-layout.json',
               'engine/us_cn_hooks.s', 'plugins.json', 'config/dependencies.lock.json']
    write_json(output_dir / 'export-manifest.json', dict(
        schema=1, role='persistent-private-build-inputs',
        source_sha256={name: sha((ROOT / name).read_bytes()) for name in sources},
        files=files, byte_match_report='byte-match.json'))
    return result


def verify_export(retail_path, export_dir, tool_prefix='arm-none-eabi-', translated_path=None):
    verify()
    directory = Path(export_dir).resolve()
    manifest = json.loads((directory / 'export-manifest.json').read_text())
    for name, expected in manifest['files'].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or sha(path.read_bytes()) != expected:
            raise ValueError('Export file identity mismatch: ' + name)
    baseline = Path(retail_path).read_bytes()
    with tempfile.TemporaryDirectory(prefix='ffta-us-cn-recheck-') as temporary:
        rebuilt, _ = compose(baseline, directory / 'pack', Path(temporary), tool_prefix)
    expected = json.loads((directory / 'byte-match.json').read_text())
    if translated_path is not None:
        verify_reference_components(baseline, Path(translated_path).read_bytes(), rebuilt,
                                    json.loads((directory / 'pack/layout.json').read_text()))
    if expected['translated_sha256'] != CN_SHA256 or len(rebuilt) != 0x1000000 or \
       len(rebuilt) != expected['rom_bytes'] or sha(rebuilt) != CN_SHA256:
        raise ValueError('Rebuilt export differs from authenticated Chinese reference')
    if translated_path is not None and rebuilt != Path(translated_path).read_bytes():
        raise ValueError('Rebuilt export differs byte-for-byte from supplied Chinese ROM')
    patch = directory / 'ffta-us-cn-v1.1-reference.ips'
    if apply_patch(baseline, patch.read_bytes()) != rebuilt:
        raise ValueError('Export IPS differs from source/resource reconstruction')
    glyphs = json.loads((directory / 'glyphs/glyph-table.json').read_text())
    for row in glyphs['glyphs']:
        offset = int(row['rom_offset'], 16)
        if sha(rebuilt[offset:offset + 128]) != row['glyph_sha256'] or \
           rebuilt[0x4966b0 + row['index']] != row['advance']:
            raise ValueError('Native glyph table differs from reconstructed ROM')
    records = 0
    with (directory / 'text-records.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            item = json.loads(line)
            data = encode_record(item['record'])
            offset = item['record']['rom_offset']
            if data != rebuilt[offset:offset + len(data)] or sha(data) != item['stored_sha256']:
                raise ValueError('Exported text differs from reconstructed ROM')
            records += 1
    if records != expected['native_text_records_checked']:
        raise ValueError('Exported text inventory is incomplete')
    return dict(status='byte-match', rebuilt_sha256=sha(rebuilt),
                rom_bytes=len(rebuilt), native_text_records_checked=records,
                native_glyphs_checked=len(glyphs['glyphs']), ips_round_trip_exact=True,
                direct_translated_byte_comparison=translated_path is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retail', required=True, type=Path)
    parser.add_argument('--translated', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output-dir', type=Path)
    mode.add_argument('--verify-export', type=Path)
    parser.add_argument('--tool-prefix', default='arm-none-eabi-')
    parser.add_argument('--glyph-map', type=Path)
    parser.add_argument('--map-report', type=Path)
    args = parser.parse_args()
    if args.verify_export:
        result = verify_export(args.retail, args.verify_export, args.tool_prefix, args.translated)
    else:
        if args.translated is None:
            parser.error('--translated is required to export')
        result = export(args.retail, args.translated, args.output_dir,
                        args.tool_prefix, args.glyph_map, args.map_report)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
