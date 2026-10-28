#!/usr/bin/env python3
"""Audit original-ID address reuse against authenticated ROMs without rebuilding."""
import argparse
import collections
import csv
import json
import struct
from pathlib import Path
import decomp_formats
import extract_resources as e
from scene_text_codec import parse_compression
from import_us_cn_native import extract, decode_entry
from build_us_cn_native import sha, require, BASE


def span(data,offset,flagged):
    record=decode_entry(data,offset,flagged)
    if flagged and record['flags']&2:
        size=int.from_bytes(data[offset+2:offset+6],'big')
        _,_,consumed=parse_compression(memoryview(data)[offset+6:],size)
        length=6+consumed
    else:length=(2 if flagged else 0)+len(bytes.fromhex(record['decoded_hex']))
    return record,length


def audit(retail,cn):
    bundle=extract(retail,cn);rows=[];roots=[];totals={};mask=bytearray(len(retail))
    for family,site in [('scene',e.SCENE_TEXT_POINTER_OFFSET),('fixed',e.FIXED_TEXT_POINTER_OFFSET),('font',e.FONT_POINTER_OFFSET),('width',0x13480)]+[('words:'+n,s) for n,(s,_) in e.WORD_TABLES.items()]:
        old=e.u32(retail,site);new=e.u32(cn,site)
        roots.append(dict(family=family,literal_rom=hex(site),literal_cpu=hex(BASE+site),retail_pointer=hex(old),translated_pointer=hex(new),same=old==new))
    for group in bundle['groups']:
        family=group['family'];counter=totals.setdefault(family,collections.Counter())
        flagged=not family.startswith('words:')
        for entry in group['entries']:
            old=entry['retail_rom_offset'];original,old_size=span(retail,old,flagged)
            missing=entry.get('source_variant')=='retail'
            target=None if missing else entry['rom_offset']
            counter['original_ids_checked']+=1
            retained=retail[old:old+old_size]==cn[old:old+old_size]
            counter['old_payload_preserved_at_old_address']+=retained
            if missing:
                category='missing_pointer_glyph_free_original_close_control'
                counter['missing_close_placeholder']+=1
                translated=None;new_size=0
            else:
                translated,new_size=span(cn,target,flagged)
                same=old==target
                category='same_address_same_tokens' if same and original['decoded_sha256']==translated['decoded_sha256'] else ('same_address_changed_tokens' if same else 'relocated')
                counter[category]+=1
                counter['same_decoded_tokens']+=original['decoded_sha256']==translated['decoded_sha256']
                counter['retail_compressed']+=bool(original['flags']&2) if flagged else 0
                counter['translated_compressed']+=bool(translated['flags']&2) if flagged else 0
                if not same:mask[target:target+new_size]=b'\x01'*new_size
            rows.append(dict(family=family,page=json.dumps(group['page']),index=entry['index'],retail_rom=hex(old),retail_cpu=hex(BASE+old),translated_rom=hex(target) if target is not None else None,translated_cpu=hex(BASE+target) if target is not None else None,category=category,old_payload_preserved=retained,retail_stored_bytes=old_size,translated_stored_bytes=new_size,retail_decoded_sha256=original['decoded_sha256'],translated_decoded_sha256=translated['decoded_sha256'] if translated else None))
    addresses=[i for i,v in enumerate(mask) if v]
    occupied=len(addresses);free=sum(retail[i]==255 for i in addresses)
    return dict(schema=1,retail_sha256=sha(retail),translated_sha256=sha(cn),rom_bytes=len(retail),roots=roots,families={k:dict(v) for k,v in totals.items()},relocated_text_payload_union=dict(bytes=occupied,retail_ff_bytes=free,retail_non_ff_bytes=occupied-free,min_rom=hex(min(addresses)),max_end_rom=hex(max(addresses)+1)),entries=rows,limits=['Counts refer to conservatively mapped original IDs, not every extra translated header slot.','Old payload retention does not establish which pointer a live consumer uses.','FF counts establish observed baseline bytes, not general allocation permission.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['retail','translated','output-dir']:p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();require(not a.output_dir.resolve().is_relative_to(Path(__file__).resolve().parents[1]),'External output required')
    result=audit(a.retail.read_bytes(),a.translated.read_bytes());a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'original-id-address-reuse.json').write_text(json.dumps(result,indent=2)+'\n')
    with (a.output_dir/'original-id-address-reuse.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(result['entries'][0]));writer.writeheader();writer.writerows(result['entries'])
    print(json.dumps({k:v for k,v in result.items() if k not in ['entries','roots']},indent=2))
if __name__=='__main__':main()
