#ifndef RG_OPENING_SCENE_GATE_H
#define RG_OPENING_SCENE_GATE_H
/* The observed native boundary immediately after the snowball battle. */
static int RgOpeningSceneGate(unsigned step, unsigned group, unsigned script,
                              unsigned queued, unsigned count, unsigned mode,
                              unsigned battle_context)
{
    return step == 1 && group == 0x0101 && script == 2 && queued == 2 &&
           count == 1 && mode == 0 && battle_context == 0x0200f4e8;
}
#endif
