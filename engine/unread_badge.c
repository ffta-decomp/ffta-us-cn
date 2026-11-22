/* Change the palette only when a native right-hand cell is our unread art. */
typedef unsigned int u32;
u32 UnreadBadgePalette(u32 cell)
{
    volatile const u32 *pixels = (volatile const u32 *)(0x06008000u + (cell & 1023u)*32u);
    const u32 *badge = (const u32 *)0x08f42000u;
    u32 tile, word;
    for (tile=0; tile<4; ++tile) {
        const u32 *part = badge+tile*8;
        if (pixels[0]!=part[0] || pixels[4]!=part[4]) continue;
        for (word=0; word<8; ++word) if (pixels[word]!=part[word]) break;
        if (word==8) return 0xe000u;
    }
    return 0xd000u;
}
