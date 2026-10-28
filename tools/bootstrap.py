#!/usr/bin/env python3
"""Build the pinned compiler in an external directory; vendor stays read-only."""
import argparse
from pathlib import Path
import shutil
import subprocess

from verify_vendor import verify

ROOT = Path(__file__).resolve().parents[1]


def bootstrap(build_dir):
    verify()
    destination = Path(build_dir).resolve() / 'toolchain'
    destination.mkdir(parents=True, exist_ok=True)
    binary = destination / 'agbcc'
    if binary.exists():
        return binary
    work = destination / 'bootstrap-work'
    if work.exists():
        raise ValueError('Inspect the retained bootstrap-work before retrying')
    shutil.copytree(ROOT / 'vendor/fftadecomp/vendor/agbcc/gcc', work)
    with (destination / 'bootstrap.log').open('w') as log:
        subprocess.run(['make', '-C', str(work), '-j1', 'CC=clang'],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    shutil.copy2(work / 'agbcc', binary)
    shutil.rmtree(work)
    return binary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', required=True, type=Path)
    args = parser.parse_args()
    if args.build_dir.resolve().is_relative_to(ROOT):
        parser.error('Build directory must be external')
    print(bootstrap(args.build_dir))
