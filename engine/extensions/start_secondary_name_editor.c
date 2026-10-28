/* CN extension of the pinned decompiled naming entry. Vendor is unchanged. */
#include "cjk_name_bindings.h"
#include "../../vendor/fftadecomp/src/task_tree_core.h"
struct NameEditorEvent {
    u32 unassigned_00;
    u8 *caller;
    u32 unassigned_08[3];
    u16 name_kind;
    u16 unassigned_22;
    u32 unassigned_24;
};
typedef char EventExtent[sizeof(struct NameEditorEvent)==28?1:-1];
extern u32 AdvanceSaveNameEditor(TaskNode *,u16 *,void *);
extern TaskNode *CreateSceneCommandTask(TaskCallback,u16,const u32 *,TaskNode *);
void StartSecondaryNameEditor(u8 *caller)
{
    struct NameEditorEvent event;
    register u32 cleared asm("r1")=0;
    asm("" : "+r"(cleared));
    caller[6]=cleared;
    event.caller=caller;
    event.name_kind=cleared;
    /* The native event leaves the other transport bytes unspecified. */
    CreateSceneCommandTask((TaskCallback)AdvanceSaveNameEditor,928,(const u32 *)&event,(TaskNode *)0);
}
asm(".global AdvanceSaveNameEditor\n.thumb_set AdvanceSaveNameEditor," CJK_NAME_CALLBACK "\n.global CreateSceneCommandTask\n.thumb_set CreateSceneCommandTask,0x08121b8d\n");
