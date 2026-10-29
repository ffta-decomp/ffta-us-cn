#!/usr/bin/env python3
"""Package committed source plus pinned vendor files, with stable archive metadata."""
import argparse
import gzip
import io
from pathlib import Path
import subprocess
import tarfile

from verify_vendor import verify
from plugin_projects import locked

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):
        parser.error('Source archive must be external')
    verify()
    names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().split('\0')
    plugins = locked()
    names = set(filter(None, names))
    for record in plugins['projects'].values():
        names.update(str(Path(record['directory']) / name) for name in record['files'])
    forbidden = {'.gba', '.rom', '.bin', '.ttf', '.otf', '.png', '.ppm', '.sav', '.state', '.ips', '.bps'}
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w', format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(filter(None, names)):
            path = ROOT / name
            if path.suffix.lower() in forbidden or not path.is_file():
                raise ValueError('Non-source archive member: ' + name)
            data = path.read_bytes()
            entry = tarfile.TarInfo('ffta-us-cn/' + name)
            entry.size = len(data)
            entry.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            entry.mtime = 0
            tar.addfile(entry, io.BytesIO(data))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('wb') as out:
        with gzip.GzipFile(fileobj=out, filename='', mode='wb', mtime=0) as zipped:
            zipped.write(archive.getvalue())


if __name__ == '__main__':
    main()
