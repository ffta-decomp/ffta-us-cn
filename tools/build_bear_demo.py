#!/usr/bin/env python3
"""Build a bounded opening-dialogue demo with unmodified Bear glyphs/metrics."""
import argparse
import json
from pathlib import Path
import struct

from decomp_formats import DECOMP_ROOT
from convert_ffta_us_cn import canonical, sha, tokenize, serialize, write_json
from build_zh_demo import iter_entries, compressed_entry
from scene_text_codec import RETAIL_SHA256

LARGE_SHA256 = "aee65df70410f9c72c2e9b7a5ac9206b826f8559050c94018907be00ef8c4574"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.profile.read_text())
    paths = {key: Path(config[key]).resolve() for key in (
        'source_rom', 'bear_assets', 'retail_assets', 'baseline_rom', 'baseline_report', 'output_dir', 'upstream')}
    for path in paths.values():
        if path.is_relative_to(DECOMP_ROOT) or path.is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError('Game data must stay outside both source trees')
    source = paths['source_rom'].read_bytes()
    if sha(source) != LARGE_SHA256:
        raise ValueError('Expected pinned Bear large-font ROM')
    bear = paths['bear_assets']
    extraction = json.loads((bear/'report.json').read_text())
    if extraction['source_rom_sha256'] != LARGE_SHA256:
        raise ValueError('Wrong source extraction')
    for name, digest in extraction['file_sha256'].items():
        if Path(name).name != name or sha((bear/name).read_bytes()) != digest:
            raise ValueError('Source extraction changed')
    baseline = paths['baseline_rom'].read_bytes()
    baseline_report = json.loads(paths['baseline_report'].read_text())
    if baseline_report['input_sha256'] != RETAIL_SHA256 or baseline_report['output_sha256'] != sha(baseline):
        raise ValueError('Baseline report/hash mismatch')
    assets = paths['retail_assets']
    documents = [json.loads((assets/name).read_text()) for name in (
        'scene-text-pages.json', 'fixed-text-pages.json', 'word-tables.json')]
    if any(d['reference_sha256'] != RETAIL_SHA256 for d in documents):
        raise ValueError('Wrong retail text revision')
    used = {t['code'] for d in documents for e in iter_entries(d)
            for t in e['tokens'] if t['type'].endswith('glyph')}
    pairs = json.loads((bear/'base-pairs.json').read_text())['s_text']
    source_charset = json.loads((bear/'source-charset.json').read_text())[1]
    us_charset = json.loads((paths['upstream']/'charset_us.json').read_text())[1]
    selected = [pairs[f'1/{i}'] for i in (0,1)]
    import re
    characters = sorted({c for _, text in selected for c in re.sub(r'@\[[^]]*\]', '', text) if c != ' '})
    free = [i for i in range(0x118,3175) if i not in used]
    if len(free)<len(characters):raise ValueError('Insufficient unused glyph slots')
    target_charset = dict(zip(characters,free))
    font_offset = struct.unpack_from('<I',source,0x133f4)[0]-0x08000000
    widths_offset = struct.unpack_from('<I',source,0x13400)[0]-0x08000000
    result = bytearray(baseline)
    ranges, glyphs = [], []
    for character, target_code in target_charset.items():
        source_code = source_charset[character]
        glyph = source[font_offset+source_code*128:font_offset+(source_code+1)*128]
        advance = source[widths_offset+source_code]
        if len(glyph)!=128 or not 0<advance<=16:raise ValueError('Invalid source glyph or advance')
        target_offset=0x433330+target_code*128
        result[target_offset:target_offset+128]=glyph
        result[0x4966b0+target_code]=advance
        ranges.extend([(target_offset,128),(0x4966b0+target_code,1)])
        glyphs.append({'character':character,'source_code':source_code,'target_code':target_code,
                       'advance':advance,'source_sha256':sha(glyph)})
    for index,(original,translated) in enumerate(selected):
        entry=documents[0]['pages'][1]['entries'][index]
        if canonical(tokenize(original,us_charset))!=canonical(entry['tokens']):
            raise ValueError('Opening source text does not match retail')
        _,decoded=serialize(tokenize(translated,target_charset))
        payload=compressed_entry(entry['flags'],decoded) if entry['compressed'] else entry['flags'].to_bytes(2,'little')+decoded
        start=entry['rom_offset'];end=documents[0]['pages'][1]['entries'][index+1]['rom_offset']
        if len(payload)>end-start:raise ValueError('Translated text exceeds fixed slot')
        result[start:start+len(payload)]=payload;ranges.append((start,len(payload)))
    changed=[i for i,(a,b) in enumerate(zip(baseline,result)) if a!=b]
    if len(result)!=len(baseline) or any(not any(start<=i<start+size for start,size in ranges)for i in changed):
        raise ValueError('Write outside declared ranges')
    out=paths['output_dir'];out.mkdir(parents=True,exist_ok=True)
    (out/'ffta-bear-large-demo.gba').write_bytes(result)
    report={'source_rom_sha256':sha(source),'baseline_sha256':sha(baseline),'demo_sha256':sha(result),
            'size':len(result),'glyphs':glyphs,'glyph_count':len(glyphs),'changed_byte_count':len(changed),
            'selected_entries':[[1,0],[1,1]],'glyph_policy':'exact source bytes, no decoration or offset changes',
            'advance_policy':'copy source renderer width table at literal 0x08013400',
            'palette_policy':'retain retail palette/style processing','ranges':ranges}
    write_json(out/'build-report.json',report)
    print(json.dumps({k:report[k]for k in ('demo_sha256','glyph_count','changed_byte_count','size')}))


if __name__=='__main__':main()
