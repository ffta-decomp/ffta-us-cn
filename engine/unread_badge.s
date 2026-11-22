.syntax unified
.cpu arm7tdmi
.thumb
.section .bridge,"ax",%progbits
.balign 4
.global UnreadBadgePaletteBridge
.thumb_func
UnreadBadgePaletteBridge:
    push {r0-r5,r7,lr}
    ldr r3, 1f
    bl 2f
    movs r6,r0
    pop {r0-r5,r7}
    pop {pc}
.balign 4
1: .word UnreadBadgePalette
.thumb_func
2: bx r3
.section .note.GNU-stack,"",%progbits
