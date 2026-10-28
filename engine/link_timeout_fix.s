/* US AFXE serial-session poll, ROM 0x004D78 / CPU 0x08004D78.
 * Keep the original unsigned BLS and the rest of the function unchanged.
 * R1 is the byte counter loaded from 0x03002B60, not an invented input.
 * The original instruction is cmp r1, #0x46 (little-endian 46 29).
 */
.syntax unified
.cpu arm7tdmi
.thumb
.section .text, "ax", %progbits
.global CnLinkTimeoutComparison
.type CnLinkTimeoutComparison, %function
.thumb_func
CnLinkTimeoutComparison:
    cmp r1, #0xfe
.size CnLinkTimeoutComparison, .-CnLinkTimeoutComparison
