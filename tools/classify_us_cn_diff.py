#!/usr/bin/env python3
"""Merge bounded, source-observed region labels without hiding unknown bytes."""
import argparse
import collections
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-dir',required=True,type=Path);a=p.parse_args();root=a.evidence_dir
    inventory=json.loads((root/'inventory/complete-diff.json').read_text())
    labels=['unknown'];mask=bytearray(0x1000000)
    def mark(start,end,name):
        if name not in labels:labels.append(name)
        mask[start:end]=bytes([labels.index(name)])*(end-start)
    for family in ['cn']:
        records=json.loads((root/'text-analysis'/f'{family}-records.json').read_text())
        for r in records:
            start=r['rom_offset'];mark(start,start+r['stored_bytes'],'native-text-stream')
        groups={}
        for r in records:
            if 'page_rom_offset' in r:groups.setdefault(r['page_rom_offset'],[]).append(r)
        for start,rows in groups.items():mark(start,start+(max(r['index'] for r in rows)+2)*2,'native-page-relative-pointer-table')
    mark(0x433330,0x433330+3175*128,'native-font-4bpp')
    mark(0x4966b0,0x4966b0+3175,'native-font-advance')
    mark(0x3b4220,0x3b4262,'new-uncompressed-copy-code')
    mark(0x3b4270,0x3b42d0,'resource-override-code')
    mark(0xa7fc00,0xa7fdb0,'startup-display-prelude-code-and-literals')
    tables=json.loads((root/'code-analysis/replacement-resource-tables.json').read_text())
    for t in tables['tables']:
        mark(int(t['table_rom'],16),int(t['sentinel_rom'],16)+2,'resource-override-table')
        for r in t['rows']:
            start=int(r['source_rom'],16);mark(start,start+r['byte_count'],'resource-override-payload-format-unresolved')
    for r in json.loads((root/'code-analysis/low-code-changes.json').read_text()):
        name=r['classification']
        branches=r.get('decoded_direct_branches',[])
        targets={int(x['target_rom'],16) for x in branches if x['variant']=='translated'}
        if 0x3b4220 in targets:name='resource-copy-call-redirection'
        if r['rom_start']>=0x53bc and r['rom_end_exclusive']<=0x53c2:name='post-load-resource-override-hook'
        mark(r['rom_start'],r['rom_end_exclusive'],name)
    totals=collections.Counter()
    for r in inventory['ranges']:
        pieces=[];start=r['rom_start'];end=r['rom_end_exclusive']
        while start<end:
            label=mask[start];stop=start+1
            while stop<end and mask[stop]==label:stop+=1
            pieces.append(dict(rom_start=start,rom_end_exclusive=stop,cpu_start=hex(0x08000000+start),cpu_end_exclusive=hex(0x08000000+stop),classification=labels[label]))
            totals[labels[label]]+=stop-start;start=stop
        r['segments']=pieces
    result=dict(schema=1,changed_bytes=inventory['changed_bytes'],classification_changed_bytes=dict(totals),ranges=inventory['ranges'],limits=['Unknown regions remain unknown. Region classification does not establish complete runtime coverage.','Historical patch provenance cannot be cryptographically proved by two final binaries; shared code and live resource address structure provide derivation evidence.'])
    (root/'classified-difference-ranges.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(totals),indent=2))
if __name__=='__main__':main()
