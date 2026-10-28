# Serial counter timeout extension

The supplied communication-fix instructions describe raising a byte-counter
limit from `0x46` (70) to `0xFE` (254). Both authenticated 16 MiB US and Chinese
inputs have the same original serial poll at CPU entry `0x08004D69` (Thumb),
ROM `0x004D68` through `0x004E0D`. This function is retained original ASM in
the current decomp source; it has no published completed C replacement.

There is an important address/encoding correction for these specific inputs:

| Item | ROM offset | CPU instruction address | Bytes, in file order |
| --- | --- | --- | --- |
| Function prologue, `push {r4,r5,lr}` | `0x004D68` | `0x08004D68` | `30 B5` |
| Original `cmp r1,#0x46` | `0x004D78` | `0x08004D78` | `46 29` |
| Replacement `cmp r1,#0xFE` | `0x004D78` | `0x08004D78` | `FE 29` |
| Unchanged unsigned `bls 0x08004D88` | `0x004D7A` | `0x08004D7A` | `05 D9` |

The cited `46 26` / `FE 26` encode `MOVS R6`, not `CMP`, on these inputs.
Do not blindly write them at the function entry. This project authenticates
the input, complete 166-byte function, original CMP/BLS and assembled result.
Only one byte changes within the two-byte comparison instruction.

`engine/link_timeout_fix.s` expresses the replacement as a readable Thumb
instruction. `tools/link_timeout_fix.py` assembles it externally and supplies a
source-pinned code fragment to the official build extension API. No vendor
source is modified. The original function, branches, stack, register behavior
and literals remain in place. This is a small ASM extension, not whole-function
C recovery, and earns no decomp recovery credit.

The function reads the counter at `0x03002B60` into R1. An unsigned counter
greater than the selected maximum returns zero before the original poll body.
The original accepts `0..70`; the fix accepts `0..254`, leaving only `255` on
that early-return path. Stable sampled state increments the byte counter;
changed state resets it. The existing status writes and phase toggle remain.
These observations establish counter behavior, not a measured 254-frame timeout
or a new implementation of the GBA GP communication protocol.

CN builds enable the fix by default. `--disable-link-fix` restores the original
comparison; combine it with `--disable-pinyin` for byte-identical original CN.
`--disable-cjk` keeps an exact English baseline unless `--enable-link-fix` is
explicitly selected. The feature report records the final image hash, source
pins, offsets, instruction bytes and selected limit.

## Verification

Unit tests check original-function/overlap refusals and actual ARM-binutils
assembly. Clean ROM comparisons must show exactly the one-byte delta at
`0x004D78` between otherwise identical fix-off and fix-on profiles.

`tools/probe_link_timeout.c` directly executes the complete poll function in
mGBA for all 256 counters, both status-selection paths, both phase values and
stable/changed sampled state: 2,048 cases per ROM. It checks the return, counter,
phase, previous state, preserved R4/R5 and SP. Build it against an explicitly
selected mGBA source/header and matching library, then run:

```sh
probe_link_timeout "$ORIGINAL_CN_ROM" 70
probe_link_timeout "$FIXED_CN_ROM" 254
```

This does not test a real linked battle between two emulator instances or
physical consoles. Both players must use the same built ROM and feature
selection; compare the complete SHA-256 before a linked-session test. End-to-end
multiplayer compatibility remains unverified until that separate test passes.
