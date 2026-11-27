#ifndef RECRUIT_RENAME_NATIVE_H
#define RECRUIT_RENAME_NATIVE_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#define RAM(type, address) (*(type *)(address))
#define NATIVE(address, result, arguments) ((result (*) arguments)((address) | 1u))

enum {
    UNIT_COUNT = 24,
    NAME_POOL_COUNT = 725,
    NAME_MAX_CELLS = 8,
    NAME_BYTES = 20,
    NAME_TASK_BYTES = 928,
    LIVE_SAVE = 0x02000000,
    FIRST_UNIT = 0x02000080,
    GENERATED_UNIT = 0x02002fc4,
    SAVE_DEVICE = 0x0200f370,
    NAME_INPUT = 0x03000004,
};

struct Unit {
    const u8 *name;
    u8 kind;
    u8 job;
    u8 race;
    u8 remaining[257];
};

struct NameEvent {
    u16 state;
    u16 reserved;
    u8 *caller;
    u8 unused[12];
    u16 kind;
    u8 padding[6];
};

struct NameEditor {
    u8 *caller;
    u8 unused[0x298 - 4];
    void *portrait;
    const struct Unit *portrait_unit;
    u8 unused_2a0[0x2f4 - 0x2a0];
    u8 tick_flag;
    u8 unused_2f5;
    u8 page;
    u8 unused_2f7[0x2fc - 0x2f7];
    void *buffers[5];
    u8 unused_310[2];
    u8 name[18];
    u8 cursor[2];
    u8 length;
    u8 unknown;
    u8 reset;
    u8 padding[3];
    void *window;
    u8 phase;
    u8 unused_331[0x33b - 0x331];
    u8 spelling_length;
};

_Static_assert(sizeof(struct Unit) == 264, "unit stride");
_Static_assert(sizeof(struct NameEvent) == 28, "name task event");
_Static_assert(__builtin_offsetof(struct NameEditor, tick_flag) == 0x2f4, "editor tick flag");
_Static_assert(__builtin_offsetof(struct NameEditor, buffers) == 0x2fc, "editor allocations");
_Static_assert(__builtin_offsetof(struct NameEditor, name) == 0x312, "editor name");
_Static_assert(__builtin_offsetof(struct NameEditor, length) == 0x326, "editor name length");
_Static_assert(__builtin_offsetof(struct NameEditor, window) == 0x32c, "editor window");
_Static_assert(__builtin_offsetof(struct NameEditor, phase) == 0x330, "editor phase");
_Static_assert(__builtin_offsetof(struct NameEditor, spelling_length) == 0x33b, "pinyin composition");

#define NAME_POOL ((const u8 *const *)0x085680dc)
#define InitHeap NATIVE(0x080070c8, void *, (void *, unsigned))
#define HeapAllocate NATIVE(0x08007138, void *, (void *, unsigned))
#define HeapAllocationSize NATIVE(0x0800717c, u32, (void *, const void *))
#define HeapFree NATIVE(0x08007170, void, (void *, void *))
#define OriginalRecruit NATIVE(0x080802e4, void, (u32, u8 *))
u32 OriginalSave(u8 slot, u8 *image);
#define OriginalLoad NATIVE(0x0813b480, u32, (u8, u8 *))
#define ShowDialog NATIVE(0x0801174c, void, (void *, u32, u32, const void *, const void *, u32, u32, u32, u32, u32))
#define SetDialogMode NATIVE(0x0801339c, void, (u32))
#define PollDialog NATIVE(0x08011860, u32, (void))
#define ReadDialogChoice NATIVE(0x08013380, u32, (void))
#define DrawNameConfirmation NATIVE(0x0812a52c, void, (struct NameEditor *))
#define FreeNameBuffer NATIVE(0x08022854, void, (void *))
#define DestroyNameWindow NATIVE(0x08121b78, void, (void *))
#define BiosCpuSet NATIVE(0x0814186c, void, (const void *, void *, u32))
#define RestoreNameDisplay NATIVE(0x0802b8e8, void, (void))
#define ConfigureNameBackground NATIVE(0x0801e458, void, (u32, u32, u32, u32, u32, void *, void *))
#define SetSound NATIVE(0x08141540, void, (u32))
#define CopyRecord NATIVE(0x081443fc, void *, (void *, const void *, unsigned))
#define NativeWrite NATIVE(0x08141d10, u32, (u16, const void *))
#define NativeRead NATIVE(0x08141b14, void, (u16, u32, void *, u32))
enum { FLASH_ID_PANASONIC_512 = 0x1b32, FLASH_ID_SANYO_1M = 0x1362 };
#define FlashId NATIVE(0x081418c0, u16, (void))
#define NameCrc NATIVE(0x0813adf0, u32, (const void *, u32, u32))

#endif
