#!/usr/bin/env python3
"""Extract/rebuild a fixed-address optional US Chinese native text asset pack.

Generated private assets must stay outside this repository. No whole-ROM diff is
used as an asset fallback. Unknown entry bytes remain explicitly source-pinned.
The pack is a component pack, not a claim that all translated ROM changes are text.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import decomp_formats  # Explicit FFTA_DECOMP_ROOT, read-only codecs.
import extract_resources as e
from scene_text_codec import encode_tokens, parse_compression, encode_compression
from font_codec import decode_atlas, encode_atlas

BASE = 0x08000000
RETAIL = '43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19'
CHINESE = 'ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, document):
    path.write_text(json.dumps(document, indent=2, ensure_ascii=True) + '\n')


def u16(data, offset):
    return struct.unpack_from('<H', data, offset)[0]


def ptr(data, site):
    value = e.u32(data, site) - BASE
    require(0 <= value < len(data), 'Pointer outside ROM')
    return value


def decode_record(data, offset, flagged=True):
    flags = u16(data, offset) if flagged else 0
    cursor = offset + (2 if flagged else 0)
    operations = None
    tail = b''
    if flagged and flags & 2:
        size = int.from_bytes(data[cursor:cursor + 4], 'big')
        require(0 < size < 100000, 'Invalid decompressed text size')
        operations, payload, consumed = parse_compression(memoryview(data)[cursor + 4:], size)
        stored_size = 6 + consumed
    else:
        payload = data[cursor:cursor + 8192]
        stored_size = None
    item = (e.decode_alt_word if flags & 1 else e.decode_word)(payload, 0)
    result = dict(rom_offset=offset, flags=flags, flagged=flagged,
                  encoding='alternate' if flags & 1 else 'standard',
                  tokens=item['tokens'], decoded_sha256=item['raw_sha256'])
    decoded = encode_tokens(result)
    require(decoded == payload[:item['size']], 'Token round-trip mismatch')
    if operations is not None:
        tail = payload[item['size']:]
        result.update(compression_ops=operations, decoded_tail_hex=tail.hex())
    if stored_size is None:
        stored_size = len(decoded) + (2 if flagged else 0)
    result['stored_bytes'] = stored_size
    require(encode_record(result) == data[offset:offset + stored_size],
            'Stored record round-trip mismatch')
    return result


def encode_record(record):
    payload = encode_tokens(record)
    result = record['flags'].to_bytes(2, 'little') if record['flagged'] else b''
    if 'compression_ops' in record:
        decoded = payload + bytes.fromhex(record['decoded_tail_hex'])
        commands = encode_compression(record['compression_ops'])
        _, check, consumed = parse_compression(commands, len(decoded))
        require(check == decoded and consumed == len(commands), 'Compression round-trip mismatch')
        result += len(decoded).to_bytes(4, 'big') + commands
    else:
        result += payload
    return result


def page_layout(data, start):
    first = u16(data, start)
    require(4 <= first < 16384 and first % 2 == 0, 'Invalid page header boundary')
    slots = [u16(data, start + 2 * i) for i in range(first // 2)]
    require(0xffff in slots, 'Page header has no FFFF terminator')
    count = slots.index(0xffff)
    offsets = slots[:count]
    require(offsets and all(first <= n < 0xffff for n in offsets), 'Invalid page pointer')
    return first, offsets


def source_pages(data):
    pages, tables = {}, []
    for family, site, count in [('scene', 0x9a88, 63), ('fixed', 0x18050, 27)]:
        master = ptr(data, site)
        tables.append((family + '_master', master, count * 4))
        for i in range(count):
            value = e.u32(data, master + i * 4)
            if family == 'fixed':
                if value == 0:
                    continue
                target = value - BASE
            else:
                target = master + value
            if family == 'scene' and i == 61:
                tables.append(('scene_nested61', target, 26 * 4))
                for j in range(26):
                    page = master + e.u32(data, target + 4 * j)
                    pages.setdefault(page, []).append(dict(family=family, page=[i, j]))
            else:
                pages.setdefault(target, []).append(dict(family=family, page=i))
    return pages, tables


def extract_pack(retail, translated, output_dir, extra_consumers=()):
    """Write source-pinned text/font segments and typed reconstruction metadata.

    extra_consumers is an explicit iterable of (original_page, translated_page)
    pairs established by the caller's actual-consumer evidence. It is not a scan.
    """
    require(sha(retail) == RETAIL and sha(translated) == CHINESE, 'Wrong ROM identities')
    require(len(retail) == len(translated) == 0x1000000, 'Expected 16 MiB ROMs')
    out = Path(output_dir).resolve()
    require(not out.is_relative_to(Path(__file__).resolve().parents[1]), 'External output required')
    out.mkdir(parents=True, exist_ok=True)
    payload_dir = out / 'segments'
    payload_dir.mkdir(exist_ok=True)
    pages, tables = source_pages(translated)
    roots, consumer_links = [], []
    for original, _, count, _ in e.CONSUMER_TEXT_PAGES:
        pattern = (original + BASE).to_bytes(4, 'little')
        refs = []
        cursor = 0
        while True:
            site = retail.find(pattern, cursor)
            if site < 0:
                break
            if site % 4 == 0:
                refs.append(site)
            cursor = site + 1
        for site in refs:
            target = ptr(translated, site)
            pages.setdefault(target, []).append(dict(family='consumer', original_page=original,
                                                      literal_site=site, original_count=count))
            consumer_links.append(dict(original_page=original, translated_page=target,
                                       literal_site=site, moved=target != original))
    for original, target in extra_consumers:
        require(0 <= original < len(retail) and 0 <= target < len(translated), 'Bad extra consumer')
        page_layout(retail, original)
        page_layout(translated, target)
        pages.setdefault(target, []).append(dict(family='explicit_consumer', original_page=original))
    word_records, word_tables = {}, []
    for name, (site, count) in e.WORD_TABLES.items():
        table = ptr(translated, site)
        tables.append(('words:' + name, table, count * 4))
        word_tables.append(dict(family=name, root_site=site, table=table, count=count))
        for i in range(count):
            value = e.u32(translated, table + i * 4)
            if not value:
                continue
            offset = value - BASE
            require(0 <= offset < len(translated), 'Word pointer outside ROM')
            word_records.setdefault(offset, []).append(dict(family=name, index=i))
    segments, opaque = [], []
    def add(kind, start, end, records=(), **metadata):
        require(0 <= start < end <= len(translated), 'Asset segment outside ROM')
        raw = translated[start:end]
        name = f'{len(segments):05d}-{kind.replace(":", "-")}-{start:06x}.bin'
        (payload_dir / name).write_bytes(raw)
        item = dict(kind=kind, rom_offset=start, cpu_address=BASE + start, bytes=len(raw),
                    source_sha256=sha(raw), retail_span_sha256=sha(retail[start:end]),
                    payload='segments/' + name, records=list(records), **metadata)
        segments.append(item)
    for kind, start, size in tables:
        add(kind, start, start + size, role='native_pointer_table')
    for start, bindings in sorted(pages.items()):
        first, relative = page_layout(translated, start)
        distinct = sorted(set(relative))
        records, unknown = [], []
        end = start + first
        for index, offset in enumerate(distinct):
            address = start + offset
            limit = start + distinct[index + 1] if index + 1 < len(distinct) else None
            try:
                record = decode_record(translated, address)
                require(limit is None or address + record['stored_bytes'] <= limit,
                        'Record overlaps next page entry')
                records.append(record)
                end = max(end, address + record['stored_bytes'])
            except (ValueError, IndexError, struct.error) as error:
                # Four-byte style+zero placeholders occur in supplied ROM.
                # Their semantics are unknown; preserve authenticated bytes.
                bound = limit if limit is not None else address + 4
                unknown.append(dict(rom_offset=address, end_exclusive=bound, reason=str(error),
                                    interpretation='opaque source bytes; no invented token'))
                end = max(end, bound)
        # Preserve only immediate source FF/zero allocation padding (<=31B).
        # A later pointer target is a hard boundary, never guessed free space.
        next_targets = [n for n in list(pages) + list(word_records) if n > start]
        next_target = min(next_targets) if next_targets else len(translated)
        typed_end = end
        unbound = []
        if start >= 0xA80000:
            # New text allocations have a source FF-fill boundary before the
            # next authenticated target. Keep unreferenced tail records too:
            # reproducing the ROM is broader than preserving retail IDs.
            marker = translated.find(b'\xff' * 16, end, next_target)
            if marker >= 0:
                end = marker
                cursor = typed_end
                while cursor < end:
                    if translated[cursor] == 0:
                        cursor += 1  # Source record separator, not a token.
                    if cursor >= end:
                        break
                    try:
                        record = decode_record(translated, cursor)
                        require(cursor + record['stored_bytes'] <= end,
                                'Unbound record exceeds allocation tail')
                        record['binding_status'] = 'unreferenced physical tail; not assigned a text ID'
                        records.append(record)
                        unbound.append(cursor)
                        cursor += record['stored_bytes']
                    except (ValueError, IndexError, struct.error) as error:
                        unknown.append(dict(rom_offset=cursor, end_exclusive=end,
                            reason='Unreferenced page allocation tail: ' + str(error),
                            interpretation='opaque source storage; no invented token or ID'))
                        break
        rounded = (end + 31) & ~31
        if rounded <= next_target and all(b in (0, 255) for b in translated[end:rounded]):
            end = rounded
        add('text_page', start, end, records=records, bindings=bindings,
            unreferenced_tail_records=unbound,
            header_bytes=first, pointer_slots_before_ffff=len(relative),
            header_hex=translated[start:start + first].hex(), opaque=unknown,
            count_scope='header slots, not asserted runtime text-ID count')
        opaque.extend(unknown)
    word_starts = sorted(word_records)
    for index, start in enumerate(word_starts):
        bindings = word_records[start]
        record = decode_record(translated, start, False)
        end = start + record['stored_bytes']
        next_start = word_starts[index + 1] if index + 1 < len(word_starts) else None
        if next_start is not None and 0 < next_start - end <= 31:
            trailing = translated[end:next_start]
            if all(value in (0, 255) for value in trailing):
                end = next_start
        # Last words of a table still carry the source's extra zero separator
        # even when the next table has a much larger FF allocation gap.
        zero_limit = min(next_start if next_start is not None else len(translated), end + 31)
        while end < zero_limit and translated[end] == 0:
            end += 1
        add('word_string', start, end, records=[record], bindings=bindings,
            trailing_bytes=end - start - record['stored_bytes'])
    font = ptr(translated, e.FONT_POINTER_OFFSET)
    size = e.FONT_GLYPH_COUNT * 128
    rawfont = translated[font:font + size]
    require(encode_atlas(decode_atlas(rawfont, e.FONT_GLYPH_COUNT, 64),
                         e.FONT_GLYPH_COUNT, 64) == rawfont, 'Font codec round-trip mismatch')
    add('font', font, font + size, glyph_count=e.FONT_GLYPH_COUNT, glyph_bytes=128,
        codec_roundtrip=True)
    width = ptr(translated, 0x13480)
    add('font_widths', width, width + e.FONT_GLYPH_COUNT, glyph_count=e.FONT_GLYPH_COUNT)
    manifest = dict(schema='ffta-us-cn-fixed-text-layout-v1', retail_sha256=RETAIL,
                    translated_sha256=CHINESE, rom_bytes=len(retail), segments=segments,
                    word_tables=word_tables, consumer_links=consumer_links,
                    opaque_records=len(opaque), limitations=[
                        'Asset component pack, not whole-ROM diff coverage.',
                        'Unknown records preserve authenticated source bytes, not invented semantics.',
                        'No glyph codes, addresses, flags, aliasing or compression choices changed.',
                        'Unicode mapping is not inferred from another ROM charset.'])
    write_json(out / 'manifest.json', manifest)
    check = build_segments(out)
    require(all(data == translated[offset:offset + len(data)] for offset, data in check),
            'Rebuilt asset differs from translated source')
    return manifest


def build_segments(pack_dir):
    """Re-encode every typed record; return exact fixed-position component spans."""
    root = Path(pack_dir)
    manifest = json.loads((root / 'manifest.json').read_text())
    result = []
    for segment in manifest['segments']:
        raw = bytearray((root / segment['payload']).read_bytes())
        require(len(raw) == segment['bytes'] and sha(raw) == segment['source_sha256'],
                'Asset payload identity mismatch')
        for record in segment['records']:
            payload = encode_record(record)
            offset = record['rom_offset'] - segment['rom_offset']
            require(0 <= offset and offset + len(payload) <= len(raw), 'Record outside segment')
            raw[offset:offset + len(payload)] = payload
        if segment['kind'] == 'font':
            raw = bytearray(encode_atlas(decode_atlas(raw, segment['glyph_count'], 64),
                                         segment['glyph_count'], 64))
        require(sha(raw) == segment['source_sha256'], 'Re-encoded segment mismatch')
        result.append((segment['rom_offset'], bytes(raw)))
    return result


def rebuild(retail, pack_dir):
    require(sha(retail) == RETAIL, 'Wrong retail identity')
    output = bytearray(retail)
    for offset, data in build_segments(pack_dir):
        output[offset:offset + len(data)] = data
    require(len(output) == len(retail), 'ROM size changed')
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retail', required=True, type=Path)
    parser.add_argument('--translated', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--extra-consumers', type=Path,
                        help='Explicit JSON array of [original_page, translated_page] pairs')
    args = parser.parse_args()
    extra = json.loads(args.extra_consumers.read_text()) if args.extra_consumers else []
    result = extract_pack(args.retail.read_bytes(), args.translated.read_bytes(), args.output_dir, extra)
    print(json.dumps(dict(segments=len(result['segments']), opaque_records=result['opaque_records'])))


if __name__ == '__main__':
    main()
