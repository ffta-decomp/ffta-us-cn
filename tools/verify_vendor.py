#!/usr/bin/env python3
"""Check every dependency source against the immutable vendor lock."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify():
    lock = json.loads((ROOT / 'vendor/lock.json').read_text())
    count = 0
    for dependency in lock['dependencies']:
        directory = ROOT / dependency['directory']
        for name, digest in dependency['files'].items():
            path = directory / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('Vendor hash mismatch: ' + str(path.relative_to(ROOT)))
            count += 1
    return count


if __name__ == '__main__':
    print(json.dumps({'verified_dependency_files': verify()}))
