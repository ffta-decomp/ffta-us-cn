#ifndef OPTIONAL_NAME_PINYIN_UI_H
#define OPTIONAL_NAME_PINYIN_UI_H

#include "optional_pinyin.h"

enum {
    NAME_PINYIN_COLUMNS = 10,
    NAME_PINYIN_ROWS = 6,
    NAME_PINYIN_LETTER_ROWS = 3,
    NAME_PINYIN_CANDIDATE_ROWS = 3,
    NAME_PINYIN_CANDIDATES_PER_PAGE = 30,
    NAME_PINYIN_KEY_COUNT = 60,
};

enum NamePinyinMove {
    NAME_PINYIN_MOVE_UP,
    NAME_PINYIN_MOVE_DOWN,
    NAME_PINYIN_MOVE_LEFT,
    NAME_PINYIN_MOVE_RIGHT,
};

struct NamePinyinUi {
    struct PinyinComposition composition;
    uint16_t candidates[NAME_PINYIN_CANDIDATES_PER_PAGE];
    uint8_t row;
    uint8_t column;
    uint16_t candidate_page;
    uint8_t candidate_count;
    uint16_t total_candidates;
};

/* Build all sixty renderer tokens. The first 26 are A-Z and the final 30
 * candidate tokens occupy the lower three rows. Empty cells use text space. */
void NamePinyinBuildPage(const struct PinyinTable *table,
                         struct NamePinyinUi *state, uint16_t *keys);

/* Apply one D-pad move, maintaining a legal letter or candidate cell. */
void NamePinyinMoveCursor(const struct PinyinTable *table,
                         struct NamePinyinUi *state,
                         enum NamePinyinMove direction);

/* A accepts a letter or returns a selected candidate token. Returns one only
 * when candidate_token was written; letter acceptance returns zero. */
int NamePinyinAccept(const struct PinyinTable *table,
                     struct NamePinyinUi *state, uint16_t *candidate_token);

/* SELECT advances to the next 30-character candidate page, wrapping at end.
 * It returns zero when the current spelling has no second page. */
int NamePinyinNextCandidatePage(const struct PinyinTable *table,
                                struct NamePinyinUi *state);

/* Dispatch the SELECT keypad edge (bit 2). Returns one when SELECT is
 * consumed, even when the current spelling has only one candidate page. */
int NamePinyinHandleSelectButton(const struct PinyinTable *table,
                                 struct NamePinyinUi *state,
                                 uint16_t pressed_buttons);

/* B first edits the pending spelling. Returns zero when it is already empty. */
int NamePinyinBackspace(const struct PinyinTable *table,
                        struct NamePinyinUi *state);

#endif
