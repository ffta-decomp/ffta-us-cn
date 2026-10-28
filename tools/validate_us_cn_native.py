#!/usr/bin/env python3
"""Reopen linked ROM pointers and check every selected text ID against its source."""
import argparse
import json
from pathlib import Path
from import_us_cn_native import decode_entry
from build_us_cn_native import BASE, sha, require, u32

def validate(image,bundle,report):
    require(sha(image)==report['output_sha256'],'Linked image identity mismatch')
    groups={(g['family'],str(g['page'])):g for g in bundle['groups']}
    total=0
    for binding in report['bindings']:
        family=binding['family'];page=binding['page'];g=groups[family,str(page)]
        start=binding['linked_rom_offset']
        if family.startswith('words:'):
            require(u32(image,g['table_pointer_site'])==BASE+start,'Word root mismatch')
        else:
            master=g['master_table_offset']
            if family=='scene':
                if isinstance(page,list):
                    table=master+u32(image,master+page[0]*4)
                    actual=master+u32(image,table+page[1]*4)
                else:actual=master+u32(image,master+page*4)
            else:actual=u32(image,master+page*4)-BASE
            require(actual==start,'Page root mismatch')
        for source in g['entries']:
            if family.startswith('words:'):offset=u32(image,start+source['index']*4)-BASE
            else:offset=start+int.from_bytes(image[start+source['index']*2:start+source['index']*2+2],'little')
            linked=decode_entry(image,offset,not family.startswith('words:'))
            require(linked['decoded_hex']==source['decoded_hex'],'Linked text ID payload mismatch')
            total+=1
    return dict(image_sha256=sha(image),linked_text_ids_checked=total,pointer_roots_checked=len(report['bindings']),all_in_gba_rom_window=len(image)<=0x2000000)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['image','bundle','report','output']:p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();result=validate(a.image.read_bytes(),json.loads(a.bundle.read_text()),json.loads(a.report.read_text()))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
