/* Optional US Chinese engine extensions. Fixed-address assembly recovery.
 * Resource tables/payloads are generated separately. No embedded opcode blobs.
 * Thumb override uses the original 0x08005318 stack frame and returns directly
 * to its caller. It is not an independently callable C ABI function.
 */
.syntax unified
.cpu arm7tdmi

.section .text.uscn_copy, "ax", %progbits
.thumb
.balign 2
.global UsCn_copy
.thumb_func
UsCn_copy:
    push {r4, r5, r6, r7, lr}
    mov r7, sl
    mov r6, sb
    mov r5, r8
    push {r5, r6, r7}
    sub sp, #8
    ldrh r7, [r1]
    str r7, [sp]
    adds r1, #4
    mov r8, r8
.Lcopy_083b4234:
    ldm r1!, {r4}
    stm r0!, {r4}
    subs r7, #4
    cmp r7, #0
    beq .Lcopy_083b4250
    b .Lcopy_083b4234
    .space 16, 0 /* Reserved padding, not executable instructions. */
.Lcopy_083b4250:
    ldr r0, [sp]
    add sp, #8
    pop {r3, r4, r5}
    mov r8, r3
    mov sb, r4
    mov sl, r5
    pop {r4, r5, r6, r7}
    pop {r1}
    bx r1

