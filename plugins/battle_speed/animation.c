/* Committed battle presentation: update native clocks, submit one display pass. */
typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned int u32;
#include "../common/options/options.h"
#define W(a) (*(volatile u32 *)(a))
#define H(a) (*(volatile u16 *)(a))
#define B(a) (*(volatile u8 *)(a))
#define CALL(a,t) ((t)(a))

static unsigned ram(u32 address, unsigned bytes)
{
    return !(address&3u) && address>=0x02000000u && address<=0x02040000u-bytes;
}

static u32 renderer(void)
{
    u32 scene, graphics;
    if (H(0x0200f424u)&0x80u || !ram(W(0x0200f4a8u),224)) return 0;
    scene=W(0x0200f4b0u);
    if (!ram(scene,948)) return 0;
    graphics=W(scene+8);
    return ram(graphics,508) ? graphics : 0;
}

static unsigned committed(u32 context)
{
    unsigned phase=H(context+220);
    /* Readable AdvanceBattlePhaseBody: confirmed path, action, reaction.
     * In particular 39/47/49 (command/range/target input) are not eligible. */
    if (W(context+208)&0x4000u || B(context+200)==1) return 0;
    if (phase==60 && (W(context+208)&0x10000u)) return 0;
    return phase==43 || phase==60 || phase==67;
}

/* One native clock visit per presentation step, including event consumers. */
void BattleAnimationTick(void *animation, void *context)
{
    CALL(0x08021291,void (*)(void *,void *))(animation,context);
}

static u32 tick_sprite(void *node, void *context)
{
    BattleAnimationTick((void *)W((u32)node),context);
    return 1;
}

/* StepBattleObjectSequence is the update portion of exact-C 080A8E0C.
 * The normal scene visitor retains ownership of drawing and cancellation. */
static u32 tick_number(void *pair, void *unused)
{
    u32 state=W((u32)pair+4);
    (void)unused;
    if (B(state+29)) CALL(0x080a8db9,void (*)(void *))((void *)state);
    return 1;
}

static void update_numbers(void)
{
    if (B(0x0200f9e8u+1500))
        CALL(0x080c7d71,void (*)(void *,void *,void *))(
            (void *)W(0x0200fa38u),(void *)tick_number,(void *)0);
}

static void update_motion(u32 context)
{
    u32 record=W(context+68), node=W(context+4), remaining=1;
    /* Selector 43's native body gates the accepted route on the moving
     * banner, then advances its path and observers. Do not re-enter the
     * opaque controller prefix or run its completion/continuation branch. */
    if (!ram(record,228) || !ram(node,132) || H(record+220)==28 ||
            !CALL(0x080a9589,unsigned (*)(void))()) return;
    if (!CALL(0x0809d8f1,unsigned (*)(void *))((void *)node)) {
        if (CALL(0x080c95a9,unsigned (*)(u32))(13))
            remaining=CALL(0x080c19a9,unsigned (*)(void))();
        if (CALL(0x080c8299,unsigned (*)(void *))((void *)W(node))) remaining=2;
    }
    while (remaining--) {
        unsigned busy=CALL(0x0809b88d,unsigned (*)(void *))((void *)record);
        if (!CALL(0x0809d615,unsigned (*)(void *))((void *)record))
            CALL(0x0809d641,unsigned (*)(void *,void *))(
                (void *)W(context),(void *)node);
        if (!busy) break;
    }
    if (!CALL(0x0809d8f1,unsigned (*)(void *))((void *)node))
        CALL(0x0809caf5,unsigned (*)(void))();
}

static void update_effects(void)
{
    u32 tasks=W(0x0200f430u);
    /* Only the task interpreter receives extra visits. The separate A640
     * primitive renderer retains its normal display visit and queue lifetime. */
    if (ram(tasks,16)) CALL(0x08005a25,void (*)(void *))((void *)tasks);
}

static u32 action_root(u32 context)
{
    u32 root=W(context+72);
    if (H(context+166)==33) {
        unsigned slot=B(context+175);
        if (slot>1) return 0;
        root=W(context+76+slot*4u);
    }
    if (ram(root,0x3454)) {
        unsigned state=H(root+0x3450);
        /* C08 states 0/14/36 require the original setup/descriptor/teardown
         * call boundary. Pending prefix owner work also stays with that caller. */
        if (state>0 && state<36 && state!=14 && !(H(root+0x26c0)&7u)) return root;
    }
    return 0;
}

