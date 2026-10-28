# Standalone migration

CN C/ASM, token/resource packaging and pinyin behavior are owned by this project.
The official generic source-replacement/resource-fragment and external-build
interface was merged in [upstream PR #1](https://github.com/ffta-decomp/fftadecomp/pull/1).
The dependency lock selects that official merge tree; vendor carries no local patch.

The joint build compiles the published native naming entries and selects the
CN extensions. CN and pinyin default on; explicit exact-CN and English paths
remain available. Private resources are explicit local inputs and are never
included in source archives.

The independently selectable serial counter fix also defaults on for CN. Disable
both pinyin and the link fix to reproduce the original Chinese reference exactly.

Validation covers exact English/CN identities, deterministic default output,
glyph/token and pointer bounds, source-only packaging and emulator naming/dialogue
paths. Emulator tests do not establish physical hardware or flash-save/reload.
See the README and native pinyin guide for commands and coverage limits.

The fixed-layout exact builder and temporary ROM-patch adapter remain historical
compatibility tools. They do not replace the joint build entry.
