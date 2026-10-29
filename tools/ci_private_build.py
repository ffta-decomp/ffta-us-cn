#!/usr/bin/env python3
"""Manual CI build from an explicitly provided private ZIP, identified by SHA-256."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROM_BYTES = 0x1000000
ROM_HASHES = {
    'retail': '43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19',
    'translated': 'ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03',
}
MAX_DOWNLOAD = 64 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('Private download redirects must use HTTPS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(destination):
    url = os.environ.get('PRIVATE_ROM_ARCHIVE_URL', '')
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('Set PRIVATE_ROM_ARCHIVE_URL to a private HTTPS ZIP download URL')
    request = urllib.request.Request(url, headers={'Accept': 'application/octet-stream'})
    # Same-repository private release assets can use the job's read-only token.
    # Unredirected headers never follow the asset's signed CDN redirect.
    parsed = urllib.parse.urlsplit(url)
    repository = os.environ.get('GITHUB_REPOSITORY', '')
    if parsed.netloc == 'api.github.com' and repository and \
       parsed.path.startswith('/repos/' + repository + '/releases/assets/'):
        token = os.environ.get('GH_TOKEN', '')
        if token:
            request.add_unredirected_header('Authorization', 'Bearer ' + token)
    # Never print request exceptions: they can contain the signed private URL.
    try:
        with urllib.request.build_opener(HTTPSRedirects()).open(request, timeout=120) as response:
            with Path(destination).open('xb') as output:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD:
                        raise ValueError('Archive exceeds download limit')
                    output.write(chunk)
    except Exception:
        raise ValueError('Private ROM archive download failed (details suppressed)') from None


def identify(archive, output):
    """Read only the explicitly supplied ZIP; member names never select ROM roles."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    found = {}
    with zipfile.ZipFile(archive) as zipped:
        if len(zipped.infolist()) > 64:
            raise ValueError('ROM archive contains too many members')
        for member in zipped.infolist():
            if member.is_dir():
                continue
            if member.file_size != ROM_BYTES:
                if Path(member.filename).suffix.lower() in {'.gba', '.rom'}:
                    raise ValueError('ROM size does not match a supported reference')
                continue
            data = zipped.read(member)
            digest = sha(data)
            role = next((name for name, expected in ROM_HASHES.items() if digest == expected), None)
            if role is None:
                raise ValueError('Unsupported ROM SHA-256: ' + digest)
            if role in found:
                raise ValueError('Duplicate ROM for role: ' + role)
            path = output / (role + '.gba')
            path.write_bytes(data)
            found[role] = path
    if set(found) != set(ROM_HASHES):
        raise ValueError('Archive must contain exactly one authenticated US and one CN v1.1 ROM')
    return found


def glyph_inputs(translated, output):
    """Recover the build map from the committed owner-provided native table."""
    rom = Path(translated).read_bytes()
    if sha(rom) != ROM_HASHES['translated']:
        raise ValueError('Wrong translated ROM')
    table = ROOT / 'config/charsets/us-cn-v1.1/character-table.json'
    rows = json.loads(table.read_text())['glyphs']
    if len(rows) != 3175:
        raise ValueError('Incomplete native character table')
    mapping = {}
    for index, row in enumerate(rows):
        cell = rom[0x433330 + index * 128:0x433330 + (index + 1) * 128]
        if row['index'] != index or row['glyph_sha256'] != sha(cell) or \
           row['advance'] != rom[0x4966B0 + index]:
            raise ValueError('Character table differs from the supplied CN font')
        character = row['unicode']
        if character and len(character) == 1 and '\u3400' <= character <= '\u9fff':
            mapping.setdefault(character, 0x8000 | index)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    data = json.dumps(mapping, ensure_ascii=True, sort_keys=True).encode()
    (output / 'glyph-map.json').write_bytes(data)
    report = dict(schema=1, translated_sha256=sha(rom),
                  native_font_sha256=sha(rom[0x433330:0x4966B0]),
                  glyph_map_sha256=sha(data), source_table_sha256=sha(table.read_bytes()),
                  mapped_characters=len(mapping),
                  proof='Owner-provided CN v1.1 native table; Hanzi subset; lowest token for aliases')
    (output / 'map-report.json').write_text(json.dumps(report, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--publish-dir', required=True, type=Path)
    parser.add_argument('--profile', choices=['default', 'exact-reference'], default='default')
    args = parser.parse_args()
    work, publish = args.work_dir.resolve(), args.publish_dir.resolve()
    if work.is_relative_to(ROOT) or publish.is_relative_to(ROOT) or \
       work.is_relative_to(publish) or publish.is_relative_to(work):
        parser.error('Work and publish directories must be separate and outside the repository')
    work.mkdir(parents=True, exist_ok=False)
    archive = work / 'inputs.zip'
    download(archive)
    roms = identify(archive, work / 'roms')
    archive.unlink()
    def run(tool, *options):
        subprocess.run([sys.executable, str(ROOT / 'tools' / tool), *map(str, options)], check=True)
    run('export_us_cn.py', '--retail', roms['retail'], '--translated', roms['translated'],
        '--output-dir', work / 'resources')
    glyph_inputs(roms['translated'], work / 'glyph-inputs')
    command = ['--retail', roms['retail'], '--pack-dir', work / 'resources/pack',
               '--glyph-map', work / 'glyph-inputs/glyph-map.json',
               '--map-report', work / 'glyph-inputs/map-report.json',
               '--output-dir', work / 'build', '--patch-output', work / 'output.ips']
    if args.profile == 'exact-reference':
        command += ['--disable-pinyin', '--disable-link-fix', '--disable-info', '--disable-italic-font']
    run('build.py', *command)
    built = (work / 'build/ffta-us-cn.gba').read_bytes()
    if args.profile == 'exact-reference' and sha(built) != ROM_HASHES['translated']:
        raise ValueError('Exact-reference profile differs from CN v1.1 (disable custom plugins)')
    # Explicit allowlist: never publish a directory containing private resources.
    publish.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(work / 'output.ips', publish / 'ffta-us-cn.ips')
    report = dict(schema=1, profile=args.profile, input_sha256=ROM_HASHES,
                  output_sha256=sha(built), patch_sha256=sha((work / 'output.ips').read_bytes()),
                  source_commit=os.environ.get('GITHUB_SHA'),
                  plugin_lock_sha256=sha((ROOT / 'config/plugin-projects.lock.json').read_bytes()),
                  reference_reconstruction=json.loads((work / 'resources/byte-match.json').read_text()))
    (publish / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
