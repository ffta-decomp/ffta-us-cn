/* Change the palette only when a native right-hand cell is our unread art. */
typedef unsigned int u32;
typedef unsigned char u8;
typedef unsigned short u16;

static unsigned same_tile(volatile const u32 *pixels, const u32 *part)
{
    u32 word;
    if (pixels[0]!=part[0] || pixels[4]!=part[4]) return 0;
    for (word=0; word<8; ++word) if (pixels[word]!=part[word]) return 0;
    return 1;
}

void ConfigureWideUnreadView(u8 *view, u32 operation, u32 flags)
{
    u32 width, period, base, storage;
    ((void (*)(void *,u32,u32))0x080175e1)(view, operation, flags);
    if (view[-60]!=2 || view[21]!=16) return;
    width=17; period=view[23]; base=*(u16 *)(view+28);
    storage=*(u32 *)(view+12);
    /* The native task owns the row templates and character interval. Extend
     * its stride before row generation, keeping the nine-row modulo cache. */
    if (!period || base+period*width*2>1024 ||
            storage<(u32)view+108 || storage+period*width*4>(u32)view-60+0x1098)
        return;
    view[21]=width;
    view[18]=width;
}

void FinishWideUnreadRow(u8 *control, u8 *destination, u16 index)
{
    volatile const u32 *pixels;
    const u32 *old=(const u32 *)0x08f42000u;
    u32 word;
    ((void (*)(void *,void *,u16))0x0805fff1)(control, destination, index);
    if (control[0]!=2 || control[81]!=17) return;
    pixels=(volatile const u32 *)(destination+0x380);
    for (word=0; word<32; ++word) if (pixels[word]!=old[word]) return;
    /* Only an actually drawn native unread marker is replaced. Read rows
     * retain their blank cells; no saved flags or text pixels are changed. */
    ((void (*)(const void *,void *,u32))0x0814186d)(
        (const void *)0x08f43000u,destination+0x380,96);
}

void ConfigureWideUnreadScrollbar(u8 *widget, u8 *view, void *callback, u32 flags)
{
    ((void (*)(void *,void *,void *,u32))0x08017db5)(widget,view,callback,flags);
    /* Native initialization derives the arrow X from the graphics stride.
     * The frame keeps its original width, so retain its original arrow edge. */
    if ((u32)view>=0x0200003cu && (u32)view<=0x0203ffe0u &&
            view[-60]==2 && view[21]==17 && (u32)callback==0x08017f05u)
        *(u16 *)(widget+8)=((u32)view[19]+16u)*8u-
            ((widget[16]&32u) ? 8u : 0u);
}

u32 UnreadBadgePalette(u32 cell, volatile u16 *target)
{
    volatile const u32 *pixels = (volatile const u32 *)(0x06008000u + (cell & 1023u)*32u);
    const u32 *badge = (const u32 *)0x08f42000u;
    const u32 *wide = (const u32 *)0x08f43000u;
    u32 tile;
    for (tile=0; tile<6; ++tile) {
        if (!same_tile(pixels,wide+tile*8)) continue;
        /* Native row styling fixes the last two columns. The wider badge's
         * first column is the immediately preceding cell, owned by this row. */
        if ((u32)target>=0x06000002u && (u32)target<0x06008000u) {
            u16 previous=target[-1];
            volatile const u32 *left=(volatile const u32 *)(0x06008000u+(previous&1023u)*32u);
            if (same_tile(left,wide) || same_tile(left,wide+8))
                target[-1]=(previous&0x0fffu)|0xe000u;
        }
        return 0xe000u;
    }
    for (tile=0; tile<4; ++tile) {
        if (same_tile(pixels,badge+tile*8)) return 0xe000u;
    }
    return 0xd000u;
}

/* Selection styling may precede the graphics upload. The managed wide view
 * owns all three trailing badge columns, including blank read rows. */
u32 SelectedUnreadPalette(u32 cell, volatile u16 *target, const u8 *view)
{
    u32 palette=UnreadBadgePalette(cell,target);
    if ((u32)view>=0x0200003cu && (u32)view<=0x0203ffe0u &&
            view[-60]==2 && view[21]==17 &&
            (u32)target>=0x06000002u && (u32)target<0x06008000u) {
        target[-1]=(target[-1]&0x0fffu)|0xe000u;
        palette=0xe000u;
    }
    return palette;
}
