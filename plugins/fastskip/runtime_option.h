/* Title-owned, session-only option. The heap extension reserves these bytes. */
#ifndef OPENING_RUNTIME_OPTION_H
#define OPENING_RUNTIME_OPTION_H
struct OpeningOption { unsigned magic, enabled, inverse, reserved; };
#define OPENING_OPTION_ADDRESS 0x0203fff0u
#define OPENING_OPTION_MAGIC 0x534e4f57u
#define OPENING_OPTION ((volatile struct OpeningOption *)OPENING_OPTION_ADDRESS)
static __inline__ unsigned OpeningOptionRead(const volatile struct OpeningOption *option)
{
    return option->magic == OPENING_OPTION_MAGIC && option->enabled == 1 &&
           option->inverse == ~1u;
}
static __inline__ void OpeningOptionWrite(volatile struct OpeningOption *option, unsigned enabled)
{
    option->magic = 0;
    option->enabled = enabled ? 1 : 0;
    option->inverse = ~option->enabled;
    option->reserved = 0;
    option->magic = OPENING_OPTION_MAGIC;
}
#endif
