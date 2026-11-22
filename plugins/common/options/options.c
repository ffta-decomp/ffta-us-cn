/* Native Options extension. The four-byte saved-settings record is unchanged. */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
#define U8(a) (*(volatile u8 *)(a))
#define U16(a) (*(volatile u16 *)(a))
#define U32(a) (*(volatile u32 *)(a))
#define CONTEXT (*(u8 *volatile *)0x02009188)
#define CELLS 0x1c00
#define SETTINGS 0x1bcc
#include "bindings.h"

void EnhancedOptionsInit(void *old, void *display_a, void *display_b, u32 tile, u32 linked)
{
    u8 *p;
    u32 i;
    void *pool = *(void **)(__builtin_return_address(0) == (void *)0x080329ed ? 0x0200f38c : 0x0200f434);
    (void)old;
    p = ((u8 *(*)(void *,u32))0x08007139)(pool, 0x1c80);
    CONTEXT = p;
    if (!p) return;
    for (i = 0; i < 0x1c80; ++i) p[i] = 0;
    *(void **)(p+24) = display_a;
    *(void **)(p+28) = display_b;
    *(u16 *)(p+2) = tile;
    U16(0x02002180) = linked;
    for (i = 0; i < 4; ++i) p[SETTINGS+i] = U8(0x02002fc0+i);
    *(void **)(p+0x1c78) = pool;
    *(u32 *)(p+0x1c7c) = 0x32364f50;
}
__attribute__((naked, used)) void OptionsInitBridge(void)
{
    __asm__("mov r3, ip\n b EnhancedOptionsInit");
}
void EnhancedOptionsClear(void)
{
    u8 *p = CONTEXT;
    U8(0x0200217e) = 0;
    U16(0x02002180) = 0;
    CONTEXT = (void *)0;
    if (p && *(u32 *)(p+0x1c7c) == 0x32364f50)
        ((void (*)(void *,void *))0x08007171)(*(void **)(p+0x1c78), p);
}
u32 EnhancedQuery(u32 option, u32 query)
{
    u8 *p = CONTEXT;
    option &= 255;
    if (option < 10) {
        u32 result = NativeQuery(option, query);
        /* The native reset-row callback still writes its old, now unused cell.
         * Mirror availability into the relocated cell without altering text. */
        if (p && option == 9 && query) p[CELLS+9*4+3] = !result;
        return result;
    }
    if (!p || option >= COMMON_OPTION_COUNT) return 0;
    if (!query) {
        u32 shift = CommonOptionBits[option-10];
        u32 mask = CommonOptionMasks[option-10] << shift;
        p[SETTINGS+3] = (p[SETTINGS+3] & ~mask) |
            ((p[CELLS+option*4] << shift) & mask);
    }
    return (p[SETTINGS+3] >> CommonOptionBits[option-10]) & CommonOptionMasks[option-10];
}

/* Keep native option IDs stable while presenting Reset as the final row. */
u32 CommonReadDisplayedOption(void *view, int row)
{
    u32 index = ((u32 (*)(void *,int))0x08017b69)(view, row);
    if (index == COMMON_OPTION_COUNT-1) return 9;
    if (index >= 9 && index < COMMON_OPTION_COUNT-1) return index+1;
    return index;
}
