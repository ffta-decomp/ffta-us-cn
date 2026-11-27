/* Reserve near-call space for all plugins; keep recruit implementations far. */
.syntax unified
.cpu arm7tdmi
.thumb
.section .bridge,"ax",%progbits
.macro BRIDGE name, target
 .balign 4
 .global \name
 .thumb_func
\name:
 ldr r3, 1f
 bx r3
1: .word \target
.endm
BRIDGE RenderNameBridge, RenderNameFar
BRIDGE AcceptBridge, AcceptFar
.balign 4
.global DialogBridge
.thumb_func
DialogBridge:
 mov ip, r3
 ldr r3, 2f
 bx r3
 nop
2: .word DialogRestoreR3
BRIDGE IdentifyRecruitFlash, IdentifyRecruitFlashFar
BRIDGE LoadBridge, LoadFar
BRIDGE SaveBridge, SaveFar
.section .opening_bridge,"ax",%progbits
BRIDGE ClanNameBridge, ClanNameFar
.section .commit_bridge,"ax",%progbits
BRIDGE NameCommitBridge, ProgramWithNames
.text
.balign 2
.global OriginalSave
.thumb_func
OriginalSave:
 push {r4-r7, lr}
 mov r7, r10
 mov r6, r9
 mov r5, r8
 ldr r3, =0x0813b0dd
 bx r3
 .ltorg
.thumb_func
ProgramWithNames:
 push {r0-r2, lr}
 bl PrepareNameSector
 cmp r0, #0
 pop {r0-r3}
 bne 3f
 mov lr, r3
 bx r2
3:
 /* Scan sector state and unwind through the native write failure path.
  * The caller spills its loop index before this hook. */
 ldr r3, =0x0813b41b
 bx r3
 .ltorg
.section .note.GNU-stack,"",%progbits
