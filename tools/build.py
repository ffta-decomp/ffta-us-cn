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
    parser.add_argument('--cn-version', choices=('cn2025', 'cn2026'), default='cn2025',
                        help='CN2026 includes translation revisions, image enhancements and pinyin naming')
    parser.add_argument('--cn2026-pack', '--image-enhancement-pack', dest='image_enhancement_pack', type=Path,
                        help='Explicit private directory containing pinned CN2026 resource fragments')
    parser.add_argument('--glyph-map', type=Path)
    parser.add_argument('--map-report', type=Path)
    parser.add_argument('--rime-dictionary', type=Path)
    parser.add_argument('--tool-prefix', default='arm-none-eabi-')
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--compiler', type=Path, help='Explicit existing pinned agbcc; otherwise bootstrap externally')
    parser.add_argument('--splash-version', choices=['1.1', '1.2'],
                        help='Replace the native CN splash version caption')
    parser.add_argument('--build-label', help='Optional release/test watermark shown in Info')
    parser.add_argument('--author-file', type=Path, default=ROOT / 'author.txt',
                        help='UTF-8 splash credit; applied only after detecting the CN patch')
    author = parser.add_mutually_exclusive_group()
    author.add_argument('--enable-author', dest='author', action='store_true')
    author.add_argument('--disable-author', dest='author', action='store_false')
    opening = parser.add_mutually_exclusive_group()
    opening.add_argument('--enable-fastskip', dest='fastskip', action='store_true')
    opening.add_argument('--disable-fastskip', dest='fastskip', action='store_false')
    parser.add_argument('--enable-recruit-rename', dest='recruit_rename', action='store_true',
                        help='Name recruits using the keyboard selected by the build')
    parser.add_argument('--enable-battle-speed', dest='battle_speed', action='store_true',
                        help='Install the experimental 1x/2x/4x/8x battle presentation speed option')
    cjk = parser.add_mutually_exclusive_group()
    cjk.add_argument('--enable-cjk', dest='cjk', action='store_true')
    cjk.add_argument('--disable-cjk', dest='cjk', action='store_false')
    pinyin = parser.add_mutually_exclusive_group()
    pinyin.add_argument('--enable-pinyin', dest='pinyin', action='store_true')
    pinyin.add_argument('--disable-pinyin', dest='pinyin', action='store_false')
    link = parser.add_mutually_exclusive_group()
    link.add_argument('--enable-link-fix', dest='link_fix', action='store_true')
    link.add_argument('--disable-link-fix', dest='link_fix', action='store_false')
    vbam = parser.add_mutually_exclusive_group()
    vbam.add_argument('--enable-vbam-save-fix', dest='vbam_save_fix', action='store_true')
    vbam.add_argument('--disable-vbam-save-fix', dest='vbam_save_fix', action='store_false')
    info = parser.add_mutually_exclusive_group()
    info.add_argument('--enable-info', dest='info', action='store_true')
    info.add_argument('--disable-info', dest='info', action='store_false')
    italic = parser.add_mutually_exclusive_group()
    italic.add_argument('--enable-italic-font', dest='italic_font', action='store_true')
    italic.add_argument('--disable-italic-font', dest='italic_font', action='store_false')
    parser.set_defaults(cjk=True, pinyin=None, link_fix=None, vbam_save_fix=None, info=None, italic_font=None, author=None, fastskip=None)
    parser.add_argument('--patch-output', type=Path,
                        help='Optional local IPS against the authenticated US input')
    args = parser.parse_args(argv)
    args.cn2026 = args.cn_version == 'cn2026'
    args.common_options = args.cn2026 or args.battle_speed
    if args.cn2026 and not args.cjk:
        parser.error('--cn-version cn2026 requires CJK')
    if args.cn2026 and args.image_enhancement_pack is None:
        parser.error('--cn-version cn2026 requires --image-enhancement-pack')
    if args.image_enhancement_pack is not None:
        if not args.cn2026:
            parser.error('--image-enhancement-pack requires --cn-version cn2026')
        if args.image_enhancement_pack.resolve().is_relative_to(ROOT):
            parser.error('Private image resources must be outside the source tree')
    if args.pinyin is True and not args.cjk:
        parser.error('--enable-pinyin requires CJK')
    args.pinyin = args.cjk if args.pinyin is None else args.pinyin
    if args.cn2026 and not args.pinyin:
        parser.error('cn2026 requires the pinyin naming input method')
    args.link_fix = args.cjk if args.link_fix is None else args.link_fix
    if args.vbam_save_fix is None:
        args.vbam_save_fix = args.recruit_rename or (args.cjk and (args.pinyin or args.link_fix))
    if args.recruit_rename and not args.vbam_save_fix:
        parser.error('--enable-recruit-rename requires the Flash compatibility extension')
    args.info = (args.pinyin or args.link_fix) if args.info is None else args.info
    if args.build_label is not None:
        args.build_label = args.build_label.strip()
        if not args.build_label or len(args.build_label) > 80 or any(ord(c) < 32 or c in '\u2028\u2029' for c in args.build_label):
            parser.error('--build-label requires one nonempty line of at most 80 characters')
        if not args.info:
            parser.error('--build-label requires Info')
    args.italic_font = (args.cjk and args.info) if args.italic_font is None else args.italic_font
    # Preserve the documented exact-reference feature-off combination.
    args.author = (not args.cjk or args.pinyin or args.link_fix or args.info) if args.author is None else args.author
    args.fastskip = (args.cjk and args.info) if args.fastskip is None else args.fastskip
    if args.fastskip and not (args.cjk and args.info):
        parser.error('--enable-fastskip requires CJK and the Info title extension')
    if args.italic_font and not args.cjk:
        parser.error('--enable-italic-font requires the cn2025 base font (--enable-cjk)')
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
    for name in ['retail', 'output_dir', 'pack_dir', 'glyph_map', 'map_report', 'rime_dictionary', 'compiler', 'patch_output', 'author_file', 'image_enhancement_pack']:
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())
    return args


def main():
    args = options()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from joint_build import build
    image, report = build(args)
    from splash_author import stamp, stamp_version, write_preview
    image, author_report = stamp(image, args.author_file, enabled=args.author)
    image, version_report = stamp_version(image, getattr(args, 'splash_version', None))
    report['splash_version'] = version_report
    report['splash_author'] = author_report
    report['build_label'] = getattr(args, 'build_label', None)
    report['output_sha256'] = hashlib.sha256(image).hexdigest()
    if author_report['applied'] or version_report['applied']:
        write_preview(image, args.output_dir / 'splash-author.png')
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
