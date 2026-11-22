#ifndef FFTA_COMMON_OPTIONS_H
#define FFTA_COMMON_OPTIONS_H
/* The native four-byte settings record reserves byte 3. Bits are assigned by
 * stable public descriptors, never by plugin load order. Unknown bits survive. */
static __inline__ unsigned CommonOptionValue(unsigned bit, unsigned width)
{
    return width && width <= 8 && bit < 8 && bit + width <= 8 ?
        (*(volatile unsigned char *)0x02002fc3u >> bit) & ((1u << width)-1u) : 0;
}
static __inline__ unsigned CommonOptionEnabled(unsigned bit)
{
    return CommonOptionValue(bit, 1);
}
#endif
