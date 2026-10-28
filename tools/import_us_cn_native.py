#!/usr/bin/env python3
"""Extract verified native text IDs from the explicitly selected US Chinese ROM."""
import argparse
import json
import struct
from pathlib import Path
import decomp_formats
import extract_resources as e
from scene_text_codec import encode_tokens
from build_us_cn_native import RETAIL, CHINESE, sha, require, u32, BASE


def decode_entry(data, offset, flags=True):
    require(0<=offset<len(data),'Text pointer outside ROM')
    f=struct.unpack_from('<H',data,offset)[0] if flags else 0
    cursor=offset+2 if flags else offset
    if f&2:
        size=int.from_bytes(data[cursor:cursor+4],'big')
        require(0<size<100000,'Invalid decompressed text size')
        _,payload,_=e.parse_compression(memoryview(data)[cursor+4:],size)
    else:payload=data[cursor:cursor+8192]
    item=(e.decode_alt_word if f&1 else e.decode_word)(payload,0)
    record=dict(tokens=item['tokens'],encoding='alternate' if f&1 else 'standard',
                decoded_sha256=item['raw_sha256'],rom_offset=offset,flags=f)
    raw=encode_tokens(record)
    require(raw==payload[:item['size']],'Native token round trip failed')
    record['decoded_hex']=raw.hex()
    return record


def extract(retail,cn):
    require(sha(retail)==RETAIL and sha(cn)==CHINESE,'Wrong source identity')
    groups=[];blocked=[]
    def page(family,pid,old,new,root_site,master):
        try:
            count=struct.unpack_from('<H',retail,old)[0]//2-1
            require(0<count<4096,'Invalid original page count')
            entries=[]
            for i in range(count):
                relative=struct.unpack_from('<H',cn,new+i*2)[0]
                if relative==0xffff:
                    original_offset=old+struct.unpack_from('<H',retail,old+i*2)[0]
                    record=decode_entry(retail,original_offset)
                    require(record['flags']==0x11 and record['decoded_hex']=='8aff',
                            'Missing translation is not a glyph-free close placeholder')
                    record['source_variant']='retail'
                else:
                    require(relative>=(count+1)*2,'Invalid translated page pointer')
                    record=decode_entry(cn,new+relative)
                    record['source_variant']='translated'
                record.update(index=i,retail_rom_offset=old+struct.unpack_from('<H',retail,old+i*2)[0])
                entries.append(record)
            groups.append(dict(family=family,page=pid,count=count,entries=entries,
                master_pointer_site=root_site,master_table_offset=master))
        except (ValueError,KeyError,IndexError,struct.error) as error:
            blocked.append(dict(family=family,page=pid,reason=str(error)))
    for family,site,count in [('scene',e.SCENE_TEXT_POINTER_OFFSET,63),('fixed',e.FIXED_TEXT_POINTER_OFFSET,27)]:
        oldmaster=u32(retail,site)-BASE;newmaster=u32(cn,site)-BASE
        for p in range(count):
            old=u32(retail,oldmaster+p*4);new=u32(cn,newmaster+p*4)
            if family=='fixed':
                if old==0:continue
                page(family,p,old-BASE,new-BASE,site,oldmaster)
            elif p==61:
                for q in range(26):
                    a=oldmaster+u32(retail,oldmaster+old+q*4)
                    b=newmaster+u32(cn,newmaster+new+q*4)
                    page(family,[p,q],a,b,site,oldmaster)
            else:page(family,p,oldmaster+old,newmaster+new,site,oldmaster)
    for name,(site,count) in e.WORD_TABLES.items():
        old=u32(retail,site)-BASE;new=u32(cn,site)-BASE;entries=[]
        for i in range(count):
            pointer=u32(cn,new+i*4)
            if pointer==0:
                require(u32(retail,old+i*4)==0,'Null binding changed')
                continue
            record=decode_entry(cn,pointer-BASE,False)
            record.update(index=i,retail_rom_offset=u32(retail,old+i*4)-BASE)
            entries.append(record)
        groups.append(dict(family='words:'+name,page=None,count=len(entries),table_full_count=count,entries=entries,
                           table_pointer_site=site,table_rom_offset=old))
    return dict(schema=1,retail_sha256=RETAIL,translated_sha256=CHINESE,groups=groups,blocked=blocked)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--retail',required=True,type=Path);p.add_argument('--translated',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args()
    require(not a.output_dir.resolve().is_relative_to(Path(__file__).resolve().parents[1]),'External output required')
    bundle=extract(a.retail.read_bytes(),a.translated.read_bytes())
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'native-import-bundle.json').write_text(json.dumps(bundle,indent=2)+'\n')
    print(json.dumps(dict(groups=len(bundle['groups']),entries=sum(g['count'] for g in bundle['groups']),blocked=bundle['blocked'])))
if __name__=='__main__':main()
