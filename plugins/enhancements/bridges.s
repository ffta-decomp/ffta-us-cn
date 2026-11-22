.syntax unified
.cpu arm7tdmi
.thumb
.section .text,"ax",%progbits
.align 2
.global ShopFar
.thumb_func
ShopFar:
 push {r4,lr}
 ldr r3, 5f
 bl CallR3
 pop {r4,pc}
.align 2
5: .word EnhancedShop
.global GrowthFar
.thumb_func
GrowthFar:
 pop {r3}
 push {r2,r3,r4,lr}
 movs r0,r1
 ldr r3, 6f
 bl CallR3
 movs r1,r0
 pop {r2,r3,r4}
 pop {r0}
 adds r0,#10
 bx r0
.align 2
6: .word EnhancedGrowth
CallR3:
 bx r3
.global PartyAPFar
.thumb_func
PartyAPFar:
 push {r0,r1,r2,r3,r4,lr}
 ldr r3, 7f
 bl CallR3
 pop {r0,r1,r2,r3,r4}
 pop {r3}
 mov lr,r3
 /* Original target consumes the caller's controller stack, not a C frame. */
 ldr r3, 8f
 bx r3
.align 2
7: .word EnhancedPartyAP
8: .word 0x08049a11
.section .bridge,"ax",%progbits
.align 2
.global ShopBridge
.thumb_func
ShopBridge:
 ldr r3, 9f
 bx r3
9: .word ShopFar
.global GrowthBridge
.thumb_func
GrowthBridge:
 /* GrowthFar saves R3 before the far target literal can clobber it. */
 push {r3}
 ldr r3, 10f
 bx r3
.align 2
10: .word GrowthFar
.global PartyAPBridge
.thumb_func
PartyAPBridge:
 ldr r3, 11f
 bx r3
11: .word PartyAPFar
.section .note.GNU-stack,"",%progbits
