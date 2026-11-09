# fastskip

This local plugin uses the host's `build-extension-v1` pipeline. It adds an
Options page inside the title's Info UI. A toggles the snowball fast-skip option;
B closes Info. The switch defaults off each time the title is initialized,
survives native heap recreation when starting a game and never writes a save.

When on, signature-checked Mewt in scene 6 and the two tutorial enemies in scene
11 have at most 1 current HP. Zero HP stays zero. Native attacks, KO handling and
battle completion remain responsible for the outcome. At the observed post-snow
boundary, the scene service releases native battle resources and enters the
Montblanc encounter/second battle. The original command-mode flag is cleared at
the second battle's normal command boundary. This accelerates the opening;
it does not teleport directly out of the initial battle before an attack.

`config.json` pins the exported source files from the roguelike CN project,
original hook envelopes, ROM arena and 16-byte RAM reservation. The native menu
heap is shortened by exactly 16 bytes so the title option survives heap clearing.
All native services use indirect Thumb calls. The plugin refuses existing writes
to any full hook envelope or its entire reserved ROM arena.

Disable its build support with `--disable-fastskip` for an original menu, or
use `exact-reference`. Enabled runtime behavior and disabled behavior must be
checked separately in emulator replays. Prior source-project fixture success
does not establish a new cold-boot playthrough, save reload or hardware acceptance.
