#!/usr/bin/env python3
"""Copy a US battery save for the recruit naming plugin's 128 KiB Flash."""
import argparse
from pathlib import Path

NATIVE_BYTES = 64 * 1024
EXTENDED_BYTES = 2 * NATIVE_BYTES


def expand(source, destination):
    data = source.read_bytes()
    if len(data) == NATIVE_BYTES:
        data += b'\xff' * NATIVE_BYTES
    elif len(data) != EXTENDED_BYTES:
        raise ValueError('Expected a raw 64 KiB or 128 KiB battery save')
    with destination.open('xb') as output:
        output.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    try:
        expand(args.source, args.destination)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