static u32 reaction_root(u32 context)
{
    u32 root=W(context+84);
    if (ram(root,140)) {
        unsigned state=H(root+68);
        /* A7218 state 12 calls EndBattleActionWorkspace on every visit.
         * Leave both initialization and this non-idempotent finalizer to
         * the native caller, which also releases the result allocation. */
        if (state>0 && state<12) return root;
    }
    return 0;
}


/* Native 01194/01CF0/01F34 use two append-only OAM banks and affine caches.
 * Discard only extra drawing, not task state, allocations or DMA transfers. */
struct DrawingCursor { u32 count, secondary; u8 matrices[288]; };
static void drawing_cursor(struct DrawingCursor *saved, unsigned bank, unsigned restore)
{
    unsigned i;
    if (!restore) {
        saved->count=W(0x03000020u+bank*4);
        saved->secondary=W(0x03002c50u+bank*4);
    } else {
        W(0x03000020u+bank*4)=saved->count;
        W(0x03002c50u+bank*4)=saved->secondary;
    }
    for (i=0;i<288;++i) {
        u32 address=i<32 ? 0x03003270u+bank*32+i : 0x030032b0u+bank*256+i-32;
        if (restore) B(address)=saved->matrices[i];
        else saved->matrices[i]=B(address);
    }
}

void BattlePresentationFrame(void *group, u32 count)
{
    u32 graphics=renderer(), context=W(0x0200f4a8u), parent=W(0x02008ff0u);
    unsigned mode=CommonOptionValue(3,2), step, bank=B(0x03000028u);
    if (mode && graphics && bank<2 && (u32)group==0x03002710u && count==9 &&
            !B((u32)group+5) && W(0x03002828u)==0x08096e79u) {
        struct DrawingCursor cursor;
        u32 raw0=W(0x03000000u),raw1=W(0x03000004u),scene_keys=W(0x0200f3a4u);
        W(0x03000000u)=0; W(0x03000004u)=0; W(0x0200f3a4u)=0;
        drawing_cursor(&cursor,bank,0);
        for (step=1;step<(1u<<mode);++step) {
            u32 action=0, reaction=0;
            if (renderer()!=graphics || W(0x0200f4a8u)!=context || !committed(context)) break;
            if (H(context+220)==60 && !(action=action_root(context))) break;
            if (H(context+220)==67 && !(reaction=reaction_root(context))) break;
            if (H(context+220)==43) update_motion(context);
            if (action) CALL(0x080a8271,unsigned (*)(void *))((void *)action);
            {
                u16 capacity=H(graphics+480);
                u32 bookmark=W(graphics+484);
                /* 210E4's command 1 combines clock advancement with a DMA
                 * request. Defer intermediate images through its native
                 * capacity guard; the one display pass uploads the final one. */
                H(graphics+480)=0;
                CALL(0x080c7cc1,void (*)(void *,void *,void *))(
                    (void *)W(graphics+8),(void *)tick_sprite,(void *)(graphics+20));
                H(graphics+480)=capacity;
                W(graphics+484)=bookmark;
            }
            update_effects();
            W(0x02008ff0u)=parent;
            if (renderer()!=graphics || W(0x0200f4a8u)!=context) {
                drawing_cursor(&cursor,bank,1);
                break;
            }
            update_numbers();
            if (reaction)
                CALL(0x080a8959,unsigned (*)(void *))((void *)reaction);
            W(0x02008ff0u)=parent;
            drawing_cursor(&cursor,bank,1);
            /* VBlank already supplied the first palette tick. Consume it
             * before advancing RAM palette clocks for the following visit,
             * including the final native visit. Ticking before this step
             * would duplicate one boundary and skip another: exact-time
             * fullscreen window sequences can then miss their next key. */
            CALL(0x08147289,void (*)(void))();
        }
        W(0x03000000u)=raw0; W(0x03000004u)=raw1; W(0x0200f3a4u)=scene_keys;
    }
    CALL(0x080069f5,void (*)(void *,u32))(group,count);
}
