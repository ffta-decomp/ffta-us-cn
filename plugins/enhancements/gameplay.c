/* Native Options extension. The four-byte saved-settings record is unchanged. */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
#define U8(a) (*(volatile u8 *)(a))
#define U16(a) (*(volatile u16 *)(a))
#define U32(a) (*(volatile u32 *)(a))
#include "../common/options/options.h"
#include "bindings.h"
u32 EnhancedGrowth(u32 value)
{
    u32 result = (value & 255) + ((CommonOptionEnabled(1)) ? 5 : 1);
    return result > 255 ? 255 : result;
}
void EnhancedShop(u32 arg)
{
    u16 chosen[5];
    volatile u16 *pool = (volatile u16 *)0x02001f30;
    u32 seed, n = 0, guard, k, id;
    ((void (*)(u32))0x080360f9)(arg);
    ((void (*)(u32))0x08035d01)(0);
    if (!(CommonOptionEnabled(0)) || U8(0x02002fbb) != 1) return;
    seed = U16(0x04000006) | ((u32)pool[0] << 16) | ((u32)pool[1] << 24);
    if (!seed) seed = 1;
    for (guard = 0; guard < 200 && n < 5; ++guard) {
        seed = seed * 1664525u + 1013904223u;
        id = (seed >> 13) & 511;
        if (!id || id > 0x177 || U8(0x0851d180+id*32+0x18) < 1 ||
            U8(0x0851d180+id*32+0x18) > 30) continue;
        for (k = 0; k < n && chosen[k] != id; ++k) {}
        if (k == n) chosen[n++] = id;
    }
    /* Commit a complete distinct list, or leave the native list intact. */
    if (n == 5) for (k = 0; k < 5; ++k) pool[k] = chosen[k];
}

/* This runs at the AP-page entry transition, never in its per-frame input
 * loop. Native participants and their result queue are not extended. */
void EnhancedPartyAP(void)
{
    static const u8 limits[6] = {16,142,77,95,85,88};
    u32 count = U16(0x0201f4fe), mask = 0, i, k;
    if (!CommonOptionEnabled(2) || !count || count > 8) return;
    for (i = 0; i < count; ++i) {
        u32 slot = U8(0x0201f518+i);
        if (slot >= 24) return;
        mask |= 1u << slot;
    }
    for (i = 0; i < 24; ++i) {
        u8 *unit = (u8 *)(0x02000080+i*0x108);
        u8 seen[144];
        u32 category = unit[6], job = unit[7], equip;
        if ((mask & (1u << i)) || (unit[0x28] & 4) ||
            category < 1 || category > 5 || !job || job > 115) continue;
        for (k = 0; k < 144; ++k) seen[k] = 0;
        for (equip = 0; equip < 5; ++equip) {
            u32 item = *(u16 *)(unit+0x2a+equip*2), group, n;
            const u8 *skills;
            if (!item || item > 0x177) continue;
            group = U8(0x0851d180+item*32+0x1d);
            if (!group || group >= ABILITY_GROUP_COUNT) continue;
            skills = (const u8 *)(0x08520080+group*20);
            n = skills[0];
            if (n > 9) continue;
            for (k = 0; k < n; ++k) {
                u32 ability = skills[3+2*k], have, need, next;
                const u8 *entry;
                if (skills[2+2*k] != job || !ability || ability >= limits[category] || seen[ability]) continue;
                seen[ability] = 1;
                if (category == 4 && (ability == 26 || ability == 33))
                    seen[ability == 26 ? 33 : 26] = 1;
                entry = ((const u8 *(*)(u32,u32))0x080cd481)(category, ability);
                need = entry[7];
                have = unit[0x40+ability] & 127;
                if (!need || need > 127 || have >= need) continue;
                /* One stored unit represents ten displayed AP. */
                next = have+2; /* +20 AP */
                if (next > need) next = need;
                /* Bit 7 is native ability availability, not a mastery flag. */
                unit[0x40+ability] = (unit[0x40+ability] & 128) | next;
                ((void (*)(u8 *,u32))0x080cd621)(unit, ability);
                if (next == need) ((void (*)(u8 *,u32))0x080cd365)(unit, ability);
            }
        }
    }
}