.section .text.uscn_override, "ax", %progbits
.thumb
.balign 4
.global UsCn_override
.thumb_func
UsCn_override:
    ldr r3, [pc, #0x5c]
    cmp r3, r5
    beq .Loverride_083b4290
    ldr r3, [pc, #0x5c]
    cmp r3, r5
    beq .Loverride_083b42b4
    ldr r3, [pc, #0x58]
    cmp r3, r5
    beq .Loverride_083b42b8
.Loverride_083b4282:
    movs r0, #0
    pop {r3}
    mov r8, r3
    pop {r4, r5, r6, r7}
    pop {r1}
    bx r1
    mov r8, r8
.Loverride_083b4290:
    ldr r3, [pc, #0x4c]
.Loverride_083b4292:
    ldrh r4, [r3]
    cmp r4, r1
    beq .Loverride_083b42a2
    adds r3, #8
    ldrb r4, [r3]
    cmp r4, #0xff
    beq .Loverride_083b4282
    b .Loverride_083b4292
.Loverride_083b42a2:
    ldr r0, [r0]
    ldrh r7, [r3, #2]
    ldr r4, [r3, #4]
.Loverride_083b42a8:
    ldm r4!, {r6}
    stm r0!, {r6}
    subs r7, #4
    cmp r7, #0
    beq .Loverride_083b4282
    b .Loverride_083b42a8
.Loverride_083b42b4:
    ldr r3, [pc, #0x68]
    b .Loverride_083b4292
.Loverride_083b42b8:
    ldr r3, [pc, #0x194]
    b .Loverride_083b4292
    .space 20, 0 /* Reserved padding before identity literals. */
    .word 0x083ACD68 /* Original resource identity A. */
    .word 0x083AB42C /* Original resource identity B. */
    .word 0x083C1834 /* Original resource identity C. */
/* PC-relative loads also refer to separately generated pointer words at
 * 0x083B42E0,0x083B4320,0x083B4450. Keep those address contracts. */

.section .text.uscn_startup, "ax", %progbits
.arm
.balign 4
.global UsCn_startup

UsCn_startup:
    bl .Lstartup_08a7fce0
    ldr r1, [pc, #0x134]
    ldr r0, [pc, #0x134]
    strt r1, [r0], #0
    ldr r1, [pc, #0x130]
    ldr r0, [pc, #0x130]
    strt r1, [r0], #0
    ldr r1, [pc, #0x12c]
    ldr r0, [pc, #0x12c]
    strt r1, [r0], #0
    ldr r1, [pc, #0x128]
    ldr r2, [pc, #0x128]
    strt r2, [r1], #0
    ldr r3, [pc, #0x124]
    bl .Lstartup_08a7fcf0
    bl .Lstartup_08a7fcd0
    mov sl, #2
.Lstartup_08a7fc44:
    sub sl, sl, #1
    ldr r1, [pc, #0x114]
    cmp sl, r1
    beq .Lstartup_08a7fc70
    ldr r1, [pc, #0xfc]
    strt sl, [r1], #0
    ldr r2, [pc, #0x104]
.Lstartup_08a7fc60:
    bl .Lstartup_08a7fd2c
    subs r2, r2, #1
    bne .Lstartup_08a7fc60
    b .Lstartup_08a7fc44
.Lstartup_08a7fc70:
    ldr r3, [pc, #0xf4]
    bl .Lstartup_08a7fd00
    bl .Lstartup_08a7fd18
.Lstartup_08a7fc7c:
    ldr r1, [pc, #0xec]
    ldrh r3, [r1], #0
    mov r4, #2
    cmp r3, r4
    ble .Lstartup_08a7fc7c
    ldr r3, [pc, #0xdc]
    bl .Lstartup_08a7fcf0
    ldr sl, [pc, #0xc4]
.Lstartup_08a7fc9c:
    add sl, sl, #1
    ldr r1, [pc, #0xb4]
    cmp sl, r1
    beq .Lstartup_08a7fcc8
    ldr r1, [pc, #0xa4]
    strt sl, [r1], #0
    ldr r2, [pc, #0xac]
.Lstartup_08a7fcb8:
    bl .Lstartup_08a7fd2c
    subs r2, r2, #1
    bne .Lstartup_08a7fcb8
    b .Lstartup_08a7fc9c
.Lstartup_08a7fcc8:
    bl .Lstartup_08a7fce0
    b .Lstartup_08a7fda0
.Lstartup_08a7fcd0:
    ldr r1, [pc, #0xa0]
    ldr r2, [pc, #0xa0]
    strt r2, [r1], #0
    mov pc, lr
.Lstartup_08a7fce0:
    ldr r1, [pc, #0x90]
    ldr r2, [pc, #0x78]
    strt r2, [r1], #0
    mov pc, lr
.Lstartup_08a7fcf0:
    ldr r1, [pc, #0x88]
    mov r2, r3
    strt r2, [r1], #0
    mov pc, lr
.Lstartup_08a7fd00:
    ldr r0, [pc, #0x7c]
    ldr r1, [pc, #0x7c]
    add r1, r1, r3
    lsl r2, r1, #0x10
    strt r2, [r0], #0
    mov pc, lr
.Lstartup_08a7fd18:
    ldr r0, [pc, #0x6c]
    ldr r1, [pc, #0x6c]
    lsl r2, r1, #0x10
    strt r2, [r0], #0
    mov pc, lr
.Lstartup_08a7fd2c:
    ldr sb, [pc, #0x60]
.Lstartup_08a7fd30:
    ldrh r0, [sb], #0
    cmp r0, #0x80
    bne .Lstartup_08a7fd30
    mov pc, lr
/* Literal pool: source, DMA/display/timer addresses and constants. */
    .word 0x08A6D000 /* CPU 08A7FD40 */
    .word 0x040000D4 /* CPU 08A7FD44 */
    .word 0x06000000 /* CPU 08A7FD48 */
    .word 0x040000D8 /* CPU 08A7FD4C */
    .word 0x84004B00 /* CPU 08A7FD50 */
    .word 0x040000DC /* CPU 08A7FD54 */
    .word 0x04000054 /* CPU 08A7FD58 */
    .word 0x00000010 /* CPU 08A7FD5C */
    .word 0x000004C4 /* CPU 08A7FD60 */
    .word 0x00000000 /* CPU 08A7FD64 */
    .word 0x00000078 /* CPU 08A7FD68 */
    .word 0x00000002 /* CPU 08A7FD6C */
    .word 0x0400010C /* CPU 08A7FD70 */
    .word 0x00000484 /* CPU 08A7FD74 */
    .word 0x04000000 /* CPU 08A7FD78 */
    .word 0x00000403 /* CPU 08A7FD7C */
    .word 0x04000050 /* CPU 08A7FD80 */
    .word 0x0400010A /* CPU 08A7FD84 */
    .word 0x00000080 /* CPU 08A7FD88 */
    .word 0x0400010E /* CPU 08A7FD8C */
    .word 0x00000087 /* CPU 08A7FD90 */
    .word 0x04000006 /* CPU 08A7FD94 */
    .word 0xFFFFFFFF, 0xFFFFFFFF /* Reserved erased-ROM padding. */
.Lstartup_08a7fda0:
    ldmia sp!, {r1}
    bx r1
.global UsCn_startup_entry
UsCn_startup_entry:
    stmdb sp!, {r1}
    b UsCn_startup
