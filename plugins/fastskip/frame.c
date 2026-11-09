/* Preserve native frame ordering; only the optional tutorial tick is new. */
#include "runtime_option.h"
static void OpeningBattleTick(void *);
void OpeningBattleFrameTask(void *unused, unsigned char *state)
{
    void *context, *actor;
    (void)unused;
    switch (*state) {
    case 0:
        *state = 1;
        break;
    case 1:
        ((void (*)(void))0x08148831)();
        context = *(void **)0x0200f4a8;
        if (context) {
            OpeningBattleTick(context);
            ((unsigned (*)(void *,unsigned,unsigned))0x08092785)(context,
                *(volatile unsigned short *)0x0200f3a6,
                *(volatile unsigned short *)0x0200f3a4);
        }
        ((void (*)(void))0x080bd06d)();
        ((void (*)(void))0x080a94d5)();
        actor = *(void **)0x0200f4b0;
        if (actor) ((void (*)(void *))0x0809a3f5)(actor);
        ((void (*)(void *))0x08024815)((void *)0x0200f3ac);
        break;
    }
}
#include "opening_battle_hp.h"
static void OpeningBattleTick(void *context)
{
    unsigned scene, phase;
    if (!OpeningOptionRead(OPENING_OPTION)) return;
    scene = *(volatile unsigned short *)0x02002192;
    RgOpeningLimitHp(scene, (RgOpeningByte *)0x02002fc4);
    if (scene == 11) {
        phase = *(unsigned short *)((unsigned char *)context + 220);
        if ((phase == 35 || phase == 37 || phase == 39) &&
            ((unsigned char (*)(unsigned short))0x080c9541)(2))
            ((void (*)(unsigned short,unsigned short))0x080c9575)(2,0);
    }
}
