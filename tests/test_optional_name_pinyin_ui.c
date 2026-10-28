#include "optional_name_pinyin_ui.h"

#include <assert.h>
#include <stddef.h>

static uint32_t PackForFixture(const char *text)
{
    uint32_t key = 0;
    unsigned length = 0;
    while (*text != '\0') {
        key = (key << 5) | (uint32_t)(*text - 'a' + 1);
        ++text;
        ++length;
    }
    return key << (5 * (6 - length));
}

int main(void)
{
    struct PinyinRow rows[] = {
        {PackForFixture("a"), 0, 1},
        {PackForFixture("ni"), 1, 35},
    };
    uint16_t tokens[36];
    struct PinyinTable table = {rows, tokens, 2, 36};
    struct NamePinyinUi state = {0};
    uint16_t keys[NAME_PINYIN_KEY_COUNT];
    uint16_t selected = 0;
    unsigned index;

    for (index = 0; index < 36; ++index)
        tokens[index] = (uint16_t)(0x9000 + index);

    NamePinyinBuildPage(&table, &state, keys);
    assert(keys[0] == 0x80b0 && keys[25] == 0x80c9);
    for (index = 26; index < NAME_PINYIN_KEY_COUNT; ++index)
        assert(keys[index] == 0x4073);

    state.row = 1;
    state.column = 3; /* N */
    assert(!NamePinyinAccept(&table, &state, &selected));
    assert(state.composition.length == 1 && state.composition.letters[0] == 'n');
    state.row = 0;
    state.column = 8; /* I */
    assert(!NamePinyinAccept(&table, &state, &selected));
    assert(state.composition.length == 2 && state.candidate_count == 30);
    assert(state.total_candidates == 35 && state.candidates[0] == 0x9001);
    assert(NamePinyinBackspace(&table, &state));
    assert(state.composition.length == 1 && state.composition.letters[0] == 'n');
    assert(state.row == 1 && state.column == 3);
    state.row = 0;
    state.column = 8;
    assert(!NamePinyinAccept(&table, &state, &selected));
    assert(state.composition.length == 2 && state.total_candidates == 35);

    NamePinyinBuildPage(&table, &state, keys);
    assert(keys[30] == 0x9001 && keys[59] == 0x901e);
    assert(!NamePinyinHandleSelectButton(&table, &state, 0x0001));
    assert(NamePinyinHandleSelectButton(&table, &state, 0x0004));
    assert(state.candidate_page == 1 && state.candidate_count == 5);
    NamePinyinBuildPage(&table, &state, keys);
    assert(keys[30] == 0x901f && keys[34] == 0x9023);
    for (index = 35; index < NAME_PINYIN_KEY_COUNT; ++index)
        assert(keys[index] == 0x4073);

    assert(NamePinyinHandleSelectButton(&table, &state, 0x0004));
    assert(state.candidate_page == 0 && state.candidate_count == 30);
    state.row = 3;
    state.column = 0;
    assert(NamePinyinAccept(&table, &state, &selected));
    assert(selected == 0x9001 && state.composition.length == 0);
    assert(state.candidate_page == 0 && state.total_candidates == 0);

    state.row = 1;
    state.column = 3;
    assert(!NamePinyinAccept(&table, &state, &selected));
    assert(NamePinyinBackspace(&table, &state));
    assert(state.composition.length == 0 && state.row == 0 && state.column == 0);
    assert(!NamePinyinBackspace(&table, &state));

    state.row = 2;
    state.column = 6; /* Z, the last valid cell in the third row. */
    NamePinyinMoveCursor(&table, &state, NAME_PINYIN_MOVE_RIGHT);
    assert(state.row == 2 && state.column == 0);
    return 0;
}
