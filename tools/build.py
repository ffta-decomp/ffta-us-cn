#!/usr/bin/env python3
"""Build CN+pinyin by default; all game resources and outputs stay external."""
import argparse
import os
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from ips_patch import encode_patch, apply_patch

ROOT = Path(__file__).resolve().parents[1]


def options(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retail', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--pack-dir', type=Path)
    parser.add_argument('--glyph-map', type=Path)
    parser.add_argument('--map-report', type=Path)
    parser.add_argument('--rime-dictionary', type=Path)
    parser.add_argument('--tool-prefix', default='arm-none-eabi-')
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--compiler', type=Path, help='Explicit existing pinned agbcc; otherwise bootstrap externally')
    cjk = parser.add_mutually_exclusive_group()
    cjk.add_argument('--enable-cjk', dest='cjk', action='store_true')
    cjk.add_argument('--disable-cjk', dest='cjk', action='store_false')
    pinyin = parser.add_mutually_exclusive_group()
    pinyin.add_argument('--enable-pinyin', dest='pinyin', action='store_true')
    pinyin.add_argument('--disable-pinyin', dest='pinyin', action='store_false')
    link = parser.add_mutually_exclusive_group()
    link.add_argument('--enable-link-fix', dest='link_fix', action='store_true')
    link.add_argument('--disable-link-fix', dest='link_fix', action='store_false')
    info = parser.add_mutually_exclusive_group()
    info.add_argument('--enable-info', dest='info', action='store_true')
    info.add_argument('--disable-info', dest='info', action='store_false')
    italic = parser.add_mutually_exclusive_group()
    italic.add_argument('--enable-italic-font', dest='italic_font', action='store_true')
    italic.add_argument('--disable-italic-font', dest='italic_font', action='store_false')
    parser.set_defaults(cjk=True, pinyin=None, link_fix=None, info=None, italic_font=None)
    parser.add_argument('--patch-output', type=Path,
                        help='Optional local IPS against the authenticated US input')
    args = parser.parse_args(argv)
    if args.pinyin is True and not args.cjk:
        parser.error('--enable-pinyin requires CJK')
    args.pinyin = args.cjk if args.pinyin is None else args.pinyin
    args.link_fix = args.cjk if args.link_fix is None else args.link_fix
    args.info = (args.pinyin or args.link_fix) if args.info is None else args.info
    args.italic_font = (args.cjk and args.info) if args.italic_font is None else args.italic_font
    if args.italic_font and not args.cjk:
        parser.error('--enable-italic-font requires the uscn base font (--enable-cjk)')
    if args.italic_font and not args.info:
        parser.error('--enable-italic-font requires the info plugin (--enable-info)')
    if args.info and not (args.cjk or args.link_fix):
        parser.error('--enable-info requires at least one enabled plugin')
    if args.cjk and args.pack_dir is None:
        parser.error('CN requires --pack-dir; import your local resources first')
    if (args.pinyin or args.info) and (args.glyph_map is None or args.map_report is None):
        parser.error('Pinyin/Info requires --glyph-map and --map-report')
    if args.info and not args.cjk and args.pack_dir is None:
        parser.error('English Info requires --pack-dir for its Chinese display font')
    for path in [args.output_dir, args.patch_output]:
        if path is not None and path.resolve().is_relative_to(ROOT):
            parser.error('Generated output must be outside the source tree')
    for name in ['retail', 'output_dir', 'pack_dir', 'glyph_map', 'map_report', 'rime_dictionary', 'compiler', 'patch_output']:
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())
    return args


def main():
    args = options()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from joint_build import build
    image, report = build(args)
    (args.output_dir / 'ffta-us-cn.gba').write_bytes(image)
    if args.patch_output:
        baseline = args.retail.read_bytes()
        patch = encode_patch(baseline, image)
        if apply_patch(baseline, patch) != image:
            raise ValueError('Local IPS round-trip failed')
        args.patch_output.parent.mkdir(parents=True, exist_ok=True)
        args.patch_output.write_bytes(patch)
        report['local_patch_sha256'] = hashlib.sha256(patch).hexdigest()
    (args.output_dir / 'features.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['build_mode', 'cjk_enabled', 'pinyin_enabled', 'link_fix_enabled', 'info_enabled', 'italic_font_enabled', 'output_bytes', 'output_sha256']}))


if __name__ == '__main__':
    main()
