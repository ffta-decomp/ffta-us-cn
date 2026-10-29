# US Chinese v1.1 character mapping

Converted from the third-party workbook `美版汉化字符表.xlsx` supplied by the
project owner. Inclusion of this character mapping in the project was explicitly
requested by the owner. This provenance note does not assign a license to the
third-party material. The source workbook identity is pinned in `manifest.json`.

- `character-table.json` and `character-table.csv` preserve all 3,175 native
  indices, including 2,731 labelled entries and 444 unlabelled entries.
- `index-to-unicode.json` maps decimal native indices to Unicode labels or null.
- `unicode-to-tokens.json` preserves every labelled token for each character;
  duplicate labels are aliases, not silently overwritten entries.
- Native full-width tokens are `0x8000 | index`. Workbook hex values represent
  the index, without the `0x8000` token flag.
- `comparison-report.json` records all 18 previously reviewed Info characters:
  every character agrees with its reviewed v1.1 native index. This sample check
  does not establish semantic correctness of every other third-party label.
- Glyph hashes and advances bind each row to the pinned Chinese ROM. No font
  pixels, ROM contents, game text, or resource pack are included here.

Reproduce with `tools/convert_cn_character_sheet.py --workbook INPUT.xlsx
--translated CN_ROM --known-map REVIEWED_MAP.json --output-dir NEW_DIRECTORY`.
The converter uses Python's standard library and refuses an existing output
directory. Source workbook, ROM and reviewed map inputs remain external.
