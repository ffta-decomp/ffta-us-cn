"""Fixed-layout US-CN resource extraction; never imports executable code.

Only data in A50000:A7FC00 and the three explicitly identified override
row tables is accepted. Payload formats not established by consumer evidence
remain labelled opaque. Generated content must live outside the source tree.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

BASE = 0x08000000
HIGH_START, HIGH_END = 0xA50000, 0xA7FC00
CN_SHA256 = 'ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build_segments(manifest_path):
    """Return (ROM offset, bytes, metadata) triples, reconstructing typed fields."""
    path = Path(manifest_path)
    manifest = json.loads(path.read_text())
    result = []
    for segment in manifest['segments']:
        kind = segment['encoding']
        if kind == 'resource_header':
            data = struct.pack('<HH', segment['byte_count'], segment['reserved_u16'])
        elif kind == 'override_table':
            data = b''.join(struct.pack('<HHI', row['key'], row['byte_count'], row['source_cpu'])
                            for row in segment['rows']) + bytes.fromhex(segment['sentinel_hex'])
        elif kind == 'u32_words':
            data = struct.pack('<' + 'I'*len(segment['words']), *segment['words'])
        elif kind == 'fill':
            data = bytes([segment['fill_byte']]) * segment['length']
        elif kind == 'asset':
            data = (path.parent / segment['asset']).read_bytes()
        else:
            raise ValueError(f'Unsupported encoding {kind}')
        if len(data) != segment['length'] or sha(data) != segment['sha256']:
            raise ValueError(f"Invalid resource segment {segment['name']}")
        result.append((segment['rom_offset'], data, segment))
    return result


def extract(rom_path, call_map_path, tables_path, output_dir):
    rom = Path(rom_path).read_bytes()
    if len(rom) != 0x1000000 or sha(rom) != CN_SHA256:
        raise ValueError('Expected the authenticated 16 MiB US-CN reference')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'assets').mkdir(exist_ok=True)
    segments, used = [], bytearray(HIGH_END - HIGH_START)

    def add(offset, length, name, classification, encoding='asset', **fields):
        data = rom[offset:offset+length]
        if len(data) != length:
            raise ValueError('Out of bounds')
        if HIGH_START <= offset < HIGH_END:
            start = offset-HIGH_START
            if offset+length > HIGH_END or any(used[start:start+length]):
                raise ValueError(f'Overlapping resource {name}')
            used[start:start+length] = bytes([1])*length
        record = dict(name=name, rom_offset=offset, rom_end_exclusive=offset+length,
                      cpu_address=BASE+offset, length=length, classification=classification,
                      encoding=encoding, sha256=sha(data), **fields)
        if encoding == 'asset':
            filename = f'assets/{offset:08X}-{name}.bin'
            (output / filename).write_bytes(data)
            record['asset'] = filename
        segments.append(record)

    calls = json.loads(Path(call_map_path).read_text())
    for offset in sorted({int(row['source_new_rom'],16) for row in calls}):
        length, reserved = struct.unpack_from('<HH', rom, offset)
        if not length or length % 4:
            raise ValueError('Copy resource length must be a positive word multiple')
        add(offset,4,f'copy-{offset:X}-header','copy-helper length and reserved header',
            'resource_header',byte_count=length,reserved_u16=reserved,
            consumers=[row for row in calls if int(row['source_new_rom'],16)==offset])
        add(offset+4,length,f'copy-{offset:X}-payload','copy-helper raw payload; pixel format not inferred')

    tables = json.loads(Path(tables_path).read_text())['tables']
    for index, table in enumerate(tables):
        rows = []
        for row in table['rows']:
            offset = int(row['source_rom'],16)
            source = int(row['source_cpu'],16)
            rows.append(dict(key=row['key'],byte_count=row['byte_count'],source_cpu=source))
            add(offset,row['byte_count'],f'override-{index}-{row["key"]}',
                'replacement payload referenced by key/byte-count/source table')
        start, sentinel = int(table['table_rom'],16), int(table['sentinel_rom'],16)
        add(start,sentinel+8-start,f'override-table-{index}',
            'u16 key/u16 byte count/u32 ROM pointer rows and 8-byte FF sentinel',
            'override_table',rows=rows,sentinel_hex=rom[sentinel:sentinel+8].hex())

    # Original fixed-size graphics reads establish these complete consumer spans.
    # 2B8E8 -> SWI 0C copies 528 words from SceneBaseGraphics to VRAM.
    add(0x3BE6B4,528*4,'scene-base-graphics',
        'raw graphics consumer span: 2B8E8 copy528words to VRAM06015C00')
    # 135E88 -> SWI 0B copies 16BC halfwords. This read extent overlaps
    # the next source pointer9675AC by4bytes; no allocation-boundary claim.
    add(0x964838,0x16BC*2,'registered-scene-graphics',
        'raw graphics full consumer read span:135E88 SWI0B16BC halfwords to06010000; allocation extent unknown')
    add(0x3B44A0,0x30,'override-table-zero-tail',
        'explicit zero-filled tail following override table envelope',
        'fill',fill_byte=0)

    # Literal words consumed by the table loaders and adjoining data padding.
    for offset, words in [(0x3B42E0,[0x083B42F0]), (0x3B4320,[0x083B4330]),
                          (0x3B4430,[0x083B4434,0x08A50000,0,0]),
                          (0x3B4450,[0x083B4460,0,0,0])]:
        add(offset,4*len(words),f'table-literals-{offset:X}',
            'table loader literal pointers and reserved zero words',
            'u32_words',words=words)
    for start,end in [(0x3B42DC,0x3B42E0),(0x3B42E4,0x3B42F0),
                      (0x3B4324,0x3B4330),(0x3B4428,0x3B4430),
                      (0x3B4440,0x3B4450),(0x3B4490,0x3B44A0)]:
        if set(rom[start:end]) != {255}:
            raise ValueError('Expected FF table padding')
        add(start,end-start,f'table-padding-{start:X}','table storage padding',
            'fill',fill_byte=255)

    add(0xA6D000,0xA7FC00-0xA6D000,'splash-storage',
        'startup image resource storage; internal format/unused subranges unknown')

    # Cover only the bounded data area, never A7FC00+ ARM startup code.
    # Uniform padding is emitted as a fill instruction; nonuniform gaps retain
    # explicit unknown-resource provenance instead of pretending to decode it.
    cursor = HIGH_START
    while cursor < HIGH_END:
        if used[cursor-HIGH_START]:
            cursor += 1
            continue
        end = cursor+1
        while end < HIGH_END and not used[end-HIGH_START]:
            end += 1
        data = rom[cursor:end]
        if len(set(data)) == 1:
            add(cursor,end-cursor,f'padding-{cursor:X}',
                'uniform storage padding','fill',fill_byte=data[0])
        else:
            add(cursor,end-cursor,f'unresolved-storage-{cursor:X}',
                'unexplained data-storage interval; no format claim')
        cursor = end
    manifest = dict(schema='ffta-us-cn-resources-v1',rom_sha256=sha(rom),rom_size=len(rom),
                    high_resource_range=[HIGH_START,HIGH_END],
                    excluded='ARM startup code at A7FC00 and beyond; original header 3B4214 owned separately',
                    segments=sorted(segments,key=lambda row:row['rom_offset']))
    manifest_path = output/'resource-manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    rebuilt = build_segments(manifest_path)
    for offset,data,_ in rebuilt:
        if data != rom[offset:offset+len(data)]:
            raise ValueError('Resource reconstruction mismatch')
    report = dict(pass_exact=True,segment_count=len(rebuilt),
                  reconstructed_bytes=sum(len(data) for _,data,_ in rebuilt),
                  unique_copy_resources=len({int(row['source_new_rom'],16) for row in calls}),
                  copy_call_count=len(calls),override_rows=sum(len(t['rows']) for t in tables),
                  high_resource_bytes=sum(used),high_resource_coverage_complete=all(used),
                  manifest_sha256=sha(manifest_path.read_bytes()))
    (output/'resource-roundtrip.json').write_text(json.dumps(report,indent=2)+'\n')
    return manifest_path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',required=True,type=Path)
    parser.add_argument('--call-map',required=True,type=Path)
    parser.add_argument('--tables',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(extract(args.rom,args.call_map,args.tables,args.output))


if __name__ == '__main__':
    main()
