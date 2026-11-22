# Battle presentation speed

Build with `--enable-battle-speed`, then choose 1x, 2x, 4x or 8x in
System / Options. English, CN2025 and CN2026 share the plugin. Labels follow
the build language. The default remains 1x; settings byte 3 bits 3-4 retain
the mode in ordinary saves. Reset restores 1x. No additional static RAM or
save storage is used.

The scene-group hook at US ROM `0x23FA8` adds update visits only in native
selectors 43 (confirmed unit path), 60 (committed action) and 67 (reaction and
result presentation). Command menus, cursor movement, range/target selection,
AI decisions, turns, world menus, audio and linked battles keep their normal
update rate. Extra visits temporarily mask stale key fields and restore them
before the normal input pass. The native controller prefix is not re-entered.

The implementation follows the existing readable C contracts:

- `AdvanceBattlePhaseBody` selector 43 and `AdvanceBattleSceneRecordProgression`
  define movement updates and completion ownership. The original caller alone
  finishes the path and changes the outer battle selector.
- `BattleCallbackContinuationBody` defines the stateful action poll. Original
  setup, teardown, pending prefix work and descriptor state 14 remain with its
  native caller, preserving its opaque incoming descriptor boundary.
- `RunTaskTree_08005A24` performs removal during traversal and clears
  `CURRENT_GROUP`; extra visits restore the enclosing task context afterward.
  Only its effects interpreter is revisited. `SceneRegisteredRoot_0000A640`
  includes primitive graphics work and keeps its one native display visit.
- `08021290` calls `080210E4`, which can enqueue DMA as well as advance clocks.
  Intermediate visits use the native capacity guard to defer texture uploads;
  the final native display visit uploads the selected frame. Animation signals
  are interleaved with their consumers rather than erased by isolated ticks.
- `080A8E0C` both advances a number sequence and draws it. Extra visits call
  only `StepBattleObjectSequence`; normal drawing/cancellation stays native.
  OAM append cursors and affine caches also discard drawings issued by effect
  tasks during extra visits, preserving the frame's earlier entries.
- VBlank's `08147288` palette dispatcher normally advances once per completed
  main frame. Extra effect steps advance these RAM palette clocks too, keeping
  fade handles alive until their consumers finish. The normal VBlank retains
  palette DMA ownership. Without this interleaving, overlapping fades can
  cancel a still-owned handle and stall a spell at 4x/8x.
  Each visit first consumes the existing VBlank palette tick, then advances
  palettes for the following visit. Duplicating the initial tick can make
  Famfrit's exact-time window sequence miss a key and wait indefinitely.
- Result poll `080A7218` state 12 calls `EndBattleActionWorkspace` on every
  visit. Extra visits stop before this non-idempotent finalizer and leave it,
  result allocation release and continuation changes to the native caller.
  Native modal-prefix waits and the action pause flag also defer extra visits.

The r2 regression fixture exercises Marche's Creation Arts in the Herb Picking
battle from an explicitly supplied battery save. All four modes complete and
return to command input with identical eight-unit result records. This covers
that reported spell path, not every spell or effect combination.

Additional controlled fixtures cover elemental magic, healing, revival,
status changes, theft, attack/healing summons, Doublecast, monster control,
morphing, items, capture and Blue Magic learning. Capture checks the new bank
entry; learning checks the native mastery byte after an opposing Goblin Punch.
Both are compared at all four speeds. Dragoon's Jump fixture creates and deploys
a Bangaa actor before battle, rather than reusing a Hume animation resource.
Input regressions compare cursor/range screenshots across all four modes.

The multiplier is a logical update budget. Native resource waits, opaque
boundaries, banners, fixed transitions and unsplit primitive effects can reduce
wall-clock speed, especially at 4x/8x. This is not emulator turbo or a whole-game
speed switch. Full spell/effect coverage and physical hardware timing remain
separate acceptance gates. Private ROMs, saves, native replays and video evidence
stay outside source control; checks accept explicit local fixtures and hashes.
