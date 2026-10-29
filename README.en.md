# ffta-us-cn

[简体中文](README.md) | English

Optional Chinese and pinyin naming extensions for Final Fantasy Tactics Advance
US, built jointly with pinned decomp source dependencies. **CN and pinyin are
both enabled by default.** The serial counter timeout fix also defaults on for
CN builds. The ROM stays 16 MiB; native glyph IDs, token/control
semantics and both original tab styles are preserved. Pinyin replaces the first
keyboard page; the original second page remains available. No third tab is added.

| Invocation | Result |
| --- | --- |
| Default | CN resources/loading, pinyin naming, serial timeout fix, title Info and appended italic entry glyphs |
| `--disable-pinyin` | CN with the serial timeout fix, without pinyin |
| `--disable-pinyin --disable-link-fix` | Exact pinned 16 MiB Chinese reference |
| `--disable-cjk` | English baseline, with pinyin disabled automatically |
| `--disable-cjk --enable-link-fix --disable-info` | English with only the serial timeout fix |
| `--disable-cjk --enable-pinyin` | Rejected as contradictory |
| `--disable-italic-font` | Keep the original font and upright Info entry |

Font plugins declare their glyph tables, source layout and priorities in
`plugins.json`. The Chinese v1.1 base has the highest priority; style plugins
append new cells and emit updated character tables without changing original
glyph codes. See [font extensions](docs/font-plugins.md).
One plugin project may export multiple plugins through a file-list manifest;
local plugins are read directly from `plugins/`, while pinned Git projects
are imported into `vendor/plugins/`. Only declared files are consumed. See [project layout](docs/plugin-projects.md).

## Fork and add a plugin

Fork this repository, copy `examples/plugin-template/build.py` into
`plugins/my_plugin/build.py`, and add the example declaration to
`plugins/plugins.json`. Run `python3 tools/plugin_projects.py sync`, then use
the normal build command. The build loads enabled declarations automatically;
no main build-script edits or second registration are required. The starter
leaves the ROM unchanged until you implement its extension manifest.

Edit local sources in `plugins/`; reserve `vendor/` for external pinned
sources. See [the local plugin guide](plugins/README.md) and
[the build-entry contract](docs/plugin-projects.md).

For private inputs, add `rom-source.txt` at your personal fork's root with one
private ROM Git URL. The [user build entry](docs/private-rom-workflow.md) reads
that file for local and manual Actions builds. No repository/revision/enable
variables are needed; Actions needs only a read-only input-repository deploy
key. The template has no real input file and skips ROM builds by default.

## Source ownership

CN C/ASM lives in `engine/`, including complete naming-entry replacements under
`engine/extensions/`. Resources and pointer layout rules live in this project.
Info is maintained and compiled directly in `plugins/info/`.
`vendor/` contains ignored Git checkouts fetched at locked revisions: the official
decomp source/toolkit, its compiler submodule and the licensed Rime dictionary.
Dependency sources are not committed or included in template source archives. The pinyin core belongs to this project under `engine/pinyin/`.
No adjacent decomp checkout or environment variable is required.

