# Plugin font extensions

`plugins.json` declares plugin priority and font ownership. Font generation uses
Python's standard library; it introduces no font engine, OCR or Swift dependency.

`uscn` owns the base font and its character table at priority 1000. Every other
plugin must have a lower priority. Its 3,175 native glyphs and widths are checked
against every row of `config/charsets/us-cn-v1.1/character-table.json` before an
extension is built. Unknown labels and duplicate Unicode aliases remain in the
table. The first original token is the canonical encoding for a duplicate label;
all original tokens remain valid.

Font declarations use these modes:

- `base`: an explicit glyph table, ROM font/width offsets, glyph count and cell
  size. The highest-priority enabled base owns the original indices; this project
  requires that base to be `uscn`.
- `append`: a named style, selected Unicode characters and a transform. The
  `row_shear` transform shifts every nonzero pixel in a row by
  `max(0, baseline - y) // rows_per_pixel`, retaining its original 4bpp shade.
  It rejects clipping and expands advances when needed; it does not rescale.

Claims for the same `(style, character)` resolve by descending priority. Equal
priority is an error. Append plugins cannot claim the `default` style or replace
base cells. Allocation is deterministic: descending plugin priority, plugin ID,
then Unicode scalar. Disabling an append plugin can change other appended IDs,
so consumers must use the generated style mapping rather than hard-coded IDs.

The `info` plugin's internal italic extension appends four glyphs for `Info`. The original glyph
indices remain 0–3174; new indices begin at 3175 (`0xC67`), with native full-glyph
tokens beginning at `0x8C67`. The ordinary Unicode map retains the original codes;
`style-glyph-maps.json` and `italic-glyph-map.json` select the new italic codes.

The original font is immediately followed by its width table, so extending it
in place would overwrite other resources. The builder places a byte-identical
copy of the original font followed by the new cells and extended width table in
verified erased ROM space at `0xD00000`. It redirects the font pointer at
`0x13474` and width pointers at `0x13480` and `0x13A7C` through the official
extension API. The original font/width storage, native loader instructions and
all original text tokens stay unchanged. No runtime hook is added.

Build outputs under `font-extensions/` include the full font/width data, complete
updated glyph table, ordinary and styled Unicode maps, extension manifest and
priority/provenance report. These generated font resources stay external.
The Info entry uses the appended italic cells; its detail pages retain the
ordinary font. Native menu palette banks and the feather cursor remain in use.

The CN+Info profile enables this extension by default. `--disable-italic-font`
restores the upright Info entry. `--enable-italic-font` requires the Info plugin
and the CN base font. Explicitly enabling it without either is rejected. Exact-reference CN flags
`--disable-pinyin --disable-link-fix` leave Info and italic extensions disabled.

`tests/test_font_plugins.py` checks ownership, priority conflicts, pixel
preservation, clipping and append-only IDs. `tools/probe_font_extensions.c`
separately calls the original glyph loader in an isolated mGBA instance and
compares every copied cell and returned width, including appended indices.
Rendered title-menu replay is a separate validation step; neither establishes
physical-hardware acceptance.
