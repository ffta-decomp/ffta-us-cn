#!/usr/bin/env python3
"""Cold-boot fastskip menu and two-battle acceptance with explicit mGBA inputs.

No saves or states are discovered or supplied. Every state is generated from
this selected ROM using ordinary button events; all outputs remain external.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]


def png(ppm):
    rgb = ppm.read_bytes().split(b'\n', 3)[3]
    if len(rgb) != 240 * 160 * 3:
        raise ValueError('Unexpected emulator framebuffer size')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    raw = b''.join(b'\0' + rgb[y * 720:(y + 1) * 720] for y in range(160))
    ppm.with_suffix('.png').write_bytes(b'\x89PNG\r\n\x1a\n' +
        chunk(b'IHDR', struct.pack('>2I5B', 240, 160, 8, 2, 0, 0, 0)) +
        chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def half(ram, offset):
    return int.from_bytes(ram[offset:offset + 2], 'little')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', required=True, type=Path)
    parser.add_argument('--rom', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.is_relative_to(ROOT):
        parser.error('Emulator evidence must be external')
    out.mkdir(parents=True, exist_ok=False)
    records = []

    def run(label, frames, events='', source=None):
        inputs = out / (label + '.input')
        inputs.write_text(events)
        command = [str(args.replay.resolve()), str(args.rom.resolve()), str(frames),
                   str(inputs), str(out / (label + '.ppm')),
                   '--state-out', str(out / (label + '.ss1')),
                   '--dump-ewram', str(frames), str(out / (label + '.ewram'))]
        if source:
            command += ['--state-in', str(out / (source + '.ss1'))]
        with (out / (label + '.json')).open('w') as stdout, (out / (label + '.log')).open('w') as stderr:
            subprocess.run(command, stdout=stdout, stderr=stderr, check=True, timeout=60)
        errors = (out / (label + '.log')).read_text()
        if any(s in errors.lower() for s in ['illegal opcode', 'invalid address', 'fatal']):
            raise ValueError('Emulator error in ' + label + ': ' + errors)
        ram = (out / (label + '.ewram')).read_bytes()
        records.append(dict(stage=label, frames=frames, scene=half(ram, 0x2192),
                            option=int.from_bytes(ram[0x3fff4:0x3fff8], 'little'),
                            ram_sha256=hashlib.sha256(ram).hexdigest()))
        png(out / (label + '.ppm'))
        return ram

    run('boot', 900)
    ram = run('title', 600, '10 8\n12 0\n200 8\n202 0\n', 'boot')
    assert struct.unpack_from('<4I', ram, 0x3fff0) == (0x534e4f57, 0, 0xffffffff, 0)
    ram = run('options-off', 240,
        '10 80\n12 0\n40 80\n42 0\n70 10\n72 0\n100 1\n102 0\n140 40\n142 0\n', 'title')
    context = int.from_bytes(ram[0xf3b0:0xf3b4], 'little') - 0x02000000
    assert ram[context + 0x899c:context + 0x899f] == bytes([1, 3, 0])
    ram = run('options-on', 120, '10 1\n12 0\n', 'options-off')
    assert struct.unpack_from('<4I', ram, 0x3fff0) == (0x534e4f57, 1, 0xfffffffe, 0)
    ram = run('options-back-off', 120, '10 1\n12 0\n', 'options-on')
    assert half(ram, 0x3fff4) == 0
    start = '10 2\n12 0\n40 80\n42 0\n70 1\n72 0\n'
    advance = ''.join(f'{frame} 1\n{frame + 2} 0\n' for frame in range(20, 6000, 60))
    accept = '10 20\n12 0\n40 1\n42 0\n' + ''.join(
        f'{frame} 1\n{frame + 2} 0\n' for frame in range(200, 9000, 90))
    snow = {}
    for enabled, menu in [('on', 'options-on'), ('off', 'options-back-off')]:
        ram = run(enabled + '-newgame', 900, start, menu)
        assert half(ram, 0x3fff4) == (enabled == 'on'), 'heap cleared the option'
        run(enabled + '-dialogue', 6000, advance, enabled + '-newgame')
        run(enabled + '-name', 180, '10 2\n12 0\n40 8\n42 0\n', enabled + '-dialogue')
        ram = run(enabled + '-snow', 9000, accept, enabled + '-name')
        assert half(ram, 0x2192) == 6
        expected = 1 if enabled == 'on' else 8
        assert half(ram, 0x2fc4 + 264 * 5 + 24) == expected
        snow[enabled] = ram
    run('snow-wait', 700,
        '10 2\n12 0\n40 80\n42 0\n70 80\n72 0\n100 1\n102 0\n160 1\n162 0\n', 'on-snow')
    ram = run('second-battle', 9000, ''.join(
        f'{frame} 1\n{frame + 2} 0\n' for frame in range(20, 9000, 90)), 'snow-wait')
    assert half(ram, 0x2192) == 11
    # Close the native law notice before reaching the normal command boundary.
    ram = run('second-commands', 3000, '10 2\n12 0\n' + ''.join(
        f'{frame} 1\n{frame + 2} 0\n' for frame in range(100, 3000, 90)), 'second-battle')
    assert [half(ram, 0x2fc4 + 264 * i + 24) for i in (0, 1)] == [1, 1]
    assert half(ram, 0x2fc4 + 264 * 2 + 24) > 1
    assert not ram[0x1f70] & 4
    assert any(snow['on'][0x1f1c:0x1f30])
    assert ram[0x1f1c:0x1f30] == snow['on'][0x1f1c:0x1f30]
    report = dict(status='passed', rom_sha256=hashlib.sha256(args.rom.read_bytes()).hexdigest(),
                  input_saves_or_states=False, menu_toggle_both_directions=True,
                  disabled_snow_target_hp=8, enabled_snow_target_hp=1,
                  reached_second_battle=True, protagonist_name_preserved=True, stages=records,
                  scope='Cold boot, title Options, naming, snowball and second-battle entry; no hardware or save-reload acceptance')
    (out / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