**Never edit vendor code.** Needed generic build options are submitted upstream;
see [the official extension-interface PR](https://github.com/ffta-decomp/fftadecomp/pull/1).
The dependency lock pins merged upstream commit
`4ecb640abb607decd2581383e27604e3caaee280`. This project consumes the official
source without a local vendor patch.
See [AGENTS.md](AGENTS.md) and [dependency provenance](docs/dependencies.md).

The compatibility build compiles five published decompiled native naming C
entries (1,700 original bytes), checks their complete bytes against US retail,
and applies the selected source/resource extension in the same build. Pinyin
replaces three complete source modules through the upstream extension API; it
does not overwrite vendor C or patch those C call sites by byte offset.
Other game code remains supplied by the authenticated original input. This is
not a claim that this project rebuilds the entire game from recovered source.
No optional/mod output earns decomp recovery credit.

## Inputs and prerequisites

Use Git, Python 3.12+, Clang, Make and ARM binutils (`arm-none-eabi-as`, `ld`,
`objcopy`, `nm`). Core build tools use the Python standard library. Compiler
bootstrap is serial, uses an external work directory and removes that owned
work directory after success. An existing compatible compiler may be selected
explicitly with `--compiler`; its hash and the exact native baseline checks are
recorded in the report.

Keep these resources outside the repository and source archives:

- US retail: SHA-256 `43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19`.
- Chinese reference, used only for local import/verification: SHA-256
  `ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03`.
- The imported private component pack, native-glyph map and its provenance report.
- The explicit source-font/charset inputs when deriving that glyph map.

No ROM, extracted game text, font, save or screenshot is distributed here.
The owner-supplied third-party v1.1 character mapping is retained under
`config/charsets/us-cn-v1.1/`, including its provenance and 18-sample comparison.
The build reads US retail plus the private pack; it does not load a Chinese ROM
as its output or import a whole-ROM binary diff.

## Import once, then build

Commands run from this repository root. Variables below name your external
inputs and clean output directories; there is no automatic resource discovery.

```sh
python3 tools/fetch_dependencies.py
python3 tools/verify_vendor.py
python3 tools/migrate_us_cn.py import \
  --retail "$US_ROM" --translated "$CN_ROM" --pack-dir "$PRIVATE_PACK"

python3 tools/map_native_pinyin_glyphs.py \
  --translated "$CN_ROM" --source-font "$SOURCE_FONT" \
  --source-charset "$SOURCE_CHARSET" --output-dir "$GLYPH_MAP_DIR"

# Default: Chinese + pinyin. Rime source and its Apache license were fetched above.
python3 tools/build.py --retail "$US_ROM" --pack-dir "$PRIVATE_PACK" \
  --glyph-map "$GLYPH_MAP_DIR/glyph-map.json" \
  --map-report "$GLYPH_MAP_DIR/map-report.json" --output-dir "$OUTPUT"

# Exact Chinese reference, without pinyin or the new serial timeout fix.
python3 tools/build.py --retail "$US_ROM" --pack-dir "$PRIVATE_PACK" \
  --disable-pinyin --disable-link-fix --output-dir "$EXACT_CN_OUTPUT"

# Original English baseline.
python3 tools/build.py --retail "$US_ROM" \
  --disable-cjk --output-dir "$EN_OUTPUT"
```

The final file is `ffta-us-cn.gba`; `features.json` records source/dependency
hashes, feature selections, actual compiled entry envelopes and output identity.
The generated `extension.json`, fragments and compiler reports stay external.
Use a clean output directory per build. Add `--patch-output "$LOCAL_PATCH"` to
also generate a deterministic IPS against the authenticated US input and check
its complete apply round trip. Generated patches contain local game resources:
keep them private; they are excluded from source packaging.

The [serial timeout fix](docs/link-timeout-fix.md) is a source-assembled Thumb
comparison extension, not a recovered C function or new GP-mode implementation.
Both linked players must select the same ROM and feature flags; compare full
ROM hashes. Direct-function emulator checks do not establish multiplayer support.

## Packaging and verification

```sh
python3 -m unittest discover -s tests -v
PYTHONPATH=tools python3 -m unittest discover -s tools -p test_convert_ffta_us_cn.py
python3 tools/package_source.py --output "$SOURCE_ARCHIVE"
```

The deterministic source archive includes project source and dependency locks,
without `vendor/`, `.git`, build caches, ROMs or private resources. After
extracting it, run `python3 tools/fetch_dependencies.py` to retrieve the pinned
public source and original license notices. Verify dependencies before and after builds.
For build determinism, use two clean external directories and compare final ROM
hashes; source manifests may contain their distinct explicit output paths.

See [native pinyin behavior and emulator-test limits](docs/native-pinyin-names.md),
[exact resource import](docs/us-cn-exact-build.md), and
[the observed Chinese address layout](docs/us-cn-translation-layout.md).
The former ROM-only and 32 MiB demo tools remain historical diagnostics, not the
current joint-build entry. Historical demos that require a full writable engine
checkout must select a separate development checkout explicitly.

The [persistent reference exporter](docs/us-cn-resource-export.md) exports native
glyphs, text, resources and IPS metadata, then proves a full-ROM byte match.
The optional [title Info UI](docs/plugin-info.md) reads plugin credits from
`plugins.json`; use `--disable-info` to omit it.
