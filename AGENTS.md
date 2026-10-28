# Scope and ownership

This is the standalone `ffta-us-cn` project. Own Chinese resources, optional
resource-loading extensions, pinyin naming, build profiles and packaging.
Keep source and documentation in English.

## Vendor is immutable

**Never modify code or files under `vendor/`.** Do not patch dependencies,
rewrite their build scripts, add local fixes, or hide changes in vendor trees.
Verify dependency hashes with `python3 tools/verify_vendor.py`.
Dependency updates select an explicitly reviewed upstream revision and update
the lock; they must not carry unpublished local patches.

If decomp needs a build option, extension point or generic loader interface,
implement and test it in a separate checkout/branch and submit a PR to the
official upstream repository. Pin the published revision when available.
Never edit another worker's checkout or active processes.

## Build extensions

CN-specific C/ASM belongs in this project's `engine/`; resource rules and build
profiles belong in `config/` and `tools/`. Use the upstream build extension API
to select replacements/hooks at build time. Never install CN source in vendor.
Reuse existing decompiled C entry points and actual native token semantics.
Distinguish resource replacement, required CN loading behavior, compatibility
code retained solely for reference reproduction, and new pinyin UI behavior.
None of these changes earns new decomp matching credit.

The project entry point defaults to CN, pinyin and the serial counter timeout
fix enabled. `--disable-pinyin --disable-link-fix` selects exact-reference CN;
`--disable-cjk` disables all three by default. The link fix can be explicitly
enabled for English. Reject contradictory pinyin options. Keep the English
baseline available. Distinguish direct serial-function tests from real linked
multiplayer acceptance; never claim the threshold change implements GP support.

## Resources and validation

Keep ROMs, extracted game text, fonts, glyph maps, private packs, saves, captures
and built patches outside Git and source archives. Never auto-discover them.
Only independently licensed dependencies and their notices may be vendored.
Private local profiles remain ignored. Never upload a ROM or resource pack.

Pin complete input hashes, native glyph codes, pointers and dependency sources.
Validate token round trips, pointer bounds, deterministic builds, feature-off
paths and actual emulator rendering separately. Emulator success does not
establish physical hardware or flash-save/reload behavior.

Package source and pinned dependencies reproducibly with provenance and license
notices. Stage explicit paths and commit unsigned. Publishing is permitted only
within the user's requested repository and upstream PR scope.
