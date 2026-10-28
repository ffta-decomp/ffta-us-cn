# Private conversion evidence

## 2026-10-18: Optional opening dialogue font shadow demo

The optional Fusion Pixel 12px builder now composes separate fill, cardinal
outline, and down/right shadow masks in a fixed priority order. It preserves
retail palette indices 0/1/2/3 and the original text-style remapping; no
hardcoded RGB palette or second runtime shadow pass is introduced.

The revision-pinned full build passed with baseline SHA-256
`0452fa22b9d9e93d9b8c2fb8b6bffd3a9f63418a1483163d93ff3bd9967fd42a`.
The optional 16,777,216-byte demo SHA-256 is
`c45488c3da702998e20aa36e5f8d973dd865551141293479d0ce430497213c3f`.
Its 38 subset glyphs occupy 4,864 bytes with 13-pixel advances; 3,004 ROM
bytes differ from the baseline, all inside declared demo ranges.

The bounded opening replay produced inspected 240x160 framebuffer captures
at frames 3600, 3700, and 4000. All three selected dialogue boxes are legible
without visible clipping or overlapping glyphs. This validates the opening
demo only, not the entire first chapter, every palette style, later gameplay,
or physical hardware. Four representative glyphs also passed deterministic
rendering, four-index inventory and cell-bound checks. No recovered C,
function matching, or resource-reconstruction totals change.

### Opening font shadow alignment correction

The initial procedural shadow projected the outline as well as the fill,
extending up to two pixels from the stroke. It now projects only fill pixels
one step right, down, and down/right, retaining fill/outline priority.
Across all 3,175 retail glyphs, this shadow rule with the original fill and
outline masks reproduces 3,172 shadow masks exactly; the other three total
four pixel differences. This establishes shadow reach, not a reconstruction
of the original outline generation or open-font shapes. Font origin, native
12px size and 13px advance are unchanged.

The verified full-build baseline was reused after checking its report/hash.
Updated demo SHA-256:
`01f0c9dec70ed6812b31fff0f46a06e02b29a669234faf44789b78635f07b8fe`;
2,742 changed bytes remain confined to declared demo ranges.

## 2026-10-18: Optional upstream Chinese resource conversion

Registered BSoD123456/ffta_us_cn revision
`cd32ebce88bb26cae030115d5538c1d01a0772f3` as an external optional source.
The independent adapter converts 1,431 active addition/correction rows into
existing standard token streams; all 1,431 pass serializer/decoder round
trips. It skips 66 inactive/untranslated rows. Original-source token binding
passes for 1,398/1,431 (97.69%); 33 separate page-family bindings remain open.

The actual text inventory selects 1,249 dynamic characters. The bundled
BoutiqueBitmap9x9 1.7 face renders 1,245; four missing glyphs are explicit.
All 1,245 generated glyph payloads match the pinned upstream generator
byte-for-byte with the same Pillow version. Two independent clean conversion
runs produce identical files, including text and glyph payloads. Five focused
control/terminator and mutation checks pass. Embedded font permission notices
and upstream GPL-3.0 text accompany external outputs.

No ROM, translated game text, or font binary is added to source. No baseline
build inputs change and no new ROM or gameplay claim is made. Text-pointer
linking, alternate-page conversion, complete original Chinese story import,
advance metrics, and runtime validation remain required. All converted rows
are explicitly gated from direct integration. See
the independent external CJK resource project for adapter usage and limits.

## 2026-10-18: Bear translation source extraction and format conversion

Both user-supplied AFXJ Bear variants are now separately hash-pinned in the
optional localization source catalog. The small-fixed source SHA-256 is
`672dca7222a0e2b1f7b759bfb9e453fb03069ebe4250cc0293e741ff3de6427e`;
the large-font source is
`aee65df70410f9c72c2e9b7a5ac9206b826f8559050c94018907be00ef8c4574`.
Neither replaces the US retail reference.

The external upstream parser exports identical 9,760-row base-pair files
from both variants, with 1,497 uncovered rows. Source fonts have 3,174 glyphs
each and independently round-trip through font_codec; their payloads differ.
The source bridge records all three upstream in-memory parser repairs and
does not modify the source ROM.

Merging the small-fixed base with pinned additions/corrections yields 8,900
active records, all token-round-trip verified. Original US token binding
passes for 7,984/8,900 (89.71%); 97 source mismatches and 819 unbound page
records remain blocked. The 2,358-character dynamic inventory yields 2,234
byte-exact source glyphs and 120 generated glyphs, with four missing glyphs.
Two clean extraction runs and two clean merged conversions are byte-identical.
All 2,234 copied glyphs were checked against the extracted source font.

The optional adapter and documentation were updated; five boundary tests and
diff checks pass. No selected-manifest changes, new recovered-code counts,
ROM integration or runtime claims arise from this milestone.

### CJK resource project boundary

At the user's direction, the upstream/Bear extraction bridge, converter,
tests, source catalog and usage documentation have moved outside this
repository into the independent CJK resource project. Historical conversion
counts above remain external research evidence, not integrated recovery.
The decomp repository owns the retail engine and generic resource formats;
localized content and third-party extraction pipelines are external.

### Explicit private CJK build boundary

The historical demo builder's resource-specific implementation moved to the
external CJK project. The retained public entry only dispatches a mandatory
private-directory/profile pair, validates script/profile containment, and
passes the decomp root explicitly. It contains no font, dialogue, glyph-code,
ROM-offset or private-path defaults. External codec loading also requires
`FFTA_DECOMP_ROOT`; adjacent-checkout discovery has been removed.

Private dispatch/environment checks pass and a symlink escaping the private
root is rejected. The private historical demo reproduces SHA-256
`01f0c9dec70ed6812b31fff0f46a06e02b29a669234faf44789b78635f07b8fe`
using its previously verified baseline. No new full build or runtime evidence
is claimed. The default retail build remains independent of private profiles.


## Bear large-font opening dialogue demo

The private `build_bear_demo.py` profile uses the hash-pinned large-font Bear
source, its original opening entries 1/0 and 1/1, and 40 directly copied
glyphs. The source renderer's width-table literal at 0x08013400 resolves to
ROM 0x488330. Both glyph bytes and individual advances are copied exactly;
there is no additional shadow pass, pixel translation or font scaling.
The US renderer retains its original palette/style processing.

The existing verified baseline SHA-256 is
`0452fa22b9d9e93d9b8c2fb8b6bffd3a9f63418a1483163d93ff3bd9967fd42a`.
The deterministic 16 MiB demo SHA-256 is
`d8c3c3029e3a90273a101e5ac4f8ce23f7d7471f296ff5ce07458616d726d8b7`.
Only declared glyph, advance and two scene-text ranges change (2,866 bytes).
All 40 glyphs and advances were independently checked against the source ROM.
Frames 3600, 3700 and 4000 were captured from the bounded input replay and
visually inspected: all three boxes are readable with intact punctuation,
line breaks and dynamic Mewt substitution. Nearest-neighbor 3x screenshots
and a 2x dialogue contact sheet provide visible pixel detail.
This reuses the prior engine baseline; it is not a new full-engine build,
whole-chapter translation or physical-hardware result. All profiles and
artifacts remain private/external.
