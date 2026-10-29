> Current joint build: use `tools/build.py --disable-pinyin --disable-link-fix` for exact CN
> variant. The commands below describe the reusable import/compatibility tools.

# Exact native US Chinese reconstruction

The fixed-layout builder reproduces the authenticated 16 MiB Chinese reference
from the English baseline, an explicitly imported private component pack, and
readable assembled hook source. It does not append a new text bank or expand the
ROM. The translated ROM is an import/verification input, not a build input.

Native glyph codes, ordering, 4bpp cells, widths, token streams and compression
operations retain their reference identities. No Unicode reassignment, generated
font or alternate charset is used. A future Unicode editor must be an auxiliary
mapping and must not silently change the native encoding.

## Local commands

The pinned vendor source supplies the read-only engine codecs by default. Keep
all inputs and generated outputs outside this repository. `PACK` must be a new
external directory; `US` and `CN` are explicitly selected local input paths.

```sh
python3 tools/migrate_us_cn.py import --retail "$US" --translated "$CN" --pack-dir "$PACK"
python3 tools/migrate_us_cn.py build --retail "$US" --pack-dir "$PACK" --language zh --output-dir "$OUT_ZH" --tool-prefix arm-none-eabi-
python3 tools/migrate_us_cn.py build --retail "$US" --language en --output-dir "$OUT_EN"
```

Chinese output is released only if the complete image hash equals the pinned
Chinese reference. English output must equal the original English image.
The importer authenticates both source hashes; builds verify every imported pack
file. Components must remain inside 16 MiB and overlapping writes must agree.

The pack is not a whole-ROM binary patch. Typed native token records are
re-encoded, fonts round-trip through the native atlas codec, resource headers and
override entries are serialized, pointer/call edits are generated, and 606 bytes
of added code are assembled from `engine/us_cn_hooks.s`. Native page templates
retain exact headers, pointer tables, padding and explicitly opaque entries.
Unknown resource formats remain source-pinned opaque assets, not guessed text.
Address fields use ROM offsets; CPU addresses add `0x08000000`.

See [layout evidence](us-cn-translation-layout.md) for unchanged roots and internal
relocation. The translation uses internal space starting at ROM `0xA50000`,
including data/resources followed by relocated native text; obsolete English
payloads can remain at their original locations. This is distinct from a new
32 MiB append layout.

The first reconstruction passed a complete byte comparison with zero differing
bytes, two clean imports/builds, native font/width checks and English baseline
comparison. Reference SHA-256:
`ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03`.
Runtime screenshots are private external artifacts. Whole-image identity proves
reconstruction identity, not linguistic quality or exhaustive game coverage.


## Original modified resource loader

The exact reference profile includes the Chinese ROM's changes to the original
resource loader at `0x08005318`, its continuation at ROM `0x53BC`, the added
copy/override functions, native replacement tables and all replacement payloads.
They are reconstructed by this project's `engine/us_cn_hooks.s`,
`config/us-cn-reference-layout.json` and typed resource exporter. At runtime the
loader chooses replacement resources and copies them into RAM; it does not
repatch the ROM. The original first-screen bitmap and startup display routine
are included as reference resources/compatibility behavior.

`tools/export_us_cn.py` checks these components explicitly and also compares all
16,777,216 reconstructed bytes. `reference-components.json` records the loader,
call sites, table/payload and 76,800-byte first-screen checks. Source is owned
here; no vendored decomp source is modified and no new matching credit is earned.
