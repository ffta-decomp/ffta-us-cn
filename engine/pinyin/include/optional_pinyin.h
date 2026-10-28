#ifndef OPTIONAL_PINYIN_H
#define OPTIONAL_PINYIN_H

#include <stdint.h>

/* This optional reader consumes ROM-resident tables generated from displayable
 * FFTA glyph tokens. It has no dependency on the retail name editor. */
struct PinyinRow {
    uint32_t spelling;
    uint16_t first_candidate;
    uint16_t candidate_count;
};

struct PinyinTable {
    const struct PinyinRow *rows;
    const uint16_t *tokens;
    uint16_t row_count;
    uint16_t token_count;
};

struct PinyinPage {
    uint16_t total_candidates;
    uint16_t returned_candidates;
};

/* Exact, lowercase full pinyin only: 1-6 ASCII letters. Invalid text or an
 * absent spelling returns an empty page. A caller chooses a page and bounded
 * output capacity; no state, heap, or file access is used. */
struct PinyinPage PinyinLookup(const struct PinyinTable *table,
                               const char *spelling, uint16_t page,
                               uint16_t *output, uint16_t capacity);

/* Fixed six-letter composition for a GBA UI adapter. No tones or prefixes. */
struct PinyinComposition {
    char letters[7];
    uint8_t length;
};

void PinyinClear(struct PinyinComposition *composition);
int PinyinAppend(struct PinyinComposition *composition, char letter);
int PinyinBackspace(struct PinyinComposition *composition);

#endif
