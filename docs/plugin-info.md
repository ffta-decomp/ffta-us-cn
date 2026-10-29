# Optional title Plugin Info

The title source extension places `Info` to the right of the native color-mode
item. Up/down retain the three original menu rows; left/right select between
color mode and Info on the last row. A/Start opens Info. The native color-mode
submenu and original game confirmations retain their existing implementation.

The detail screen has a blue background, white text and two white rounded
frames. The left sidebar selects enabled plugins and the right panel shows
content. Up/down, left/right or L/R change plugins; B closes the panel and returns to Info. A advances
through additional content pages when automatic wrapping needs more than four
lines. Explicit newlines and normal spaces remain distinct.

`plugins.json` is public display metadata. `feature` selects a build flag;
`name` is the sidebar label and `content` is a JSON string using `\n` for actual
line breaks. Unknown feature names, duplicate IDs and unsupported controls fail
validation. No game text, glyph map or font data belongs in this catalogue.

The main build enables Info with the normal pinyin/link-fix profile. Use
`--disable-info` to remove it independently. The exact-reference flags
`--disable-pinyin --disable-link-fix` also leave Info disabled by default;
`--enable-info` can explicitly select a CN-only Info build. `--disable-cjk`
without explicit extensions remains the exact English baseline.

Info needs the explicit native Hanzi map and provenance report, including all
characters used in enabled plugin descriptions. It reads the original native
font cells and widths and fails on missing labels. Latin/digit ranges retain
the native full-glyph token semantics. For English plus the link fix, Info's
Chinese display font also requires an explicit CN pack; `--disable-info` keeps
the English/link-only build independent of that pack.

The official extension API selects one complete title source replacement and a
new payload at verified erased ROM space `0xC00000`. There are no instruction
hooks in the original title handler. Its 12-byte state is appended to the
original task-owned allocation and freed with the title task. The original
color-mode handler, labels, cursor and transitions are reused. The 1D OBJ payload
uses tiles 384–1023; the pinned title graphics upload ends below tile 384.
All generated glyph graphics, source bindings, compiler reports, ROMs and test
captures remain outside the source tree. This optional UI earns no decomp
matching credit.

Info currently copies a mode-dependent native palette into its owned OBJ
palette slot, using blue index 6 and white index 4. Visual parity with the
original menu is still unresolved; the palette source has not been established
as the original window palette. The detail panels, sidebar and text are
pre-rendered glyph graphics, rather than native window/text widgets.
It saves and disables
the title window masks for the modal view and restores them on return; this
prevents the title background from showing through the four screen corners.

The complete panel graphics, including text and frames, are semi-transparent through native OBJ alpha blending
(12/16 panel plus 4/16 background). A separate footer below the white frames
reads `B: Close`. Native display/window and blending registers are
restored together when the modal view closes.
