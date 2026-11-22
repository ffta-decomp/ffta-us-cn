# Optional gameplay enhancements

CN2026 registers three in-game switches with `common/options`: monthly shop
refresh, growth equipment +5 per battle, and nonparticipant equipment AP +20.
All are off for existing saves whose reserved settings byte is zero. Choose
switches in System / Options and save normally to persist them.

Shop refresh calls both original functions with Thumb entry addresses, samples
at most 200 candidates, and commits only a complete five-item distinct list.
Growth increments saturate at 255 and retain the original +1 when disabled.
AP progress is stored in ten-AP units: adding 2 internally awards 20 displayed AP.
Nonparticipant AP runs at the native AP-page entry transition, deduplicates
skills across equipment, preserves the native availability bit, caps progress,
and calls native paired-skill/job-unlock helpers. It neither borrows allocator
scratch RAM nor appends nonparticipants to the eight-entry result table.

The original mod's fixed starting names remain disabled. New recruit naming is
a separate optional plugin. No late-save character names are rewritten here.

AP gains currently do not add nonparticipant mastery popup rows. Direct native
routine tests do not establish full battle, linked multiplayer or hardware
acceptance.
