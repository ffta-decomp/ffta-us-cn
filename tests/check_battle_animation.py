#!/usr/bin/env python3
"""Identity-bound native animation regression; requires an explicit local ROM.

Run with a battle-speed-enabled candidate and the optional Unicorn package.
No copyrighted fixtures or build outputs are discovered or written here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR, UC_ARM_REG_SP


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    assert len(rom) == 0x1000000 and hashlib.sha256(rom).hexdigest() == args.sha256
    assert rom[0x36d3b0:0x36d3b4] == bytes.fromhex('004b1847')
    anim, owner, renderer, frames = 0x02028000, 0x02018000, 0x02019000, 0x02029000
    stop = 0x03007f00

    def run(patched, steps, *, enabled=True, linked=False, live=True,
            valid_owner=True, matching_renderer=True, flags=3, timer=5, event=False, mode=1):
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        uc.mem_map(0x08000000, len(rom)); uc.mem_write(0x08000000, rom)
        uc.mem_map(0x02000000, 0x40000); uc.mem_map(0x03000000, 0x8000)
        w32 = lambda at,v: uc.mem_write(at,struct.pack('<I',v))
        uc.mem_write(0x02002fc3,bytes([mode << 3 if enabled else 0]))
        uc.mem_write(0x0200f424,struct.pack('<H',0x80 if linked else 0))
        w32(0x0200f4a8,0x0200f4e8 if live else 0)
        w32(0x0200f4b0,owner if valid_owner else 0)
        w32(owner+8,renderer)
        uc.mem_write(anim,bytes(64)); w32(anim,flags)
        uc.mem_write(anim+10,struct.pack('<hhh',timer,0,3))
        w32(anim+52,frames); w32(anim+56,frames)
        for i in range(3):
            record=bytearray(20);record[8]=5
            if event and i==0: record[9]=8;record[10]=1
            uc.mem_write(frames+i*20,bytes(record))
        calls=[]
        uc.hook_add(UC_HOOK_CODE,lambda u,a,n,d: calls.append(a) if a==0x08021290 else None)
        for _ in range(steps):
            uc.reg_write(UC_ARM_REG_R0,anim)
            uc.reg_write(UC_ARM_REG_R1,renderer+20 if matching_renderer else renderer+24)
            uc.reg_write(UC_ARM_REG_SP,0x03007000)
            uc.reg_write(UC_ARM_REG_LR,stop|1)
            uc.emu_start(0x0836d3b1 if patched else 0x08021291,stop,count=50000)
            assert uc.reg_read(UC_ARM_REG_SP)==0x03007000
        return bytes(uc.mem_read(anim,64)),len(calls)

    count=0
    for mode in (1,2,3):
        multiplier=1 << mode
        for timer in range(1,12):
            for flags in (3,0x4003,0x1003):
                for steps in (1,2,7,19):
                    got,calls=run(True,steps,timer=timer,flags=flags,mode=mode)
                    expected,_=run(False,steps*multiplier,timer=timer,flags=flags)
                    assert got==expected and calls==steps*multiplier,(mode,timer,flags,steps)
                    count+=1
    for kw in (dict(enabled=False),dict(linked=True),dict(live=False),
               dict(valid_owner=False),dict(matching_renderer=False),
               dict(flags=0x103),dict(flags=0x2003)):
        got,calls=run(True,7,**kw);expected,_=run(False,7,**kw)
        assert got==expected and calls==7,kw
        count+=1
    for mode in (1,2,3):
        for timer in (1,2):
            got,calls=run(True,1,timer=timer,event=True,mode=mode)
            expected,_=run(False,timer,timer=timer,event=True)
            assert got==expected and got[30]==0x81 and calls==timer
            count+=1
    print(json.dumps(dict(rom_sha256=args.sha256,native_cases=count,
        multipliers_match_native=[2,4,8],event_preserved=True,off_menu_link_guards=True)))


if __name__=='__main__':
    main()
