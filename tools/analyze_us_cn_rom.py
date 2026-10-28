#!/usr/bin/env python3
"""Authenticate local ROMs and inventory every changed byte; no payload export."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

EXPECTED = ('43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19',
            'ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def analyze(retail, translated):
    if len(retail) != 0x1000000 or len(translated) != len(retail):
        raise ValueError('Both inputs must be 16 MiB')
    if (sha(retail), sha(translated)) != EXPECTED:
        raise ValueError('Unrecognized input identity')
    ranges = []
    cursor = 0
    while cursor < len(retail):
        if retail[cursor] == translated[cursor]:
            cursor += 1
            continue
        start = cursor
        while cursor < len(retail) and retail[cursor] != translated[cursor]:
            cursor += 1
        ranges.append(dict(rom_start=start, rom_end_exclusive=cursor,
                           cpu_start=hex(0x08000000 + start),
                           cpu_end_exclusive=hex(0x08000000 + cursor),
                           length=cursor-start,
                           retail_sha256=sha(retail[start:cursor]),
                           translated_sha256=sha(translated[start:cursor]),
                           classification='unresolved'))
    blocks = []
    for start in range(0, len(retail), 0x10000):
        a, b = retail[start:start+0x10000], translated[start:start+0x10000]
        changed = sum(x != y for x, y in zip(a,b))
        blocks.append(dict(rom_start=start, cpu_start=hex(0x08000000+start),
                           changed_bytes=changed, retail_sha256=sha(a), translated_sha256=sha(b)))
    return dict(schema=1, input_sha256=list(EXPECTED),
                changed_bytes=sum(r['length'] for r in ranges), ranges=ranges, blocks=blocks)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--retail',required=True,type=Path)
    p.add_argument('--translated',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if a.output_dir.resolve().is_relative_to(root):
        raise ValueError('Evidence must remain outside source')
    result=analyze(a.retail.read_bytes(),a.translated.read_bytes())
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'complete-diff.json').write_text(json.dumps(result,indent=2)+'\n')
    with (a.output_dir/'complete-diff.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(result['ranges'][0]))
        writer.writeheader();writer.writerows(result['ranges'])
    print(json.dumps(dict(changed_bytes=result['changed_bytes'],ranges=len(result['ranges']))))

if __name__=='__main__':
    main()
