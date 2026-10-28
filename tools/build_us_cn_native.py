#!/usr/bin/env python3
"""Experimental nonmatching native-token prototype; not the 16 MiB alignment build.

All copyrighted inputs and generated outputs are selected explicitly and external.
The disabled profile is the byte-identical English baseline.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
import decomp_formats
from scene_text_codec import encode_tokens, parse_compression
from extract_resources import decode_word, decode_alt_word
from font_codec import decode_atlas, encode_atlas

RETAIL='43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19'
CHINESE='ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03'
BASE=0x08000000

def sha(data):return hashlib.sha256(data).hexdigest()
def u32(data,pos):return struct.unpack_from('<I',data,pos)[0]
def require(value,message):
    if not value:raise ValueError(message)

def build(retail, translated, bundle, enabled):
    require(sha(retail)==RETAIL,'Wrong English baseline')
    if not enabled:return retail,dict(language='en',output_sha256=sha(retail),changed_bytes=0)
    require(sha(translated)==CHINESE,'Wrong Chinese source')
    require(bundle['retail_sha256']==RETAIL and bundle['translated_sha256']==CHINESE,'Bundle identity mismatch')
    out=bytearray(retail)
    patches=[];bindings=[];roundtrips=0
    def write(pos,data,kind):
        require(pos>=0 and pos+len(data)<=len(out),'Patch outside image')
        out[pos:pos+len(data)]=data
        patches.append(dict(kind=kind,rom_offset=pos,cpu_address=hex(BASE+pos),size=len(data),sha256=sha(data)))
    def put32(pos,value,kind):write(pos,struct.pack('<I',value),kind)
    def append(data,kind):
        out.extend(b'\xff'*((-len(out))%4))
        pos=len(out);require(pos+len(data)<=0x2000000,'GBA 32MiB ROM limit')
        out.extend(data)
        patches.append(dict(kind=kind,rom_offset=pos,cpu_address=hex(BASE+pos),size=len(data),sha256=sha(data)))
        return pos
    font=translated[0x433330:0x433330+3175*128]
    require(encode_atlas(decode_atlas(font,3175,64),3175,64)==font,'Font round trip')
    write(0x433330,font,'native-font')
    write(0x4966b0,translated[0x4966b0:0x4966b0+3175],'native-advances')
    nested={}
    for group in bundle['groups']:
        entries=group['entries'];count=group['count'];family=group['family'];page=group['page']
        require(len(entries)==count and [e['index'] for e in entries]==list(range(count)),'Non-contiguous text IDs')
        payloads=[]
        for entry in entries:
            decoded=encode_tokens(entry)
            require(decoded.hex()==entry['decoded_hex'],'Token source mismatch')
            source=entry['rom_offset']
            source_image=retail if entry.get('source_variant')=='retail' else translated
            require(entry.get('source_variant')!='retail' or (entry['flags']==0x11 and decoded==bytes.fromhex('8aff')),'Unsafe English fallback')
            require(0<=source<len(source_image),'Source text outside ROM')
            if family.startswith('words:'):
                source_payload=source_image[source:source+len(decoded)]
            else:
                source_flags=struct.unpack_from('<H',source_image,source)[0]
                require(source_flags==entry['flags'],'Source flags mismatch')
                if source_flags&2:
                    size=int.from_bytes(source_image[source+2:source+6],'big')
                    require(0<size<100000,'Invalid source compression size')
                    _,source_payload,_=parse_compression(memoryview(source_image)[source+6:],size)
                    source_payload=source_payload[:len(decoded)]
                else:source_payload=source_image[source+2:source+2+len(decoded)]
            require(source_payload==decoded,'Tokens do not match authenticated source')
            parsed=(decode_alt_word if entry['encoding']=='alternate' else decode_word)(decoded,0)
            require(parsed['raw_sha256']==entry['decoded_sha256'] and parsed['size']==len(decoded),'Token decoder mismatch')
            for token in entry['tokens']:
                if token['type'].endswith('glyph'):require(0<=token['code']<3175,'Glyph outside imported atlas')
            payloads.append(decoded);roundtrips+=1
        if family.startswith('words:'):
            start=group['table_rom_offset']
            require(start+group.get('table_full_count',count)*4<=len(retail),'Word pointer table out of bounds')
            for entry,payload in zip(entries,payloads):
                loc=append(payload,'word-token-stream')
                put32(start+entry['index']*4,BASE+loc,'word-pointer')
            site=group['table_pointer_site']
            require(u32(retail,site)==BASE+group['table_rom_offset'],'Word table binding changed')
            # Keep the table at its original location: other real consumers alias it.
        else:
            # First relative offset encodes count+1. Keep the extra sentinel slot.
            table=bytearray((count+1)*2)
            for entry,payload in zip(entries,payloads):
                if len(table)%2:table.append(0)
                require(len(table)<0x10000,'Page-relative pointer overflow')
                struct.pack_into('<H',table,entry['index']*2,len(table))
                flags=entry['flags']&~2
                table.extend(struct.pack('<H',flags)+payload)
            require(len(table)<0x10000,'Page exceeds native u16 envelope')
            struct.pack_into('<H',table,count*2,len(table))
            start=append(table,'native-text-page')
            master=group['master_table_offset']
            require(u32(retail,group['master_pointer_site'])==BASE+master,'Master table binding changed')
            if family=='scene':
                if isinstance(page,list):nested.setdefault(page[0],{})[page[1]]=start
                else:put32(master+page*4,start-master,'scene-page-binding')
            else:
                require(isinstance(page,int),'Nested fixed page unsupported')
                put32(master+page*4,BASE+start,'fixed-page-binding')
        bindings.append(dict(family=family,page=page,count=count,linked_rom_offset=start,linked_cpu_address=hex(BASE+start)))
    for page,children in nested.items():
        require(sorted(children)==list(range(len(children))),'Incomplete nested page')
        master=next(g['master_table_offset'] for g in bundle['groups'] if g['family']=='scene')
        table=b''.join(struct.pack('<I',children[i]-master) for i in range(len(children)))
        start=append(table,'nested-scene-table')
        put32(master+page*4,start-master,'nested-scene-root-binding')
    # Fixed size simplifies emulator and patch tooling. No translated code is imported.
    out.extend(b'\xff'*(0x2000000-len(out)))
    code_limit=0x150000
    allowed=set()
    require(all(retail[i]==out[i] or i in allowed for i in range(code_limit)),'Unexpected engine change')
    return bytes(out),dict(language='zh',input_sha256=RETAIL,translation_source_sha256=CHINESE,
        output_sha256=sha(out),output_bytes=len(out),token_roundtrips=roundtrips,
        font_roundtrip=True,engine_hooks_imported=0,bindings=bindings,patches=patches,
        blocked=bundle['blocked'],retail_glyph_free_placeholders=sum(e.get('source_variant')=='retail' for g in bundle['groups'] for e in g['entries']),limits=['Untranslated consumer text and graphical resources are retained; this is not a complete game translation.','Unicode assignment for the imported font is not yet verified.','No runtime language toggle: language is selected at build time.'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--retail',required=True,type=Path);p.add_argument('--translated',type=Path)
    p.add_argument('--bundle',type=Path);p.add_argument('--language',choices=['en','zh'],required=True)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--allow-nonmatching-prototype',action='store_true',help='Explicit historical reproduction only: 32 MiB append layout is not translated-ROM bytematch')
    a=p.parse_args()
    if a.language=='zh' and not a.allow_nonmatching_prototype:
        p.error('The 32 MiB prototype is superseded: requested target is the supplied 16 MiB translated ROM. No image was built. Historical reproduction requires --allow-nonmatching-prototype.')
    require(not a.output_dir.resolve().is_relative_to(Path(__file__).resolve().parents[1]),'External output required')
    require(a.language=='en' or (a.translated and a.bundle),'Chinese profile requires explicit resources')
    image,report=build(a.retail.read_bytes(),a.translated.read_bytes() if a.translated else b'',json.loads(a.bundle.read_text()) if a.bundle else {},a.language=='zh')
    report['python_version']=sys.version
    report['bundle_sha256']=sha(a.bundle.read_bytes()) if a.bundle else None
    report['tool_sha256']={p.name:sha(p.read_bytes()) for p in [
        Path(__file__),Path(__file__).with_name('import_us_cn_native.py'),
        Path(sys.modules['scene_text_codec'].__file__),Path(sys.modules['extract_resources'].__file__),
        Path(sys.modules['font_codec'].__file__)]}
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/('ffta-'+a.language+'.gba')).write_bytes(image)
    (a.output_dir/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k in ['language','output_sha256','token_roundtrips','engine_hooks_imported']}))
if __name__=='__main__':main()
