#!/usr/bin/env python3
"""Fetch explicitly locked public Git sources; dependency checkouts stay ignored."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

from verify_vendor import verify_dependency

ROOT = Path(__file__).resolve().parents[1]


def git(directory, *args):
    return subprocess.check_output(['git', '-C', str(directory), *args], text=True).strip()


def fetch(root=ROOT):
    root = Path(root).resolve()
    dependencies = json.loads((root / 'config/dependencies.lock.json').read_text())['dependencies']
    for dependency in dependencies:
        destination = (root / dependency['directory']).resolve()
        if not destination.is_relative_to(root / 'vendor'):
            raise ValueError('Dependency checkout must be under vendor/')
        if not re.fullmatch(r'[0-9a-f]{40}', dependency['revision']):
            raise ValueError('Dependency requires a complete Git commit')
        if destination.exists():
            verify_dependency(root, dependency)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='ffta-git-dependency-') as temporary:
            checkout = Path(temporary) / 'source'
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
            git(checkout, 'fetch', '-q', '--depth=1', '--', dependency['url'], dependency['revision'])
            git(checkout, 'checkout', '-q', '--detach', 'FETCH_HEAD')
            if git(checkout, 'rev-parse', 'HEAD') != dependency['revision']:
                raise ValueError('Fetched dependency commit differs')
            if dependency.get('compiler_revision'):
                # The upstream .gitmodules is part of the verified source lock.
                module = git(checkout, 'ls-tree', 'HEAD', 'vendor/agbcc')
                if module.split()[2] != dependency['compiler_revision']:
                    raise ValueError('Upstream compiler submodule differs from lock')
                git(checkout, 'submodule', 'update', '--init', '--depth=1', '--', 'vendor/agbcc')
            # Verify the exact exported file inventory before installing a checkout.
            relative = checkout.relative_to(Path(temporary)).as_posix()
            staged = dict(dependency, directory=relative)
            verify_dependency(Path(temporary), staged)
            # Move on the same filesystem without copying Git/compiler source trees.
            import shutil
            shutil.move(str(checkout), str(destination))
        print(dependency['name'] + ': fetched ' + dependency['revision'])
    return len(dependencies)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps({'dependencies_ready': fetch()}))


if __name__ == '__main__':
    main()
