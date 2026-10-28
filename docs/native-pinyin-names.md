# Optional native pinyin naming

The pinyin core and host UI model live in this project under `engine/pinyin/`.
The native adapter connects them to the primary and secondary name editors.
Pinyin defaults on in this project and is disabled with `--disable-pinyin`; it
does not change the official decomp project's default manifest.

The original two `Aa` / `123` tab resources, palettes, positions and selected-tab
renderer remain intact. Pinyin replaces native keyboard page zero, selected by
the first tab, and is ready when the editor opens. The second tab keeps its
original native character page. There is no third tab, overlay, extra OBJ VRAM
reservation or temporary palette.

The pinyin page has 26 letter cells and up to 30 candidate cells. Its six rows
use 14-pixel spacing, followed by a separate spelling strip at screen
`y=116..127`, with a simple `> ` prefix. The committed name stays in the
original panel at `y=136`.
The builder checks that all admitted glyphs have empty source rows 14 and 15
before allowing this layout. It neither scales nor modifies font cells.

Controls:

- L/R switches between pinyin on page zero and the original second page.
  A pending spelling is retained when switching away and back.
- D-pad selects a letter or an existing candidate; A accepts it.
- B removes the last pending letter first. Only an empty composition lets B
  delete a committed name character.
- SELECT advances through 30-candidate pages and wraps at the end.
- Impossible next letters are rejected without changing the buffer. Valid
  prefixes have candidates from their possible continuations, so `m` can
  still become `ma`. Exact syllables keep their original candidate order.
- START and Yes/No use the original confirmation and name-publication paths.
  Candidate commit uses the original eight-token limit, ninth scratch cell,
  and 87-pixel width check, rather than a replacement name writer.

## Installed-glyph map and build

Private inputs and generated files below must be external. No glyph map, font,
ROM, extracted text, replay or capture belongs in Git. Only the separately
licensed, hash-pinned Rime dictionary and its license are vendored.

The conservative map matches exact shade-3 foreground stroke coordinates,
allowing only bounding-box translation, between the pinned local Bear large
font and the installed US Chinese font. Unicode labels come from the pinned
forward charset. Ambiguous shapes, duplicate labels, and duplicate target
cells are excluded. The resulting map has 2,214 Hanzi, all with pinned Rime
readings. This is not full 128-byte cell equality or a claim of independent
manual verification of every Unicode label. The map report records this limit.
No candidate introduces a new font cell or changes a native glyph code.

Run from this project root. The pinned vendor dependency provides generic
codecs; this project owns the pinyin core. To derive local inputs, run:

```sh
python3 tools/map_native_pinyin_glyphs.py \
  --translated "$CN_ROM" \
  --source-font "$BEAR_LARGE/font-4bpp.bin" \
  --source-charset "$BEAR_LARGE/source-charset.json" \
  --output-dir "$EXTERNAL/glyph-map"

python3 tools/build.py \
  --retail "$US_ROM" --pack-dir "$EXACT_CN_PACK" \
  --glyph-map "$EXTERNAL/glyph-map/glyph-map.json" \
  --map-report "$EXTERNAL/glyph-map/map-report.json" \
  --output-dir "$EXTERNAL/pinyin-build" \
  --tool-prefix arm-none-eabi-
```

The dictionary and adjacent Apache-2.0 license are hash-pinned by the existing
generator. The build first reconstructs and authenticates the exact Chinese
baseline, then compiles the optional adapter with Clang for ARM7TDMI Thumb-1.
It rejects static RAM sections, changed hook identities, candidates outside
the installed font, and code that does not fit the verified erased ROM area.
The result remains 16 MiB. Generated tables, coverage and build reports are
written in the external output directory; the final ROM is `ffta-us-cn.gba`.

The feature-enabled ROM intentionally differs from the supplied Chinese ROM.
Use `tools/build.py --disable-pinyin --disable-link-fix` for byte-identical
Chinese-reference output, or `--disable-cjk` for byte-identical US retail. See the README for
complete commands and [exact import details](us-cn-exact-build.md).

## Native lifecycle and temporary patch boundary

Both original constructors, `0812B208` and `0812B230`, select the same editor
callback. The source extensions increase their task-owned work from `0x334`
to `0x3A0`, keep the original context/mode halfword and select the callback and
cursor through complete C module replacements. The nearby Thumb cursor bridge
occupies authenticated padding; the new code and table occupy erased storage
at ROM `B00000`, without ROM
expansion. The assembly is local to this CJK subproject and earns no decomp
matching credit. Replace these fixed-revision bridges with typed engine hooks
when the main engine integration is ready.

Both native page caches are prepared by the original open sequence. Before
native event `0x102` copies page zero to VRAM, the adapter replaces only that
page's 120-byte token cache and `0x2100`-byte graphics cache. The original
second-page caches remain untouched. Rendering uses the existing scratch area
inside the task-owned buffer. Native name tokens remain big-endian byte pairs;
no page index beyond zero or one is used.

On later input and page changes, the original keyboard uploader and original
selected-tab resource uploader are used. The first tab therefore regains its
own label/frame when switching back. No custom tab rendering is called, and
the original 236-byte sprite-layout C module remains byte-identical to retail.

The native upload allocator has only three 28-byte descriptors. The initial
pinyin render only prepares RAM; the original open path performs its existing
uploads. During editing, a native name redraw plus keyboard and selected-tab
uploads uses at most three slots. Each added upload checks this limit. No
additional header allocation or VRAM/palette backup/restore lifecycle exists.

## Validation boundary

The local acceptance run checks actual keypad input in mGBA: composition,
backspace, impossible-prefix rejection, six-letter display, candidate paging
and wrap, two-page switching, original second-page input, width rejection,
primary-name confirmation and return to the story. The primary test commits a name different from the
default. Original tab-label regions are compared pixel-for-pixel against the
native renderer, including switching back to the first tab. The old third-tab
bridge storage remains unchanged, and two clean builds must produce the same ROM.

`tools/probe_native_pinyin.c` is a separate host test driver linked to mGBA.
Its input language supports `key HEX`, `spell LETTERS`, `candidate INDEX`,
`clear`, `expect-spelling`, `expect-name`, `expect-global`, `capture`, and `wait`.
ROM, same-ROM savestate, action file, and output directory are explicit inputs.
`secondary-context-fixture` exercises the original secondary/clan mode and
publication target by changing the existing mode halfword; it is explicitly
not proof of navigating to clan naming through the story. Flash-save/reload
and physical hardware remain separate acceptance gates.

The former direct ROM-patch adapter remains an explicit compatibility tool. The
current `tools/build.py` compiles existing decomp entries and selects this
project's C source extensions through the official upstream extension API.
