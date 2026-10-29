# Persistent US v1.1 Chinese reference export

`tools/export_us_cn.py` exports the authenticated US-based v1.1 Chinese reference
and verifies reconstruction against every byte of the supplied 16 MiB ROM.
It does not enable the new pinyin, serial timeout or Info features. Those are
independent build extensions and necessarily differ from the reference.

Use explicit private inputs and a new persistent directory outside this source
repository. This resource directory is a build input, not compiler cache.
Never clean it as part of a build-cache cleanup or upload it to source hosting.

```sh
python3 tools/export_us_cn.py \
  --retail "$US_ROM" --translated "$CN_V11_ROM" \
  --output-dir "$CN_V11_RESOURCES"
```

ARM binutils are required to assemble the readable reference compatibility
source. Select a nondefault installation with `--tool-prefix /path/arm-none-eabi-`.
No Nix or compiler bootstrap is required by the exporter.

The exporter rejects any input whose complete hash differs from the pinned
US retail or Chinese reference. It creates:

- `pack/`: native pointer tables, typed text/compression records, original
  payload assets, resource rules and readable compatibility assembly. The build
  reconstructs from this pack and US retail; it does not read the Chinese ROM.
- `glyphs/glyph-table.json`: all 3,175 native indices/tokens, ROM offsets,
  glyph hashes and advances, in the original Chinese ROM order.
- `glyphs/font-4bpp.bin`, `glyphs/font-widths.bin` and complete atlas previews:
  the actual Chinese ROM glyph resources, without reshaping or reordering.
  Preview colors 0–3 show the normal background/outline/shadow/foreground;
  other nibble indices use diagnostic colors, retaining the original raw data.
- `text-records.jsonl`: the native text records and control tokens, compression
  operations, stored hashes, and optional annotated previews. Re-encoding every
  record is checked against its original source bytes. Pointer aliases and
  padding remain in the pack's typed layout rather than being flattened.
- `ffta-us-cn-v1.1-reference.ips`: a local IPS against the authenticated US ROM.
- `patches.json` and `plugins.json`: the applied reference profile, component
  ranges and hashes, compatibility source identity and available plugin credits.
  The catalogue also lists optional plugins that are disabled in this reference.
- `reference-components.json`: explicit byte checks of the modified original
  resource loader, added copy/override/startup functions, 22 redirected calls,
  three replacement tables and their payloads, and the 76,800-byte first-screen
  bitmap identified by the startup DMA contract.
- `byte-match.json` and `export-manifest.json`: whole-ROM comparison, IPS
  round trip, input identities and a complete exported-file hash inventory.

A successful export requires a direct whole-ROM byte comparison and an IPS
round trip. The canonical IPS generated from the rebuilt ROM must also match
the canonical IPS generated from the original Chinese ROM byte-for-byte; this
does not assert binary identity with an independently encoded upstream patch file. Temporary assembly outputs are automatically removed. An incomplete
or failed export is never marked `byte-match`; an existing destination is never
overwritten.

Recheck a retained export without importing or re-extracting it:

```sh
python3 tools/export_us_cn.py --retail "$US_ROM" \
  --verify-export "$CN_V11_RESOURCES" --translated "$CN_V11_ROM"
```

`--translated` is optional for rechecking. Without it, the rebuilt image must
still match the pinned Chinese reference SHA-256. Verification checks all
exported files, all glyph cells/advances, every exported native text record and
the IPS result. Changing an exported asset fails verification.

## Unicode annotations and native glyph resources

The ROM contains native glyph codes and pixel cells, not a Unicode dictionary.
Exporting it therefore does not justify assigning Unicode labels by another
translation's charset ordering. Unknown Unicode labels stay `null` in the glyph
table and `@[U:NNNN]` in text previews. Control and half-width tokens also retain
explicit notation. Native records, never the annotated preview, drive rebuilding.
This distinction does not weaken the byte-match gate.

Optional independently checked labels can be attached with both
`--glyph-map "$NATIVE_MAP" --map-report "$NATIVE_MAP_REPORT"`. Their provenance
must bind the complete Chinese ROM, native font and map hashes. A partial map is
reported as partial and is never promoted to a complete Unicode vocabulary.

`tools/map_native_pinyin_glyphs.py` remains the conservative exact-stroke mapper
for its explicitly pinned source font/charset. It cannot substitute an unrelated
charset or invent labels when those private inputs are missing.

`tools/export_us_cn_glyph_table.py` also provides a standalone font/table export
with `--translated`, `--output-dir` and the same optional annotation inputs.
Full-ROM byte-match verification belongs to the unified exporter above.
