# fastskip patch and title option

The local `fastskip` project entry is declared in `plugins/plugins.json` and
pinned by `config/plugin-projects.lock.json`. The normal joint build calls its
`prepare` entry and applies the returned `build-extension-v1` manifest. It
does not edit vendor files or import the rest of the roguelike game mode.

Default Chinese builds include **Title > Info > Options**. The snowball fast-skip
switch defaults off. A toggles it; B closes Info. The setting survives starting
a new game, is reset when the title context is initialized and never touches
cartridge saves. `--disable-fastskip` removes both the Options page and its code
hooks. English and exact-reference profiles omit the plugin.

When the setting is on, the original scene/slot/allegiance signatures limit the
snowball target and the second battle's two enemies to 1 current HP. Native
attacks and KO handling remain intact; zero HP is never raised. At the observed
post-snow lifecycle boundary, the native battle-release helper is called before
entering the Montblanc encounter and second battle. The tutorial command flag
is cleared at the second battle's normal command boundary, after its law notice.

The extension checks the complete original frame, scene and menu-heap envelopes
before installing eight-byte Thumb tail jumps. Its 782-byte linked service
payload currently occupies a declared 8 KiB ROM arena at `0x08e00000`. The native
menu heap excludes `0x0203fff0..0x02040000`, reserving exactly 16 bytes for the
runtime option. It fails on conflicting hooks or occupied arena bytes. Source
provenance and original hashes are in `plugins/fastskip/config.json`.

The standard `tools/build.py --patch-output "$LOCAL_IPS"` and private-build
entry points include fastskip in the final IPS against authenticated US retail.
An incremental IPS must identify its exact CN baseline hash as well. Never
upload these private ROMs or patches as part of a source archive.

## Reproduce emulator acceptance

Use the existing bounded mGBA replay executable explicitly:

```sh
python3 tests/replay_fastskip.py \
  --replay "$REPLAY_EXECUTABLE" --rom "$BUILT_CN_ROM" \
  --output-dir "$NEW_EXTERNAL_EVIDENCE_DIRECTORY"
```

The replay starts from cold boot, uses ordinary button inputs and generates
all states itself. It checks menu navigation, both switch directions, new-game
heap retention, protagonist naming, snowball target HP (off: 8; on: 1), native
snowball completion, second-battle entry and command setup, two enemy HP values
of 1, the unaffected ally and preserved protagonist name. It writes screenshots,
RAM dumps, input files, logs and `acceptance.json` only to the explicit external
directory. Input events use hexadecimal key masks, as required by the runner.

Host tests also exercise HP identity guards, unrelated scenes, zero HP,
transition signatures and the option's validity checks under ASan/UBSan.
Hardware operation, flash-save/reload and winning the second battle are separate
acceptance gates.
