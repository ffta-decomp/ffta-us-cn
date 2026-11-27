# Recruit naming

Enable the plugin with `tools/build.py --enable-recruit-rename`. The stock US
build uses `--disable-cjk --disable-author --enable-recruit-rename` and needs
only the retail ROM input. The CN build uses the native keyboard when built
with `--disable-pinyin` and the pinyin keyboard when pinyin is enabled.

During regular post-mission recruitment the editor opens with the recruit's
name and portrait. Press START to confirm the draft, or SELECT to keep the
original name. While a pinyin spelling is in progress, SELECT pages through
candidates and START waits for a candidate selection. Choosing No when
the game asks whether to recruit the unit discards the draft.

After naming the clan in the opening story, the game offers to name each
ordinary starting companion in order. Named story characters retain
their original names. Press START and choose Yes to accept
the name, choose No to continue editing, or press SELECT to keep the original.
The queue reuses the native keyboard and graphics with its own name buffer,
confirmation, and cleanup. Use
`--disable-opening-roster-naming` to skip this queue and keep regular recruit
naming available.

## Memory

The plugin reserves 1,024 bytes of cold-cleared EWRAM at
`[0x0203F800, 0x0203FC00)` for name records, the lookup cache and session
bookkeeping. The builder reads the structure size from the ARM object and
reports actual use separately from the reservation.

The post-mission editor requests 108,692 bytes from the scene heap for its
session, graphics backup and private editor pool. It restores the scene
buffers and frees that allocation when the editor closes. If it cannot get
the workspace, recruitment proceeds with the original name.

The opening queue reuses the native keyboard and frees each set of editor
buffers before starting the next companion. Its own close path keeps the
generated roster's native name IDs so each confirmed alias stays bound to its
slot. The last editor frees the task.

The name-save extension builds its 4 KiB sector image on the IWRAM stack only
during a synchronous Flash write. It checks the live stack address before
reserving the sector. The build checks the compiler's static writer frame
against the guarded stack budget with a further 512 bytes for nested Flash calls.

Use a copy of your battery save. With this plugin, mGBA expands a 64 KiB
save to 128 KiB at boot under default settings. The first bank is preserved,
the added bank is erased, and existing 128 KiB saves retain both banks.
For VBA-M, expand a 64 KiB save before importing it. If your emulator
still selects 64 KiB, set its cartridge override to Flash 1 Mbit.

```sh
python3 engine/recruit_rename/migrate_save.py original.sav recruit.sav
```

Manual migration copies all 65,536 original bytes and appends an erased bank.
The game still writes and verifies progress in bank 0. If the startup probe
finds only fixed-capacity 64 KiB Flash, that configuration is unsupported.
The ROM retains game code `AFXE` and advertises `FLASH1M_V103`.
To roll back, use the original ROM and your 64 KiB backup. A copy of the
current save's first 65,536 bytes carries the current native progress and
restores recruits to their original names.

Both companion keyboards accept at most eight committed glyphs within the
native 87-pixel width. The ninth measurement cell is reserved. On confirmation
the plugin copies the committed cells and adds its own zero terminator. On
load, a malformed record falls back to the unit's original name individually.

All native calls to the save serializer pass through the same entry hook.
Regular saves, battle suspend and mission snapshots take aliases from the
active party, filtered by the submitted roster before native reference
encoding. The ending instead rereads and updates the selected file. It
carries that file’s verified companion page forward with the new sequence
and checksum, including legacy names and reserved bytes. Overwriting a file
from a party without aliases clears the destination’s names while carrying
its reserved bytes forward. A file without saved aliases receives an empty,
checksummed companion block, including on its first save.

Before the native writer publishes the slot header in bank 0, the plugin writes
and verifies the matching name block in bank 1. A failed name write returns
through the native save-error path. The primary location mirrors the native
header sector. If that location still holds the last committed name block, the
next block uses the second sector of the new slot allocation and carries an
alternate-location marker. The loader recognizes existing primary blocks and
checks both locations against the native save.

Each regular slot and the native battle suspend slot independently owns one
4,096-byte page in bank 1. Offsets 0x000–0xBFF are reserved for names. The
current header and 24 records occupy 592 bytes, leaving 2,480 bytes for name
extensions. Regular slots also reserve the full trailing 1,024 bytes. The
suspend slot uses the first 12 bytes of that tail for an optional pending
message owner (NMR1, one-based physical roster slot, original name ID, race
and checksum), leaving 1,012 bytes. When native sectors rotate, a verified
prior page for the same logical slot supplies its unowned bytes. A fresh
slot starts with erased bytes. Keep existing offsets stable when extending
the format.

For legacy suspend images that stored an alias buffer address as a battle
message argument, the loader recognizes exact alias record starts, recovers
the original name from the restored unit, then applies a validated alias if
available. New suspend saves store the native text reference in bank 0. A
suspend with only bank 0 can resume that message with the original name.
Name-table entries can be shared by multiple units; the message owner is
recorded only when the actual slot is known.
The native sequence and checksum identify the exact save, and a separate CRC
covers the name records. Each name belongs to the native roster slot and is
checked against the unit's original name and race. The native roster copy
replaces the slot's previous name after the player accepts the recruit.
The formation, deployment, battle and unit detail cards and the battle turn
order use the same resolved name. Recruitment prompts use the pending draft
until acceptance. Fixed-name units are outside the ordinary recruitment flow.
The optional opening naming flow uses its own editor sequence.
Native unit identifiers, protagonist naming and clan naming retain their
original behavior.
Names using the shared Latin letters and digits display in both ROMs. Other
names remain in the save and display in the build whose font they use. The
other build displays the recruit's original name.

When adding a display hook, trace selector 0 of `ReadUnitField` to its consumer.
The turn order stores native unit pointers in `StoreBattleTurnOrderInContext`
and resolves their text in `ResolveSelectionRecordLabel`. Route the latter
through `RenderNameBridge`. Keep native name references in state records such
as `PackBattleUnitStateValues`. The battle message queue also needs native
references, since the shared text argument can persist in the save image.
The build checks the original call instruction and patch conflicts for each
entry in `UNIT_NAME_DISPLAY_CALLS`.

For testing, use a copy of a real late-game battery save with an empty roster
slot. The controlled mGBA fixture enters the existing recruit scene with a
native candidate produced at `0x080d241c`. It stages the scene's native buffer
and free-slot pointer, then uses Game Boy Advance buttons for naming,
recruitment, the System save menu and cold load.
