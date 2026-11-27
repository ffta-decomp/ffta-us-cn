#!/usr/bin/env python3
"""Check the actual ending save and cold battle-name display on a local ROM."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from replay_recruit_save_slots import PAGE, companion_page


def replay(probe, rom, battery, commands):
    result = subprocess.run([probe, rom, battery], input='\n'.join([*commands, 'quit']) + '\n',
                            text=True, capture_output=True, check=True, timeout=120)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('probe', 'rom', 'save', 'mission-entry-keys', 'battle-list-keys'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--roster-slot', type=int, required=True, choices=range(1, 25))
    args = parser.parse_args()
    source = args.save.read_bytes()
    old = companion_page(source, 0)
    index = args.roster_slot - 1
    offset = 16 + index * 24 + 4
    text = source[old + offset:old + offset + 20]
    if not text[0]:
        raise ValueError('The specified roster slot needs a displayable custom name')
    unit = 0x02000080 + 264 * index
    # RAM starts with NameBlock; its alias text uses the same offset as on disk.
    alias = 0x0203F800 + offset
    with tempfile.TemporaryDirectory(prefix='ffta-ending-') as directory:
        battery = Path(directory) / 'battery.sav'
        battery.write_bytes(source)
        keys = [k for k in args.mission_entry_keys.read_text().splitlines() if k.startswith('run ')]
        # Arm scene 105 only at the known idle mission-entry boundary, then let
        # the retail script play through the credits and save with game input.
        checkpoint = Path(directory) / 'entry.ss1'
        log = replay(args.probe, args.rom, battery, keys + [
            'peek 02002192 c', 'peek 020159cc 4', f'savestate {checkpoint}'])
        if '02002192 0e000e000000000000000100' not in log or '020159cc 00000000' not in log:
            raise ValueError('Key replay did not reach the idle mission-entry boundary')
        log = replay(args.probe, args.rom, battery, [
            f'loadstate {checkpoint}', 'poke16 02002192 69', 'poke16 02002194 69', 'run 18240 0',
            'watch 0812c420', 'watch 0812c450', 'run 2 1', 'run 75 0', 'run 2 8', 'run 75 0',
            'run 300 0', 'clear', 'run 90 0'])
        if any(f' {pc} lr=' not in log for pc in ('0812c420', '0812c450')):
            raise ValueError('The ending script did not read and write its selected file')
        saved = battery.read_bytes()
        current = companion_page(saved, 0)
        if (source[old + 4:old + 8] == saved[current + 4:current + 8] or
                source[old + 12:old + PAGE] != saved[current + 12:current + PAGE]):
            raise ValueError('Ending save did not carry the verified companion page forward')
        keys = [k for k in args.battle_list_keys.read_text().splitlines()
                if k.startswith(('run ', 'rununtil ', 'watch ', 'clear'))]
        log = replay(args.probe, args.rom, battery, [*keys, f'peek {alias:08x} 14'])
        row = rf'0802586a .*args={unit:08x} [^\n]*\nhit \d+ 0802586e .*args={alias:08x} '
        if not re.search(row, log) or f'{alias:08x} {text.hex()}' not in log:
            raise ValueError('Cold battle list did not render the saved alias for this unit')
    print('Ending save and cold battle list preserved the custom name.')


if __name__ == '__main__':
    main()
