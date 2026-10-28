#!/usr/bin/env python3
"""Import local US-CN resources and rebuild their exact 16 MiB original layout.

Import may read both authenticated ROMs. Build reads only English retail, the
private component pack, and readable hook assembly. It never loads the translated
ROM or a whole-ROM binary diff. Native glyph assignments are never regenerated.
"""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path
from assemble_us_cn_hooks import assemble_hooks
from us_cn_text_layout import extract_pack, build_segments, decode_record, encode_record
from us_cn_resource_layout import extract as extract_resources, build_segments as resource_segments

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/us-cn-reference-layout.json'


def sha(data):return hashlib.sha256(data).hexdigest()
def require(value,message):
    if not value:raise ValueError(message)
def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def safe_file(root,relative):
    path=(root/relative).resolve()
    require(path.is_relative_to(root.resolve()),'Pack path escapes its root')
    return path

def thumb_bl(offset,target):
    delta=target-(0x08000000+offset+4)
    require(delta%2==0 and -(1<<22)<=delta<(1<<22),'Thumb BL outside range')
    return struct.pack('<HH',0xf000|((delta>>12)&0x7ff),0xf800|((delta>>1)&0x7ff))

def primitive_segments(retail,layout):
    result=[]
    for row in layout['pointer_literals']:
        require(struct.unpack_from('<I',retail,row['offset'])[0]==row['old'],'Original pointer identity mismatch')
        result.append((row['offset'],struct.pack('<I',row['new']),'typed ROM pointer relocation'))
    for row in layout['copy_calls']:
        offset=int(row['call_rom'],16)
        require(retail[offset:offset+4]==thumb_bl(offset,0x0800543c),'Original resource call differs')
        result.append((offset,thumb_bl(offset,0x083b4220),'resource copy BL redirect'))
    require(struct.unpack_from('<I',retail,0xec)[0]==0xe12fff11,'Original startup is not BX R1')
    branch=0xea000000|(((0x08a7fda8-(0x080000ec+8))>>2)&0xffffff)
    result.extend([(0xec,struct.pack('<I',branch),'ARM startup branch'),
        (0x53bc,struct.pack('<H',0x4802)+thumb_bl(0x53be,0x083b4270),'LDR R0 literal and epilogue extension BL')])
    for off,register,old,new in [(0x313f6,2,0xc6,0xfa),(0x4c2da,1,0xe0,0xd0)]:
        require(struct.unpack_from('<H',retail,off)[0]==0x2000|(register<<8)|old,'Original MOVS differs')
        result.append((off,struct.pack('<H',0x2000|(register<<8)|new),'Thumb MOVS immediate'))
    for row in layout['fills']:
        result.append((row['offset'],bytes([row['value']])*row['size'],row['purpose']))
    return result

def verify_pack(root):
    manifest=json.loads((root/'pack-manifest.json').read_text())
    for relative,expected in manifest['files'].items():
        require(sha(safe_file(root,relative).read_bytes())==expected,'Pack file identity mismatch: '+relative)
    return manifest

def compose(retail,pack,output_dir,tool_prefix):
    pack=Path(pack).resolve();outdir=Path(output_dir).resolve()
    manifest=verify_pack(pack);layout=json.loads((pack/'layout.json').read_text())
    require(len(retail)==layout['rom_bytes'] and sha(retail)==layout['retail_sha256'],'Wrong English retail identity')
    require(not outdir.is_relative_to(ROOT) and not outdir.is_relative_to(pack),'Generated outputs must be outside source and pack')
    outdir.mkdir(parents=True,exist_ok=True)
    hook_report=assemble_hooks(pack/'engine/us_cn_hooks.s',outdir/'assembled-hooks',tool_prefix)
    segments=[(off,data,'native text/font fixed layout') for off,data in build_segments(pack/'text')]
    segments += [(off,data,meta['classification']) for off,data,meta in resource_segments(pack/'resources/resource-manifest.json')]
    for record in json.loads((pack/'inline-native-text.json').read_text()):
        data=encode_record(record)
        require(sha(data)==record['stored_sha256'],'Inline native text differs')
        segments.append((record['rom_offset'],data,'typed inline native glyph/token stream'))
    segments+=primitive_segments(retail,layout)
    for row in hook_report['segments']:
        data=Path(row['binary']).read_bytes()
        require(sha(data)==row['sha256'],'Assembled code identity mismatch')
        segments.append((row['rom_offset'],data,'readable assembled engine hook'))
    image=bytearray(retail);written=bytearray(len(image));components=[]
    for offset,data,kind in segments:
        end=offset+len(data);require(0<=offset<end<=len(image),'Component outside original16MiB image')
        for i,value in enumerate(data,offset):
            require(not written[i] or image[i]==value,'Conflicting components at '+hex(i))
        image[offset:end]=data;written[offset:end]=bytes([1])*len(data)
        components.append(dict(rom_offset=offset,cpu_address=hex(0x08000000+offset),bytes=len(data),kind=kind,sha256=sha(data)))
    report=dict(schema=1,retail_sha256=sha(retail),target_sha256=layout['translated_sha256'],
        output_sha256=sha(image),output_bytes=len(image),component_count=len(components),
        unique_component_bytes=sum(written),components=components,
        hooks_source_sha256=hook_report['source_sha256'],pack_manifest_sha256=sha((pack/'pack-manifest.json').read_bytes()),
        glyph_policy='Unmodified native source glyph codes/order/4bpp cells/advances; no Unicode remapping or font rendering',
        translated_rom_read_by_build=False,whole_rom_diff_used=False)
    return bytes(image),report

