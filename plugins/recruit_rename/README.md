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

Use a copy of your battery save. With this plugin, mGBA expands a 64 KiB
save to 128 KiB at boot under default settings. The first bank is preserved,
the added bank is erased, and existing 128 KiB saves retain both banks.
For VBA-M, expand a 64 KiB save before importing it. If your emulator
still selects 64 KiB, set its cartridge override to Flash 1 Mbit.

```sh
python3 plugins/recruit_rename/migrate_save.py original.sav recruit.sav
```

Manual migration copies all 65,536 original bytes and appends an erased bank.
The game still writes and verifies progress in bank 0. If the startup probe
finds only 64 KiB Flash, ordinary recruitment keeps its original behavior.
The ROM retains game code `AFXE` and advertises `FLASH1M_V103`.
To roll back, use the original ROM and your 64 KiB backup. A copy of the
current save's first 65,536 bytes carries the current native progress and
restores recruits to their original names.

Each name block is paired with the native save's first physical sector in bank 1.
The native sequence and checksum identify the exact save, and a separate CRC
covers the name records. Each name belongs to the native roster slot and is
checked against the unit's original name and race. The native roster copy
replaces the slot's previous name after the player accepts the recruit.
The party card, unit details and recruitment prompts show the resulting name.
Native unit identifiers, protagonist naming and clan naming retain their
original behavior.
Names using the shared Latin letters and digits display in both ROMs. Other
names remain in the save and display in the build whose font they use. The
other build displays the recruit's original name.

For testing, use a copy of a real late-game battery save with an empty roster
slot. The controlled mGBA fixture enters the existing recruit scene with a
native candidate produced at `0x080d241c`. It stages the scene's native buffer
and free-slot pointer, then uses Game Boy Advance buttons for naming,
recruitment, the System save menu and cold load.
