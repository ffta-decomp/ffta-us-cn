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
.section .note.GNU-stack,"",%progbits
