# Optional upstream localization resources

`config/optional-localization-sources.json` registers
[BSoD123456/ffta_us_cn](https://github.com/BSoD123456/ffta_us_cn) at
`cd32ebce88bb26cae030115d5538c1d01a0772f3`. The external checkout supplies
translation additions and corrections, charset provenance, and the bundled
BoutiqueBitmap9x9 1.7 font. It is not a complete standalone Chinese script:
the upstream workflow obtains most existing translated story text from a
separately supplied Chinese ROM. The English retail reference remains fixed.

## Conversion

Use external paths for all inputs and output; output must be empty. The
converter rejects unreviewed revisions and modified upstream input files.
It does not execute upstream Python or alter a ROM.

```sh
git clone https://github.com/BSoD123456/ffta_us_cn.git "$UPSTREAM"
git -C "$UPSTREAM" checkout cd32ebce88bb26cae030115d5538c1d01a0772f3
uv run --no-project --with pillow==11.3.0 --with fonttools==4.60.1 \
  python tools/convert_ffta_us_cn.py \
  --upstream "$UPSTREAM" --assets-dir "$ASSETS" \
  --output-dir "$OUTPUT" --generate-font
python3 tools/test_convert_ffta_us_cn.py
```

`ASSETS` is an extraction of the identified US retail ROM. Without
`--generate-font`, conversion requires only the Python standard library.

| Output | Purpose |
| --- | --- |
| `localized-text.json` | Existing full-glyph/control token schema, original text, target offsets and expected hashes, per-entry binding and integration gates |
| `text-streams.bin` | Standard-encoded streams indexed by payload offset/size; checked with the existing serializer and decoder |
| `charset.json` | Deterministic temporary Unicode mapping; retain retail symbols below 0x122 and allocate selected remaining characters |
| `font-4bpp.bin`, `font-atlas.pgm` | Compact glyph payload and existing 16x16, 128-byte tile/PGM representation, verified by font_codec round trip |
| `font.json` | Explicit game-code-to-payload-offset mapping, missing glyphs, pixel roles, unverified advance status |
| `report.json` | Pinned source hashes, conversion counts, binding counts and evidence limits |
| `UPSTREAM-LICENSE.txt`, `font-notices.json` | Upstream repository license and the actual bundled font's embedded notices |

Commented and placeholder rows are excluded. `trans_fix_txt.json` takes
precedence over the corresponding translation addition. Control parameters,
embedded choice terminators, names and variables remain typed tokens.
Unknown controls, unmapped characters and premature terminators block the
record rather than silently removing data. Source binding compares token
identities, normalizing only full/half glyph representation. Nested scene
page indices are retained.

The adapter standardizes text encoding; it does not reuse old alternate-mode
flags or compression metadata. It is a localization intermediate format,
not a replacement `scene-text-pages.json` or a ROM patch. Code assignments
can overlap untranslated retail glyphs: a dedicated localization linker must
resolve text inventories, flags, compression, pointer relocation, capacity,
and font advances before integration. Every entry remains explicitly marked
`integration_ready: false`. Missing glyphs also block affected records.

## Font appearance and provenance

The optional renderer uses the bundled face at size 10 and placement matching
the upstream generator's `(0, 1)` offset plus its internal one-pixel margin.
It applies eight-neighbor outline index 1, then right/right-down shadow index
2, then stroke index 3. Transparent pixels remain 0. This reproduces the
upstream decoration recipe; it does not justify changing the separate
Fusion Pixel demo's font size or claiming exact retail glyph geometry.
Retail palettes and style remapping are reused. Advance metrics are left
unverified rather than guessed from the face size.

The repository declares GPL-3.0. The adapter is independently implemented
against its file formats; source URLs, revision, input hashes and notices
accompany converted output. The font is separately attributed to
[BoutiqueBitmap9x9](https://github.com/scott0107000/BoutiqueBitmap9x9).
Preserve the embedded notices from version 1.7 rather than assuming the
current font release's license text describes that exact historical binary.
Neither the repository license nor a font license licenses original game
content. Translations, generated glyphs, ROMs and captures remain external.

## Verified scope

At the pinned revision, 1,431 active rows convert and round-trip; 66 inactive
or untranslated rows are skipped. Of the active rows, 1,398 match the
extracted retail source tokens. The remaining 33 belong to `pages:battle`,
`pages:quest/`, and `pages:choice`; their consumer bindings remain unresolved.
The subset requests 1,249 dynamic characters and renders 1,245. The bundled
font lacks U+4FAC, U+5FCF, U+8426, and U+9522. No substitute boxes are emitted.
These counts describe resource conversion, not localization or decompilation
completion. No new runtime, palette-style, advance, or hardware evidence is
claimed by this adapter.

Two independent clean conversions produced byte-identical output files. A
separate verification harness compared all 1,245 packed glyphs against the
pinned upstream generator under the same Pillow version: all matched. This
includes placement and decoration, and is stronger evidence than visual
similarity. Five focused control/terminator/mutation tests passed.

## Bear ROM source bridge

The user-supplied Japanese-based Bear translations are separately hash-pinned
in the optional source catalog. The small-fixed variant is the preferred
localization source; neither is a US retail build reference.

```sh
python3 tools/identify_rom.py "$BEAR_ROM"
python3 tools/identify_rom.py "$RETAIL_ROM"
uv run --no-project --with pillow==11.3.0 \
  python tools/extract_bear_localization.py --rom "$BEAR_ROM" \
  --retail-rom "$RETAIL_ROM" --upstream "$UPSTREAM" \
  --output-dir "$BEAR_ASSETS"
uv run --no-project --with pillow==11.3.0 --with fonttools==4.60.1 \
  python tools/convert_ffta_us_cn.py --upstream "$UPSTREAM" \
  --assets-dir "$ASSETS" --bear-assets "$BEAR_ASSETS" \
  --output-dir "$OUTPUT" --generate-font
```

The bridge explicitly imports the pinned external upstream parser and its
US/JP alignment rules, unlike the independent format converter. It only
parses/aligns and exports; it never calls upstream ROM export/repack or work
file updates. The CN parser performs three documented in-memory text repairs
at 0x48cd3f, 0x9761eb and 0x987bdf. Input files are not modified. Their offsets
and operations are retained in the extraction report. Parser acceptance is
not proof of runtime compatibility or translation accuracy.

Both supplied variants produce identical 9,760-row base-pair files and
1,497-row uncovered files. Their 3,174-glyph font payloads differ. The font
source pointer is at ROM 0x133f4 and resolves to ROM 0x425030. Each 406,272-byte
font payload round-trips through the existing atlas codec.

When `--bear-assets` is supplied, base pairs are loaded before translation
additions and corrections. The input extraction report and file hashes are
verified. Font generation prefers exact source-ROM glyph bytes using the
upstream character map; only absent characters fall back to the bundled TTF.
No outline, shadow or origin changes are applied to source-ROM glyphs.

The merged profile has 8,900 active rows, all of which pass standard token
round trips. Source binding verifies 7,984 rows; 97 scene rows have source
mismatches (including absent US originals), and 819 rows belong to unmapped
page families. These remain integration blockers, not inferred matches.
The dynamic inventory contains 2,358 characters: 2,234 exact Bear glyphs,
120 TTF-generated glyphs, and four missing glyphs. Source glyph meaning relies
on the pinned upstream charset; glyph-copy fidelity does not prove every
Unicode identity. Advance metrics and ROM integration remain unverified.
