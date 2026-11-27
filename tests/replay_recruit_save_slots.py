#!/usr/bin/env python3
"""Exercise slot rotation on a disposable copy of a battery save with a renamed recruit."""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zlib

BANK = 65536
PAGE = 4096
SLOTS = (0, 1, 2)
PROBES = (592, 0xBFC, 0xC20, 0xFFC)


def companion_page(data, slot):
    headers = []
    for offset in range(0, BANK, PAGE):
        header = data[offset:offset + 26]
        if header[:8] == b'FFTEX000' and header[16] == slot:
            headers.append(header)
    if not headers:
        raise ValueError(f'Missing native slot {slot}')
    header = max(headers, key=lambda h: int.from_bytes(h[8:12], 'little', signed=True))
    for sector, magic in zip(header[18:20], (b'RRN2', b'RRN3')):
        start = BANK + sector * PAGE
        if data[start:start + 12] == magic + header[8:16]:
            crc, = struct.unpack_from('<I', data, start + 12)
            if crc == zlib.crc32(data[start + 16:start + 592]):
                return start
    raise ValueError(f'No current companion page for slot {slot}')


def replay(probe, rom, source, work, commands):
    temporary = work / 'input.sav'
    temporary.write_bytes(source)
    result = work / 'result.sav'
    commands = [*commands, f'save {result}', 'quit']
    output = subprocess.run([probe, rom, temporary], input='\n'.join(commands) + '\n',
                            capture_output=True, text=True, check=True, timeout=120).stdout
    return result.read_bytes(), output


def run(probe, rom, source, work, boot, slots):
    commands = [*boot, 'call 0836d394 0 02000000']
    commands.extend(f'call 0813b0d4 {slot:x} 02000000' for slot in slots)
    data, output = replay(probe, rom, source, work, commands)
    calls = re.findall(r'^call (0836d394|0813b0d4) result=([a-f0-9]+)', output, re.M)
    if calls != [('0836d394', '00000001')] + [('0813b0d4', '00000001')] * len(slots):
        raise ValueError('Native slot operation failed')
    return data


def check_file_ownership(args, work, boot, data):
    # Give the same native recruit different aliases in the two files.
    data = bytearray(data)
    target = companion_page(data, 1)
    record = next(offset for offset in range(16, 592, 24)
                  if data[target + offset + 4])
    text = target + record + 4
    glyph = b'\x80\xb1' if data[text:text + 2] == b'\x80\xb0' else b'\x80\xb0'
    data[text:text + 20] = glyph + bytes(18)
    struct.pack_into('<I', data, target + 12, zlib.crc32(data[target + 16:target + 592]))
    # Exercise both states of the native ending callback with file 1 in RAM
    # while the selected read/modify/write transaction targets file 2.
    commands = [*boot, 'call 0836d394 0 02000000', 'poke16 0200e400 104',
                'poke16 0200e426 1', 'call 0812c2b8 0 0200e400 0200e420',
                'call 0812c2b8 0 0200e400 0200e420', 'peek 0200e425 1']
    saved, log = replay(args.probe, args.rom, data, work, commands)
    new = companion_page(saved, 1)
    if ('0200e425 1b' not in log or saved[new + 4:new + 8] == data[target + 4:target + 8]
            or saved[new + 12:new + PAGE] != data[target + 12:target + PAGE]):
        raise ValueError('The ending failed to retain the selected file’s own names and reserved bytes')

    # Simulate loading a native-only party, then save over the other files.
    # Drop this file's two candidate pages only, preserving both targets.
    first = companion_page(data, 0)
    for offset in range(0, BANK, PAGE):
        header = data[offset:offset + 26]
        if header[:8] == b'FFTEX000' and header[16] == 0 and header[8:16] == data[first + 4:first + 12]:
            for sector in header[18:20]:
                start = BANK + sector * PAGE
                data[start:start + PAGE] = b'\xff' * PAGE
            break
    else:
        raise ValueError('Missing native header for the mixed-format control')
    saved = run(args.probe, args.rom, data, work, boot, (1, 2))
    for slot in (1, 2):
        old, new = companion_page(data, slot), companion_page(saved, slot)
        if (any(saved[new + 16:new + 592]) or
                any(saved[new + p:new + p + 4] != data[old + p:old + p + 4] for p in PROBES)):
            raise ValueError(f'Unnamed party inherited aliases or lost reserved bytes in slot {slot}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True, help='Interactive mGBA replay driver')
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--save', type=Path, required=True, help='Input with a valid alias in regular slot 1')
    parser.add_argument('--boot-keys', type=Path, required=True, help='Button replay to the loaded party')
    args = parser.parse_args()
    boot = [line for line in args.boot_keys.read_text().splitlines() if line.startswith('run ')]
    with tempfile.TemporaryDirectory(prefix='ffta-recruit-rotation-') as output:
        work = Path(output)
        data = bytearray(run(args.probe, args.rom, args.save.read_bytes(), work, boot, SLOTS))
        for slot in SLOTS:
            start = companion_page(data, slot)
            for offset in PROBES:
                data[start + offset:start + offset + 4] = bytes((0xA7, slot, offset >> 8, 0x55))
        for _ in range(2):
            data = run(args.probe, args.rom, data, work, boot, SLOTS)
            for slot in SLOTS:
                start = companion_page(data, slot)
                for offset in PROBES:
                    if data[start + offset:start + offset + 4] != bytes((0xA7, slot, offset >> 8, 0x55)):
                        raise ValueError(f'Slot {slot} lost its reserved bytes at {offset:#x}')
        check_file_ownership(args, work, boot, data)
    print('Regular and suspend slot rotation, ending file ownership and unnamed-party overwrite passed.')


if __name__ == '__main__':
    main()
