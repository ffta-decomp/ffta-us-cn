# Supplied US Chinese ROM: address layout and exact-match target

The target is the authenticated 16 MiB translated image, SHA-256
`ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03`.
The earlier 32 MiB append-layout experiment does not meet this objective and is
superseded for this purpose. No full-image Chinese bytematch is claimed here.

## What the translation reuses

ROM offsets become CPU addresses by adding `0x08000000`.

| Structure | ROM offset retained | CPU address retained |
| --- | --- | --- |
| Scene master table | `0x9C1484` | `0x089C1484` |
| Fixed-text master table | `0x36D678` | `0x0836D678` |
| Battle word pointer table | `0x5567F0` | `0x085567F0` |
| System word pointer table | `0x5668B0` | `0x085668B0` |
| Glyph atlas, 3175 cells × 128 bytes | `0x433330` | `0x08433330` |
| Glyph advance table, 3175 bytes | `0x4966B0` | `0x084966B0` |

All eleven word root tables retain their original addresses. Of 3235 pointer
slots, 3223 change target and 12 retain their value, including one null slot.
The original glyph loader remains byte-identical; paired atlas/advance data are
replaced at the original bases.

Reusing a lookup table is different from retaining a string address. Among the
conservatively mapped 15201 original IDs, 10951 valid text targets move, 4247
retain their address and tokens, one changes tokens in place, and two original
close-control placeholders have missing translated pointer slots. This count is
not the complete translated header inventory. Original scene and fixed payloads
remain byte-identical at their obsolete locations for all corresponding IDs.

Examples:

| ID | Original ROM / CPU | Chinese ROM / CPU |
| --- | --- | --- |
| Scene page1 entry0 | `0x9C16EE` / `0x089C16EE` | `0xA8A180` / `0x08A8A180` |
| Battle word8 | `0x55420E` / `0x0855420E` | `0xA83448` / `0x08A83448` |

Scene page1 itself moves from `0x9C1580` to `0xA8A000`. The existing master slot
stores a 32-bit offset relative to the unchanged scene master. Fixed-text slots
store absolute CPU pointers. Entries inside pages use 16-bit page-relative
offsets. Physical pages can be shared by several logical page IDs.

## Why expansion is unnecessary

The entire retail interval ROM `0xA50000..0xB00000` (720896 bytes) is `FF`.
The translation places resource payloads, startup data/code and text in this
existing region. Its last changed byte is before ROM `0xAF38DC`; both images
remain `0x1000000` bytes. The 32 MiB layout was an implementation choice in the
prototype, not a limitation imposed by Chinese text capacity.

The union of conservatively mapped relocated text payloads occupies333165 bytes;
333140 of those bytes were `FF` in retail. The other25 are the small low-ROM
`uitm` rearrangement. These are measured byte identities, not a general license
to overwrite every `FF` run or normalize unused space.

## Direct consumer roots must also be followed

Seven existing consumer page roots redirect to new pages, even though their old
payloads remain unchanged:

| Original ROM | Chinese ROM |
| --- | --- |
| `0x497418` | `0xABCA00` |
| `0x4A002C` | `0xAC2800` |
| `0x4AADFC` | `0xAC9700` |
| `0x4B64A4` | `0xAD1100` |
| `0x4B83A0` | `0xAD2740` |
| `0x4C3D50` | `0xAD8300` |
| `0x4E8FD4` | `0xAEFA00` |

The bounded reference at `0x13C84` retains `0x084EF3F4` for the eighth previously
examined page. This does not establish that every other consumer is covered.
The earlier conclusion that all eight pages were untranslated was incorrect.

## Exact placement includes headers and opaque records

Relocated page bases are observed to be32-byte aligned; not every page is
256-byte aligned. Translated headers contain a first `FFFF` sentinel and `FF`
padding. Page1 has first offset `0x180`, 183 pointer-looking slots before `FFFF`
and16 padding bytes; retail has first offset `0x16E`,182 slots and no padding.
A candidate slot is not proof that a script uses that text ID. Do not derive a
translated runtime count by dividing the first offset by two.

Thirteen scene/fixed candidate slots fail strict existing decoding. Another
consumer page at `0xAC9700` contains128 four-byte `6A 18 00 00` placeholders;
their runtime meaning is unresolved. Preserve observed bytes and bindings rather
than inventing text or clearing flag bits. Preserve trailing bytes, page aliases,
obsolete English data, physical order and padding for the exact-match target.
No universal string deduplication or arbitrary relocation is justified.

## Code and resource changes are part of the target

There are22 resource-copy call redirects,41 changed pointer literals, a post-load
resource replacement hook, an ARM startup display prelude and two immediate
changes in the bounded low-code frontier. The copy helper at CPU `0x083B4220`
handles length-prefixed uncompressed resources; it is not a glyph decoder.
The helper occupies former resource data near ROM `0x3B4214`; that resource is
moved to `0xA50000`. This is reclaimed storage, not an originally empty cave.
Some resources split by consumer: original `0x3BB7F0` maps to both `0xA51E00`
and `0xA52200`. A global one-to-one pointer substitution would be incorrect.

The matching implementation must reproduce those changes and all remaining
resource spans explicitly. A blanket changed-byte patch or a copy of the
translated ROM would not establish a recovered build implementation.

## Reproducible read-only comparison

```sh
export FFTA_DECOMP_ROOT=/explicit/compatible/engine
python3 tools/compare_us_cn_layout.py --retail "$US_ROM" \
  --translated "$CN_ROM" --output-dir "$EXTERNAL_EVIDENCE"
```

The JSON and CSV retain per-original-ID ROM/CPU addresses, byte hashes, storage
sizes and whether obsolete payloads survived. Separate external header, consumer
reference and code/storage reports retain the unbound/unknown cases. This review
generates no new ROM and makes no new whole-ROM alignment claim.
