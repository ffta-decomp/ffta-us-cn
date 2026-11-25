# CN2026

CN2026 extends CN2025 with translation revisions by 隼, image enhancements and
packaging by bhe, and the existing pinyin naming input method. CN2025 retains
ownership of native character codes. Existing optional gameplay and save
extensions keep their independent build switches.

Select `--cn-version cn2026 --cn2026-pack /explicit/private/pack`. The old
`--image-enhancement-pack` spelling remains an alias. The default CN2025
preserves existing builds and exact-reference output. CN2026 requires pinyin
naming; explicitly disabling it is rejected. Its credit page replaces CN2025's
page, retaining original translation credits and the four-slot Info sidebar.

`images.json` pins the image resources, native graphics pointers, tilemaps and
sprite descriptors. `revisions.json` pins 455 translation segments and skips one
unreferenced residue segment. Every preimage and input fragment is authenticated
before the official upstream extension manifest is emitted. `save-layout.json` pins five native caption-layout instruction edits for the wider label; arbitrary executable fragments and external manifests are rejected. Missing, altered or overlapping fragments
fail. Private directories are never discovered.

The verified bold results variant uses Source Han Sans SC Bold for both
Mission Cleared and Battle Victory. `result-artwork.json` records the style
and pins the paired sprite and background banks supplied in the private pack.
The original `cn2026-images-5` pack still works. If only one bank is updated,
the build rejects the mixed pair.

The supplied revision put four item labels at ROM `0xB00000`, colliding with the
pinyin program. These labels move to `0xF24000`; only the four typed content-table
pointers are retargeted. Sixteen formerly blank native glyph slots also change.
When an appended font is active, the loader mirrors their bytes into that font
and records its final hash. Existing Unicode mappings and styled glyphs remain
unchanged; the new unmapped glyph slots are not guessed into pinyin candidates.

Gameplay implementations are separate in `enhancements`; their switches register with `common/options` and start off for zero-valued legacy settings. Fixed starting names remain disabled. Direct routine tests and save/load checks have passed; full battle acceptance remains pending. Translation and image revisions are always applied
when CN2026 is selected; they are not gameplay modifier switches.

Rendering tools, extracted text, fonts, captures, fragment binaries and ROMs
remain private outside Git. Ten rounded stat labels are included after physical-pixel alias checks.
See both plans for structural checks and remaining natural scene/palette limits.
