# Native naming source extensions

These four complete C modules are selected by the official build extension API;
no vendored C is edited. The two naming constructors select the pinyin callback
and reserve its larger work area. The save-name update selects the native input
bridge. The sprite-layout entry calls the tab adapter while retaining the
original Aa/123 resources and native drawing behavior.

`cjk_name_bindings.h` is generated in the external build directory. Every
replacement is checked against the original complete module envelope and the
normal compiler entry identity before publication.

Pinyin behavior lives in `../pinyin/` and the project's native-name C adapter.
The small Thumb assembly support provides EABI division and near/far-call
bridges for the payload beyond Thumb-1's direct BL range. It is not a substitute
for an unrecovered naming function. Chinese-reference loading/compatibility
source is separately selected by the CN build profile.
