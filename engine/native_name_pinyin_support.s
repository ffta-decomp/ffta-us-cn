/* Freestanding Thumb-1 ABI support for the optional adapter. Only small
 * nonnegative grid coordinates reach division here (divisors six and ten).
 * EABI returns quotient in R0 and remainder in R1. */
.syntax unified
.cpu arm7tdmi
.thumb
.section .text.__aeabi_uidivmod,"ax",%progbits
.global __aeabi_uidivmod
.type __aeabi_uidivmod,%function
.thumb_func
__aeabi_uidivmod:
    movs r2, #0
    cmp r1, #0
    beq .Lzero
.Ldivide:
    cmp r0, r1
    blo .Ldone
    subs r0, r0, r1
    adds r2, #1
    b .Ldivide
.Ldone:
    movs r1, r0
    movs r0, r2
    bx lr
.Lzero:
    movs r1, r0
    movs r0, #0
    bx lr
.size __aeabi_uidivmod, .-__aeabi_uidivmod
.global __aeabi_uidiv
.thumb_set __aeabi_uidiv, __aeabi_uidivmod

/* Explicitly reserved padding in the exact CN layout. No function body or
 * asset is displaced. The A440 call site keeps editor+2F6 in R5. */
.section .pinyin_tabs_bridge,"ax",%progbits
.thumb_func
.global PinyinTabsBridge
PinyinTabsBridge:
.ifndef CJK_SOURCE_EXTENSIONS
    movs r0, r5
.endif
    ldr r3, =NativePinyinTabs
    bx r3
    .ltorg

.section .pinyin_cursor_bridge,"ax",%progbits
.thumb_func
.global PinyinCursorBridge
PinyinCursorBridge:
    ldr r3, =NativePinyinCursor
    bx r3
    .ltorg
.section .note.GNU-stack,"",%progbits
