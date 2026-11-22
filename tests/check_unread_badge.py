#!/usr/bin/env python3
"""Check the native unread palette bridge using an explicit private ROM."""
import argparse
import hashlib
import struct
import subprocess
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)


def check_wide(rom, elf):
    symbols={}
    for row in subprocess.check_output(['arm-none-eabi-nm','-n',str(elf)],text=True).splitlines():
        parts=row.split()
        if len(parts)==3: symbols[parts[2]]=int(parts[0],16)
    def core():
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for at,size in ((0x08000000,len(rom)),(0x02000000,0x40000),
                        (0x06000000,0x18000),(0x03000000,0x8000)):
            uc.mem_map(at,size)
        uc.mem_write(0x08000000,rom)
        return uc
    def call(uc,name,*args):
        for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):uc.reg_write(reg,value)
        uc.reg_write(UC_ARM_REG_SP,0x03007000);uc.reg_write(UC_ARM_REG_LR,0x03007f01)
        uc.emu_start(symbols[name]|1,0x03007f00,count=50000)
        assert uc.reg_read(UC_ARM_REG_SP)==0x03007000
    control,view=0x02010000,0x0201003c
    count=0
    for mode,width,period,base,storage,expected in (
        (2,16,9,448,control+168,17),(7,16,9,448,control+168,16),
        (2,15,9,448,control+168,15),(2,16,0,448,control+168,16),
        (2,16,9,1000,control+168,16),(2,16,9,448,control+0x1090,16)):
        uc=core();uc.mem_write(control,bytes([mode]));uc.mem_write(view+12,struct.pack('<I',storage))
        uc.mem_write(view+18,bytes([width]));uc.mem_write(view+21,bytes([width,8,period]))
        uc.mem_write(view+28,struct.pack('<H',base));call(uc,'ConfigureWideUnreadBridge',view,1,4)
        assert bytes(uc.mem_read(view+21,1))==bytes([expected])
        assert uc.mem_read(view+16,1)[0]&4
        count+=1
    old=rom[0xf42000:0xf42080];wide=rom[0xf43000:0xf430c0];destination=0x0600b800
    for unread,width,mode in ((True,17,2),(False,17,2),(True,16,2),(True,17,7)):
        uc=core();uc.mem_write(control,bytes([mode]));uc.mem_write(control+81,bytes([width]))
        uc.mem_write(control+79,b'\x07');uc.mem_write(control+112,struct.pack('<IIH',0x08017f05,view,192))
        uc.mem_write(destination,b'\xa5'*0x440+b'\x5a'*64)
        def native(u,address,size,data):
            if address==0x0805fff0:
                u.mem_write(destination+0x380,old if unread else bytes(128))
            elif address==0x0814186c:
                source=u.reg_read(UC_ARM_REG_R0);target=u.reg_read(UC_ARM_REG_R1);length=u.reg_read(UC_ARM_REG_R2)*2
                assert length==192 and target==destination+0x380
                u.mem_write(target,bytes(u.mem_read(source,length)))
            else:return
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        uc.hook_add(UC_HOOK_CODE,native)
        call(uc,'FinishWideUnreadBridge',control,destination,2)
        if unread and width==17 and mode==2:
            assert bytes(uc.mem_read(destination+0x380,192))==wide
        else:
            assert bytes(uc.mem_read(destination+0x380,128))==(old if unread else bytes(128))
            assert bytes(uc.mem_read(destination+0x400,64))==b'\xa5'*64
        assert bytes(uc.mem_read(destination,0x380))==b'\xa5'*0x380
        assert bytes(uc.mem_read(destination+0x440,64))==b'\x5a'*64
        count+=1
    for mode,width,expected in ((2,17,184),(7,17,192),(2,16,184)):
        uc=core();uc.mem_write(control,bytes([mode]));uc.mem_write(view+19,bytes([7,3,width,8,9]))
        uc.mem_write(view+24,struct.pack('<H',21))
        uc.reg_write(UC_ARM_REG_R4,0x11223344)
        call(uc,'WideUnreadScrollbarBridge',control+112,view,0x08017f05)
        assert uc.reg_read(UC_ARM_REG_R4)==0x11223344
        # The fourth argument is zero in this controlled native initializer.
        assert struct.unpack('<H',uc.mem_read(control+120,2))[0]==expected
        count+=1
    for part in range(6):
        for corrupt in (False,True):
            for flips in (0,0xc00):
                uc=core();piece=bytearray(wide[part*32:(part+1)*32])
                if corrupt:piece[0]^=0x80
                uc.mem_write(0x06008200,wide[:32]);uc.mem_write(0x06008220,bytes(piece))
                uc.mem_write(0x06005900,struct.pack('<HH',0xb010,0xb011))
                uc.reg_write(UC_ARM_REG_R4,0x06005902)
                uc.reg_write(UC_ARM_REG_R6,0x02012340)
                call(uc,'UpdateUnreadPaletteBridge',17|flips)
                assert uc.reg_read(UC_ARM_REG_R0)==17|flips
                assert uc.reg_read(UC_ARM_REG_R1)==(0xd000 if corrupt else 0xe000)
                assert uc.reg_read(UC_ARM_REG_R4)==0x06005902
                assert uc.reg_read(UC_ARM_REG_R6)==0x02012340
                assert struct.unpack('<H',uc.mem_read(0x06005900,2))[0]==(0xb010 if corrupt else 0xe010)
                count+=1
    uc=core();uc.mem_write(control,b'\x02');uc.mem_write(view+21,b'\x11')
    uc.mem_write(0x06005900,struct.pack('<HH',0xb010,0xb011))
    uc.reg_write(UC_ARM_REG_R4,0x06005902);uc.reg_write(UC_ARM_REG_R6,view)
    call(uc,'UpdateUnreadPaletteBridge',17)
    assert uc.reg_read(UC_ARM_REG_R1)==0xe000
    assert struct.unpack('<H',uc.mem_read(0x06005900,2))[0]==0xe010
    count+=1
    return count


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom',type=Path);p.add_argument('--sha256',required=True)
    p.add_argument('--elf',type=Path,help='Explicit matching palette-hook ELF for wide-row boundary checks')
    args=p.parse_args()
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
    if args.elf: cases+=check_wide(rom,args.elf)
    print(f'{cases} native badge palette, row bounds and register/stack cases passed')


if __name__=='__main__':main()