def import_pack(retail_path,translated_path,pack):
    layout=json.loads(CONFIG.read_text());retail=retail_path.read_bytes();translated=translated_path.read_bytes()
    require(len(retail)==len(translated)==layout['rom_bytes'],'Expected original16MiB inputs')
    require(sha(retail)==layout['retail_sha256'] and sha(translated)==layout['translated_sha256'],'Wrong source revision')
    require(not pack.resolve().is_relative_to(ROOT),'External pack required')
    pack.mkdir(parents=True,exist_ok=False)
    write_json(pack/'layout.json',layout)
    extract_pack(retail,translated,pack/'text',layout['extra_consumer_pages'])
    write_json(pack/'copy-call-map.json',layout['copy_calls']);write_json(pack/'override-tables.json',layout['replacement_tables'])
    extract_resources(translated_path,pack/'copy-call-map.json',pack/'override-tables.json',pack/'resources')
    records=[]
    for offset in layout['inline_native_streams']:
        record=decode_record(translated,offset,False)
        record['stored_sha256']=sha(encode_record(record));records.append(record)
    write_json(pack/'inline-native-text.json',records)
    (pack/'engine').mkdir();shutil.copyfile(ROOT/'engine/us_cn_hooks.s',pack/'engine/us_cn_hooks.s')
    files={str(p.relative_to(pack)):sha(p.read_bytes()) for p in sorted(pack.rglob('*')) if p.is_file()}
    write_json(pack/'pack-manifest.json',dict(schema='ffta-us-cn-exact-layout-pack-v1',
        retail_sha256=layout['retail_sha256'],target_sha256=layout['translated_sha256'],rom_bytes=len(retail),files=files,
        engine_source='engine/us_cn_hooks.s',glyph_policy='native ROM glyph/code table retained without remapping',
        source_role='Private localization resources plus readable hook source; no full ROM or binary diff payload'))
    return translated

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import');imp.add_argument('--retail',required=True,type=Path);imp.add_argument('--translated',required=True,type=Path);imp.add_argument('--pack-dir',required=True,type=Path)
    build=sub.add_parser('build');build.add_argument('--retail',required=True,type=Path);build.add_argument('--pack-dir',type=Path);build.add_argument('--language',choices=['en','zh'],required=True);build.add_argument('--output-dir',required=True,type=Path);build.add_argument('--tool-prefix',default='arm-none-eabi-')
    args=parser.parse_args()
    if args.command=='import':
        import_pack(args.retail,args.translated,args.pack_dir);print(json.dumps({'pack':str(args.pack_dir),'status':'imported'}));return
    require(not args.output_dir.resolve().is_relative_to(ROOT),'External output required')
    if args.language=='en':
        layout=json.loads(CONFIG.read_text());image=args.retail.read_bytes()
        require(sha(image)==layout['retail_sha256'],'Wrong English retail identity')
        report=dict(language='en',output_sha256=sha(image),output_bytes=len(image),byte_identical_to_retail=True)
        args.output_dir.mkdir(parents=True,exist_ok=True)
    else:
        require(args.pack_dir is not None,'Chinese build requires explicit private pack')
        image,report=compose(args.retail.read_bytes(),args.pack_dir,args.output_dir,args.tool_prefix)
        report['whole_image_target_hash_match']=report['output_sha256']==report['target_sha256']
        write_json(args.output_dir/'build-report.json',report)
        require(report['whole_image_target_hash_match'],'Whole16MiB target mismatch; no ROM released; compare component report')
    (args.output_dir/('ffta-'+args.language+'.gba')).write_bytes(image)
    write_json(args.output_dir/'build-report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k in ['output_sha256','output_bytes','whole_image_target_hash_match','translated_rom_read_by_build']}))
if __name__=='__main__':main()
