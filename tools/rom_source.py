#!/usr/bin/env python3
"""Read one private GitHub repository URL from the personal clone's root file."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'rom-source.txt'


def load(path=CONFIG):
    path = Path(path)
    if not path.is_file():
        return None
    url = path.read_text(encoding='utf-8').strip()
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?', url)
    if not match:
        raise ValueError('rom-source.txt must contain one GitHub HTTPS or SSH URL, without credentials')
    return dict(url=url, repository=match[1])


def checkout(destination, config=CONFIG):
    source = load(config)
    if source is None:
        raise ValueError('Create rom-source.txt in your personal source clone with the private ROM Git URL')
    destination = Path(destination).resolve()
    if destination.is_relative_to(Path(config).resolve().parent):
        raise ValueError('Private ROM checkout must stay outside the source project')
    if destination.exists():
        raise ValueError('Choose a new ROM checkout directory; existing inputs are never overwritten')
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'clone', '--depth=1', '--', source['url'], str(destination)], check=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--github-output', type=Path)
    mode.add_argument('--clone-to', type=Path)
    args = parser.parse_args()
    if args.clone_to:
        checkout(args.clone_to, args.config)
    else:
        source = load(args.config)
        with args.github_output.open('a') as stream:
            stream.write('configured=' + ('true' if source else 'false') + '\n')
            if source:
                stream.write('repository=' + source['repository'] + '\n')
        if source is None:
            print('ROM build disabled: this source clone has no rom-source.txt')


if __name__ == '__main__':
    main()
