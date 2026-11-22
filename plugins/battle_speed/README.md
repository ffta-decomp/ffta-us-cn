# Experimental battlefield animation speed

Build with `--enable-battle-speed`, then choose 1x, 2x, 4x or 8x in System /
Options. The standalone plugin works with the English baseline, CN2025 and
CN2026. Labels and hints follow the build language; multiplier values are
language-neutral. The default is 1x. Stable settings bits 3-4 store the four
modes across ordinary battery saves and cold starts. Reset restores 1x.

The installer redirects the one sprite animation tick call at US ROM offset
`0x21494`. Each visit executes up to the selected number of native ticks before the
original renderer submits its final sprite once. Only the published battle
renderer is eligible; menu preview renderers and linked battle mode are excluded.
One-visit animation events stop extra ticks until the consumer sees them.
Frozen and instant tracks receive one native tick. Event-heavy tracks can
therefore run below the selected multiplier to preserve their signals.

This first experiment accelerates battlefield sprite frame clocks. It does
not double movement interpolation, scene coroutine delays, AI, turns, input,
audio, spell task scheduling or video refresh. It is not a whole-battle speed mode.
FFTA2's extra scheduler passes informed the separation of update and drawing;
its NDS scheduler code and addresses are not transplanted here.

The native animation engine and event consumers remain unchanged. No new RAM
reservation or save-format change is introduced. Full action/effect coverage,
natural battle settlement and hardware timing still need acceptance.
