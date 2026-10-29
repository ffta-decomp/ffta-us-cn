#!/usr/bin/env python3
"""Check every dependency source against the immutable vendor lock."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify_dependency(root, dependency):
    directory = root / dependency['directory']
    for name, digest in dependency['files'].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError('Missing dependency source: ' + name + '; run python3 tools/fetch_dependencies.py')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Dependency hash mismatch: ' + str(path))
    return len(dependency['files'])


def verify():
    lock = json.loads((ROOT / 'config/dependencies.lock.json').read_text())
    count = sum(verify_dependency(ROOT, dependency) for dependency in lock['dependencies'])
    if (ROOT / 'config/plugin-projects.lock.json').is_file():
        from plugin_projects import locked
        plugins = locked()
        count += sum(len(project['files']) for project in plugins['projects'].values())
    return count


if __name__ == '__main__':
    print(json.dumps({'verified_dependency_files': verify()}))
