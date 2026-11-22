#!/usr/bin/env python3
"""Check the native unread palette bridge using an explicit private ROM."""
import argparse
import hashlib
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12,
    UC_ARM_REG_SP, UC_ARM_REG_LR)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom',type=Path);p.add_argument('--sha256',required=True);args=p.parse_args()
    rom=args.rom.read_bytes();assert hashlib.sha256(rom).hexdigest()==args.sha256
    badge=rom[0xf42000:0xf42080];assert len(badge)==128 and any(badge)
    registers=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,
        UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
        UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12]
    cases=0
    for tile in range(4):
        for corrupt in (False,True):
            for flips in (0,0x400,0x800,0xc00):
                uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
                uc.mem_map(0x08000000,len(rom));uc.mem_write(0x08000000,rom)
                uc.mem_map(0x06000000,0x18000);uc.mem_map(0x03000000,0x8000)
                art=bytearray(badge[tile*32:(tile+1)*32])
                if corrupt:art[0]^=0x80
                uc.mem_write(0x06008200,bytes(art))
                values=[0x110000+n*0x100 for n in range(13)];values[0]=16|flips
                for reg,value in zip(registers,values):uc.reg_write(reg,value)
                uc.reg_write(UC_ARM_REG_SP,0x03007000);uc.reg_write(UC_ARM_REG_LR,0x03007f01)
                uc.emu_start(0x0836d3b9,0x03007f00,count=50000)
                for n,reg in enumerate(registers):
                    expected=(0xd000 if corrupt else 0xe000) if n==6 else values[n]
                    assert uc.reg_read(reg)==expected,(tile,corrupt,flips,n)
                assert uc.reg_read(UC_ARM_REG_SP)==0x03007000
                cases+=1
    print(f'{cases} native badge palette and register/stack cases passed')


if __name__=='__main__':main()
