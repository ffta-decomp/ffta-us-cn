#!/usr/bin/env python3
"""Explicit-ROM native checks for presentation boundaries and queue ownership."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_PC)


def run_case(rom, mode, phase, *, linked=False, bank=0, action_state=15,
             pending=0, destroy=False, queue_command=False, wrong_group=False):
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    for at,size in ((0x08000000,len(rom)),(0x02000000,0x40000),(0x03000000,0x8000)):
        uc.mem_map(at,size)
    uc.mem_write(0x08000000,rom)
    w32=lambda a,v:uc.mem_write(a,struct.pack('<I',v))
    w16=lambda a,v:uc.mem_write(a,struct.pack('<H',v))
    r32=lambda a:struct.unpack('<I',uc.mem_read(a,4))[0]
    context,scene,graphics=0x0200f4e8,0x02018000,0x02019000
    group,list_head,node,animation,frames=0x03002710,0x0201c000,0x0201c100,0x02028000,0x02029000
    effects,root,motion,actor=0x02020000,0x02024000,0x0202b000,0x0202c000
    parent=0x02017000
    uc.mem_write(0x02002fc3,bytes([mode<<3]));w16(0x0200f424,128 if linked else 0)
    w32(0x0200f4a8,context);w32(0x0200f4b0,scene);w32(scene+8,graphics)
    w16(context+220,phase);w32(context+68,motion);w32(context+4,actor)
    w32(context+72,root);w32(context+84,root);w16(root+0x3450,action_state);w16(root+0x26c0,pending)
    w16(motion+220,6);w32(actor,0x02000080)
    w32(graphics+8,list_head);w32(list_head+4,node);w32(node,animation)
    w16(graphics+480,4);w32(graphics+484,0);w32(0x0200f430,effects)
    w32(0x02008ff0,parent);w32(0x03002828,0x08096e79)
    uc.mem_write(0x03000028,bytes([bank]))
    keys=bytes.fromhex('0102030405060708');scene_keys=b'\x09\x0a\x0b\x0c'
    uc.mem_write(0x03000000,keys);uc.mem_write(0x0200f3a4,scene_keys)
    valid_bank=bank if bank<2 else 0
    matrices=bytes((i*7)&255 for i in range(288))
    uc.mem_write(0x03003270+valid_bank*32,matrices[:32])
    uc.mem_write(0x030032b0+valid_bank*256,matrices[32:])
    w32(0x03000020+valid_bank*4,2);w32(0x03002c50+valid_bank*4,3)
    w32(animation,3);w16(animation+10,1);w16(animation+14,3)
    w32(animation+52,frames);w32(animation+56,frames)
    for i in range(3):
        frame=bytearray(20);frame[8]=2
        if queue_command:
            frame[9]=1;struct.pack_into('<I',frame,0,0x1234+i)
        else:frame[9]=8;frame[10]=i+1
        uc.mem_write(frames+i*20,bytes(frame))
    calls={'normal':0,'ticks':0,'effects':0,'action':0,'reaction':0,'motion':0}
    signals=[]
    def ret(value=0):
        uc.reg_write(UC_ARM_REG_R0,value)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    def hook(u,address,size,data):
        if address==0x08021290:
            calls['ticks']+=1
            assert u.reg_read(UC_ARM_REG_R1)==graphics+20
            assert struct.unpack('<H',u.mem_read(graphics+480,2))[0]==0
            return
        if address==0x08000adc:raise AssertionError('Intermediate sprite DMA submitted')
        if address==0x080a8940:raise AssertionError('Extra visit released native reaction owner')
        if address==0x080069f4:
            calls['normal']+=1
            assert bytes(u.mem_read(0x03000000,8))==keys
            assert bytes(u.mem_read(0x0200f3a4,4))==scene_keys
            assert r32(0x02008ff0)==parent
            assert struct.unpack('<H',u.mem_read(graphics+480,2))[0]==4
            assert r32(graphics+484)==0
            assert r32(0x03000020+valid_bank*4)==2
            assert r32(0x03002c50+valid_bank*4)==3
            assert bytes(u.mem_read(0x03003270+valid_bank*32,32))==matrices[:32]
            assert bytes(u.mem_read(0x030032b0+valid_bank*256,256))==matrices[32:]
            ret();return
        if address in (0x08005a24,0x080a8270,0x080a8958,0x0809b88c):
            assert bytes(u.mem_read(0x03000000,8))==bytes(8)
            assert bytes(u.mem_read(0x0200f3a4,4))==bytes(4)
        if address==0x08005a24:
            calls['effects']+=1;signals.append(u.mem_read(animation+30,1)[0])
            w32(0x02008ff0,0)
            w32(0x03000020+valid_bank*4,99);w32(0x03002c50+valid_bank*4,99)
            u.mem_write(0x03003270+valid_bank*32,b'\xee'*32)
            u.mem_write(0x030032b0+valid_bank*256,b'\xee'*256)
            if destroy:w32(0x0200f4a8,0)
            ret();return
        stubs={0x080a8270:'action',0x080a8958:'reaction',0x0809b88c:'motion'}
        if address in stubs:
            calls[stubs[address]]+=1;ret(1);return
        values={0x080a9588:1,0x0809d8f0:0,0x080c95a8:0,0x080c8298:0,
                0x0809d614:1,0x0809caf4:1,0x0802104c:0x0202d000,0x08021064:1}
        if address in values:ret(values[address])
    uc.hook_add(UC_HOOK_CODE,hook)
    uc.reg_write(UC_ARM_REG_R0,group+16 if wrong_group else group)
    uc.reg_write(UC_ARM_REG_R1,9)
    uc.reg_write(UC_ARM_REG_SP,0x03007e00);uc.reg_write(UC_ARM_REG_LR,0x03007f01)
    uc.emu_start(0x0836d3b9,0x03007f00,count=300000)
    assert uc.reg_read(UC_ARM_REG_SP)==0x03007e00
    active=mode and not linked and bank<2 and not wrong_group and phase in (43,60,67)
    if phase==60 and (action_state in (0,14,36) or pending&7):active=False
    expected=(1 if destroy else (1<<mode)-1) if active else 0
    assert calls['normal']==1
    assert calls['ticks']==calls['effects']==expected,(mode,phase,calls,expected)
    assert calls['motion']==(expected if phase==43 else 0)
    assert calls['action']==(expected if phase==60 else 0)
    assert calls['reaction']==(expected if phase==67 and not destroy else 0)
    return calls


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom',type=Path);p.add_argument('--sha256',required=True)
    args=p.parse_args();rom=args.rom.read_bytes()
    assert len(rom)==0x1000000 and hashlib.sha256(rom).hexdigest()==args.sha256
    cases=0
    for mode in range(4):
        for phase in range(127):run_case(rom,mode,phase);cases+=1
    for mode in (1,2,3):
        for phase in (43,60,67):
            for kw in ({'linked':True},{'bank':1},{'bank':2},{'wrong_group':True},
                       {'destroy':True},{'queue_command':True}):
                run_case(rom,mode,phase,**kw);cases+=1
        for state in (0,14,36):run_case(rom,mode,60,action_state=state);cases+=1
        for pending in (1,2,4):run_case(rom,mode,60,pending=pending);cases+=1
    print(json.dumps(dict(rom_sha256=args.sha256,native_cases=cases,
        selectors_checked=127,input_and_context_restored=True,intermediate_dma=False,
        extra_oam_discarded=True,linked_guard=True)))
if __name__=='__main__':main()
