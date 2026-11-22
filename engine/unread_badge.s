.syntax unified
.cpu arm7tdmi
.thumb
.section .bridge,"ax",%progbits
.balign 4
.global UnreadBadgePaletteBridge
.thumb_func
UnreadBadgePaletteBridge:
    push {r0-r5,r7,lr}
    movs r1,r4
    ldr r3, 1f
    bl 2f
    movs r6,r0
    pop {r0-r5,r7}
    pop {pc}
.balign 4
1: .word UnreadBadgePalette
.thumb_func
2: bx r3
.balign 4
.global ConfigureWideUnreadBridge
.thumb_func
ConfigureWideUnreadBridge:
    ldr r3, 3f
    bx r3
3: .word ConfigureWideUnreadView
.balign 4
.global FinishWideUnreadBridge
.thumb_func
FinishWideUnreadBridge:
    ldr r3, 4f
    bx r3
4: .word FinishWideUnreadRow
.balign 4
.global WideUnreadScrollbarBridge
.thumb_func
WideUnreadScrollbarBridge:
    push {r4,lr}
    ldr r4, 5f
    bl 6f
    pop {r4,pc}
.balign 4
5: .word ConfigureWideUnreadScrollbar
.thumb_func
6: bx r4
.balign 4
.global UpdateUnreadPaletteBridge
.thumb_func
UpdateUnreadPaletteBridge:
    push {r0,r2-r7,lr}
    movs r1,r4
    movs r2,r6
    ldr r3, 7f
    bl 8f
    movs r1,r0
    pop {r0,r2-r7}
    pop {pc}
.balign 4
7: .word SelectedUnreadPalette
.thumb_func
8: bx r3
.section .note.GNU-stack,"",%progbits
