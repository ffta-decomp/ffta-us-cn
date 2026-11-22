# Shared native Options

This module extends the in-game System / Options list once for all enabled
plugins. It retains the original ten rows, scrolling, confirmation dialog and
normal save path. New switches appear before the final Reset row, while native option IDs remain unchanged. Plugins export an `options` descriptor through `plugins.json`;
they do not implement another menu or write Flash themselves.

Descriptors use schema `ffta-common-options-v1`, storage byte 3, and stable bit
assignments 0–7. Each row declares an ID, starting bit, native-font label and hint.
An optional `width` reserves up to three adjacent bits; `values` then supplies
every stored value. Labels, hints and values can use language maps with `en` and
`zh-Hans` entries. Native Latin tokens work without the Chinese font or pack.
Duplicate
bits, unknown glyphs and unsupported descriptors fail the build. Bit assignments
must never depend on plugin order. Gameplay reads `CommonOptionEnabled(bit)` from
`options.h`; multibit modes use `CommonOptionValue(bit, width)`. Unassigned bits
survive individual changes. The core is installed once whenever any build needs it.
The build rejects ranges outside the eight-bit saved byte, overlapping ranges,
and value lists that do not match their reserved width. Its report lists the
capacity, occupied bits and remaining bits; the generated C also asserts that
the combined mask fits one byte. The native value row supports at most eight
choices, so one option may reserve at most three bits.

The native settings record remains four bytes at save offset `0x2FC0`. Its unused
fourth byte holds opt-in flags; existing saves with a zero byte keep every new
option off. The native reset row clears these flags with the other settings.
Exiting Options only commits to live game state; the player must still perform
an ordinary game save to persist it. No SAV extension or save-capacity change is
introduced by this module.

The original Options context contains text immediately after its ten cells.
Additional cells therefore live in a separately allocated context tail, not in
that text buffer. The two pinned native constructor callers select their own
active pool (world menu or modal menu); the context records its owning pool and
is freed on exit. Original cells, labels, definitions and hints are redirected
through authenticated ROM hooks. No fixed scratch RAM is claimed.

Emulator and direct ARM tests are separate from real hardware acceptance.
