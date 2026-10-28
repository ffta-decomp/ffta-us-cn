#include "optional_name_pinyin_ui.h"

enum {
    NAME_TOKEN_FIRST_LATIN = 0x80b0,
    NAME_TOKEN_TEXT_SPACE = 0x4073,
    NAME_PINYIN_LAST_LETTER = 25,
};

static uint16_t CellIndex(uint8_t row, uint8_t column)
{
    return (uint16_t)row * NAME_PINYIN_COLUMNS + column;
}

static int IsLetterCell(uint8_t row, uint8_t column)
{
    return row < NAME_PINYIN_LETTER_ROWS &&
           CellIndex(row, column) <= NAME_PINYIN_LAST_LETTER;
}

static void RefreshCandidates(const struct PinyinTable *table,
                              struct NamePinyinUi *state)
{
    struct PinyinPage page;

    page = PinyinLookup(table, state->composition.letters,
                        state->candidate_page, state->candidates,
                        NAME_PINYIN_CANDIDATES_PER_PAGE);
    state->total_candidates = page.total_candidates;
    state->candidate_count = (uint8_t)page.returned_candidates;
}

static int IsCandidateCell(const struct NamePinyinUi *state,
                           uint8_t row, uint8_t column)
{
    uint16_t index;
    if (row < NAME_PINYIN_LETTER_ROWS)
        return 0;
    index = (uint16_t)(row - NAME_PINYIN_LETTER_ROWS) *
            NAME_PINYIN_COLUMNS + column;
    return index < state->candidate_count;
}

void NamePinyinBuildPage(const struct PinyinTable *table,
                         struct NamePinyinUi *state, uint16_t *keys)
{
    uint16_t index;

    RefreshCandidates(table, state);
    for (index = 0; index < NAME_PINYIN_KEY_COUNT; ++index)
        keys[index] = NAME_TOKEN_TEXT_SPACE;

    for (index = 0; index < 26; ++index)
        keys[index] = (uint16_t)(NAME_TOKEN_FIRST_LATIN + index);
    for (index = 0; index < state->candidate_count; ++index)
        keys[NAME_PINYIN_LETTER_ROWS * NAME_PINYIN_COLUMNS + index] =
            state->candidates[index];
}

void NamePinyinMoveCursor(const struct PinyinTable *table,
                         struct NamePinyinUi *state,
                         enum NamePinyinMove direction)
{
    int row = state->row;
    int column = state->column;
    int attempt;

    RefreshCandidates(table, state);
    for (attempt = 0; attempt < NAME_PINYIN_KEY_COUNT; ++attempt) {
        switch (direction) {
        case NAME_PINYIN_MOVE_UP:
            row = (row + NAME_PINYIN_ROWS - 1) % NAME_PINYIN_ROWS;
            break;
        case NAME_PINYIN_MOVE_DOWN:
            row = (row + 1) % NAME_PINYIN_ROWS;
            break;
        case NAME_PINYIN_MOVE_LEFT:
            column = (column + NAME_PINYIN_COLUMNS - 1) % NAME_PINYIN_COLUMNS;
            break;
        case NAME_PINYIN_MOVE_RIGHT:
            column = (column + 1) % NAME_PINYIN_COLUMNS;
            break;
        }
        if (IsLetterCell((uint8_t)row, (uint8_t)column) ||
            IsCandidateCell(state, (uint8_t)row, (uint8_t)column)) {
            state->row = (uint8_t)row;
            state->column = (uint8_t)column;
            return;
        }
    }
}

int NamePinyinAccept(const struct PinyinTable *table,
                     struct NamePinyinUi *state, uint16_t *candidate_token)
{
    RefreshCandidates(table, state);
    if (IsLetterCell(state->row, state->column)) {
        char letter = (char)('a' + CellIndex(state->row, state->column));
        if (PinyinAppend(&state->composition, letter)) {
            state->candidate_page = 0;
            RefreshCandidates(table, state);
        }
        return 0;
    }
    if (candidate_token != 0 &&
        IsCandidateCell(state, state->row, state->column)) {
        uint16_t index = (uint16_t)(state->row - NAME_PINYIN_LETTER_ROWS) *
                         NAME_PINYIN_COLUMNS + state->column;
        *candidate_token = state->candidates[index];
        PinyinClear(&state->composition);
        state->candidate_page = 0;
        state->row = 0;
        state->column = 0;
        RefreshCandidates(table, state);
        return 1;
    }
    return 0;
}

int NamePinyinNextCandidatePage(const struct PinyinTable *table,
                                struct NamePinyinUi *state)
{
    if (state->total_candidates <= NAME_PINYIN_CANDIDATES_PER_PAGE)
        return 0;
    ++state->candidate_page;
    if ((uint16_t)state->candidate_page * NAME_PINYIN_CANDIDATES_PER_PAGE >=
        state->total_candidates)
        state->candidate_page = 0;
    RefreshCandidates(table, state);
    state->row = NAME_PINYIN_LETTER_ROWS;
    state->column = 0;
    while (!IsCandidateCell(state, state->row, state->column) &&
           state->column + 1 < NAME_PINYIN_COLUMNS)
        ++state->column;
    return state->candidate_count != 0;
}

int NamePinyinHandleSelectButton(const struct PinyinTable *table,
                                 struct NamePinyinUi *state,
                                 uint16_t pressed_buttons)
{
    if ((pressed_buttons & 0x0004) == 0)
        return 0;
    (void)NamePinyinNextCandidatePage(table, state);
    return 1;
}

int NamePinyinBackspace(const struct PinyinTable *table,
                        struct NamePinyinUi *state)
{
    if (!PinyinBackspace(&state->composition))
        return 0;
    state->candidate_page = 0;
    RefreshCandidates(table, state);
    if (state->composition.length == 0) {
        state->row = 0;
        state->column = 0;
    } else {
        uint8_t letter_index = (uint8_t)(
            state->composition.letters[state->composition.length - 1] - 'a');
        state->row = letter_index / NAME_PINYIN_COLUMNS;
        state->column = letter_index % NAME_PINYIN_COLUMNS;
    }
    return 1;
}
