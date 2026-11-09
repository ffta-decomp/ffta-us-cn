#!/usr/bin/env python3
"""Package an explicitly selected local ROM, detecting its CN splash patch.

An optional local IPS is applied before detection. Never upload this output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.dont_write_bytecode = True
from ips_patch import apply_patch
from splash_author import ROOT, AUTHOR, stamp, write_preview


def package(rom, output, author_file=AUTHOR, patch=None, author=True):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Private package outputs must remain outside the source tree')
    if output.exists():
        raise ValueError('Package output directory already exists')
    original = Path(rom).read_bytes()
    if len(original) != 0x1000000:
        raise ValueError('Expected a 16 MiB FFTA ROM')
    image = original
    patch_data = Path(patch).read_bytes() if patch else None
    if patch_data is not None:
        image = apply_patch(image, patch_data)
    image, credit = stamp(image, author_file, enabled=author)
    # Validate everything before creating outputs. Failed detection or text
    # validation never produces a partially stamped package.
    sha = lambda data: hashlib.sha256(data).hexdigest()
    report = dict(schema=1, input_sha256=sha(original),
                  input_patch_sha256=sha(patch_data) if patch_data is not None else None,
                  output_sha256=sha(image), output_bytes=len(image), splash_author=credit)
    output.mkdir(parents=True, exist_ok=False)
    name = 'ffta-us-cn.gba' if credit.get('detected_patch') else 'ffta.gba'
    (output / name).write_bytes(image)
    (output / 'package-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    names = [name, 'package-report.json']
    if credit['applied']:
        (output / 'author.txt').write_text(credit['text'] + '\n', encoding='utf-8')
        write_preview(image, output / 'splash-author.png')
        names += ['author.txt', 'splash-author.png']
    (output / 'SHA256SUMS.txt').write_text(''.join(
        sha((output / n).read_bytes()) + '  ' + n + '\n' for n in names), encoding='ascii')
    names.append('SHA256SUMS.txt')
    archive = output / 'ffta-rom.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for n in names:
            entry = zipfile.ZipInfo(n, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            zipped.writestr(entry, (output / n).read_bytes())
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None or sha(zipped.read(name)) != report['output_sha256']:
            raise ValueError('ROM ZIP verification failed')
    return archive, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', required=True, type=Path)
    parser.add_argument('--patch', type=Path, help='Optional local IPS, applied before CN detection')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--author-file', type=Path, default=AUTHOR)
    parser.add_argument('--disable-author', action='store_true', help='Preserve exact-reference bytes')
    args = parser.parse_args()
    archive, report = package(args.rom, args.output_dir, args.author_file, args.patch, not args.disable_author)
    print(json.dumps(dict(archive=str(archive), **report), ensure_ascii=False))


if __name__ == '__main__':
    main()
