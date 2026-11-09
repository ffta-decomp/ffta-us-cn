/* Optional opening test: keep native battle resolution and KO handling. */
#ifndef RG_OPENING_BATTLE_HP_H
#define RG_OPENING_BATTLE_HP_H

typedef unsigned char RgOpeningByte;
typedef unsigned short RgOpeningHalf;
#define RG_OPENING_UNIT_SIZE 264u

/* Slot signatures are from the CN/US native tutorial encounters. A scene and
 * per-slot identity/allegiance check prevents changes in unrelated battles.
 * Zero HP is never raised: the native engine owns knockout and cleanup. */
static void RgOpeningLimitHp(unsigned scene, RgOpeningByte *units)
{
    RgOpeningByte *u;
    unsigned i;
    if (scene == 6) {
        u = units + 5u * RG_OPENING_UNIT_SIZE;
        if (u[4] == 0x10 && (*(RgOpeningHalf *)(u + 40) & 0x8000u) == 0 &&
            *(RgOpeningHalf *)(u + 24) > 1)
            *(RgOpeningHalf *)(u + 24) = 1;
    } else if (scene == 11) {
        for (i = 0; i < 2; ++i) {
            u = units + i * RG_OPENING_UNIT_SIZE;
            if (u[4] == 0x01 &&
                u[5] == (i == 0 ? 0x11 : 0x0d) &&
                (*(RgOpeningHalf *)(u + 40) & 0x8000u) != 0 &&
                *(RgOpeningHalf *)(u + 24) > 1)
                *(RgOpeningHalf *)(u + 24) = 1;
        }
    }
}
#endif
