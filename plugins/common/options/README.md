# Shared native Options

This module extends the in-game System / Options list once for all enabled
plugins. It retains the original ten rows, scrolling, confirmation dialog and
normal save path. New switches appear before the final Reset row, while native option IDs remain unchanged. Plugins export an `options` descriptor through `plugins.json`;
they do not implement another menu or write Flash themselves.

Descriptors use schema `ffta-common-options-v1`, storage byte 3, and stable bit
assignments 0–7. Each row declares an ID, bit, native-font label and hint. Duplicate
bits, unknown glyphs and unsupported descriptors fail the build. Bit assignments
must never depend on plugin order. Gameplay reads `CommonOptionEnabled(bit)` from
`options.h`. Unassigned bits survive individual toggles.

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
