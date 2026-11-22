/* Advance only battlefield sprite animation clocks; submit graphics once. */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
#include "../common/options/options.h"
#define U32(a) (*(volatile u32 *)(a))
#define U16(a) (*(volatile u16 *)(a))

static unsigned ram_object(u32 address, unsigned bytes)
{
    return !(address & 3u) && address >= 0x02000000u &&
        address <= 0x02040000u - bytes;
}

static unsigned battlefield_animation(void *context)
{
    u32 owner, renderer;
    if (!CommonOptionValue(3, 2)) return 0;
    /* Native scene control +0x94 bit 7 selects the linked battle path. */
    if (U16(0x0200f424u) & 0x80u) return 0;
    if (!U32(0x0200f4a8u)) return 0;
    owner = U32(0x0200f4b0u);
    if (!ram_object(owner, 12)) return 0;
    renderer = U32(owner + 8);
    if (!ram_object(renderer, 488)) return 0;
    /* The native visit cycle passes its renderer's embedded +20 context.
     * Menu previews use a distinct renderer even while a battle is alive. */
    return (u32)context == renderer + 20;
}

void BattleAnimationTick(u8 *animation, void *context)
{
    void (*const native_tick)(void *,void *) = (void *)0x08021291;
    unsigned ticks = battlefield_animation(context) ?
        1u << CommonOptionValue(3, 2) : 1u;
    do {
        native_tick(animation, context);
    /* Opcode 8 reports a one-visit event at +0x1e. Let its existing consumer
     * observe it before a subsequent tick resets the byte. Frozen/instant
     * tracks retain their native semantics and do not receive an extra visit. */
        if (animation[30] || (U32((u32)animation) & 0x2100u)) break;
    } while (--ticks);
}
