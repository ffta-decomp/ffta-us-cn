/* First function in this relocated module is the entry service. */
#include "runtime_option.h"
static int OpeningGate(unsigned int, unsigned int, unsigned int, unsigned int, unsigned int, unsigned int, unsigned int);
static void OriginalOpeningSceneLifecycle(void *, unsigned char *);

void OpeningSceneService(void *context, unsigned char *step)
{
    volatile unsigned short *queue = (volatile unsigned short *)0x02002190;
    volatile unsigned char *system = (volatile unsigned char *)0x0200f390;
    volatile unsigned char *count = (volatile unsigned char *)0x0200219c;
    unsigned int battle = *(volatile unsigned int *)0x0200f4a8;
    if (OpeningOptionRead(OPENING_OPTION) &&
        OpeningGate(*step, queue[0], queue[1], queue[2], *count, system[0], battle)) {
        /* Reproduce the observed transition order in the tested fixture.
         * This native helper frees battle resources and finishes its tasks. */
        queue[0] = 0x0202;
        queue[1] = 9;
        queue[2] = 9;
        system[0] = 9;
        system[12] = 0;
        ((void (*)(void))0x08125561)();
    }
    OriginalOpeningSceneLifecycle(context, step);
}

#include "opening_scene_gate.h"
static int OpeningGate(unsigned int a,unsigned int b,unsigned int c,unsigned int d,unsigned int e,unsigned int f,unsigned int g)
{ return RgOpeningSceneGate(a,b,c,d,e,f,g); }
/* Calls go through Thumb function pointers: the old linker cannot safely use
 * ARM-state absolute veneers to enter Thumb native helpers from relocated code. */
struct OpeningLifecycle { void *task_group; unsigned int unknown04; void *script_task; unsigned char phase; };
#define OPEN_LIFECYCLE (*(struct OpeningLifecycle **)0x020159cc)
#define OPEN_CALL(addr) ((void (*)(void))(addr))()
static void OriginalOpeningSceneLifecycle(void *unused, unsigned char *step)
{
    void *task;
    (void)unused;
    switch (*step) {
    case 0:
        if (*(volatile unsigned char *)0x0200219c)
            OPEN_CALL(0x08009fd1);
        *step = 1;
        break;
    case 1:
        if (!((unsigned char (*)(void))0x08009fbd)()) break;
        OPEN_CALL(0x08121e49);
        OPEN_CALL(0x08121e9d);
        task = ((void *(*)(unsigned int))0x0812237d)(*(volatile unsigned short *)0x02002192);
        OPEN_LIFECYCLE->script_task = task;
        *(volatile unsigned char *)0x0200f391 = 1;
        *step = 2;
        break;
    case 2:
        if (OPEN_LIFECYCLE->phase) *step = 3;
        ((void (*)(void *))0x08005a25)(OPEN_LIFECYCLE->task_group);
        ((unsigned int (*)(void))0x08121c39)();
        break;
    case 3:
        ((void (*)(void *))0x08005a25)(OPEN_LIFECYCLE->task_group);
        OPEN_CALL(0x08121c19);
        OPEN_CALL(0x08121f81);
        *step = 4;
        break;
    case 4:
        *(volatile unsigned char *)0x0200f391 = 0;
        OPEN_CALL(0x08009ff9);
        OPEN_CALL(0x08121f39);
        OPEN_CALL(0x08121a49);
        OPEN_CALL(0x08121ef1);
        OPEN_CALL(0x08121e75);
        *step = 1;
        break;
    }
}
