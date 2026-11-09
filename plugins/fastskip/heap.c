/* Reserve exactly 16 bytes from the same native heap used by the source mod.
 * Its pinned start is already word-aligned. No new save or battle state. */
void OpeningInitializeMenuHeap(void)
{
    void *base = (void *)0x020159d0;
    unsigned bytes = 0x0203fff0u - 0x020159d0u;
    ((void (*)(void *,unsigned))*(unsigned *)0x0836d4b8)(base,bytes);
    *(void **)0x0200f434 = ((void *(*)(void *,unsigned))0x080070c9)(base,bytes);
}
