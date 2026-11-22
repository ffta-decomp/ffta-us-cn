.syntax unified
.cpu arm7tdmi
.thumb
.section .text,"ax",%progbits
.align 2
.global NativeQuery
.thumb_func
NativeQuery:
 push {r4,r5,r6,lr}
 lsls r0,r0,#24
 lsrs r0,r0,#24
 movs r5,r0
 ldr r3, 3f
 bx r3
.align 2
3: .word 0x080094c5
.section .bridge,"ax",%progbits
.align 2
.global ListCountBridge
.thumb_func
ListCountBridge:
 ldr r0, 4f
 ldrb r0, [r0]
 strh r0, [r5, #24]
 movs r0,#0
 strh r0, [r5, #26]
 bx lr
.align 2
4: .word CommonOptionCount
.global ReadDisplayedOptionBridge
.thumb_func
ReadDisplayedOptionBridge:
 ldr r3, 5f
 bx r3
5: .word CommonReadDisplayedOption
.section .note.GNU-stack,"",%progbits
