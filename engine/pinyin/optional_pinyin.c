#include "optional_pinyin.h"

#include <stddef.h>

static uint32_t PackSpelling(const char *spelling)
{
    uint32_t packed = 0;
    unsigned length = 0;

    if (spelling == NULL)
        return 0;
    while (*spelling != '\0') {
        if (*spelling < 'a' || *spelling > 'z' || length == 6)
            return 0;
        packed = (packed << 5) | (uint32_t)(*spelling - 'a' + 1);
        ++length;
        ++spelling;
    }
    /* Left alignment gives lexicographic order for a fixed-width key. */
    return length == 0 ? 0 : packed << (5 * (6 - length));
}

struct PinyinPage PinyinLookup(const struct PinyinTable *table,
                               const char *spelling, uint16_t page,
                               uint16_t *output, uint16_t capacity)
{
    struct PinyinPage result = {0, 0};
    uint32_t key = PackSpelling(spelling);
    uint16_t left = 0;
    uint16_t right;

    if (key == 0 || table == NULL || table->rows == NULL ||
        table->tokens == NULL || (capacity != 0 && output == NULL))
        return result;
    right = table->row_count;
    while (left < right) {
        uint16_t middle = left + (right - left) / 2;
        uint32_t found = table->rows[middle].spelling;
        if (found < key)
            left = middle + 1;
        else
            right = middle;
    }
    if (left < table->row_count && table->rows[left].spelling == key) {
        const struct PinyinRow *row = &table->rows[left];
        uint32_t first = (uint32_t)row->first_candidate +
                         (uint32_t)page * capacity;
        uint16_t available;
        uint16_t index;

        if ((uint32_t)row->first_candidate + row->candidate_count >
            table->token_count)
            return result;
        result.total_candidates = row->candidate_count;
        if (capacity == 0 || first >=
            (uint32_t)row->first_candidate + row->candidate_count)
            return result;
        available = (uint16_t)((uint32_t)row->first_candidate +
                               row->candidate_count - first);
        result.returned_candidates = available < capacity ? available : capacity;
        for (index = 0; index < result.returned_candidates; ++index)
            output[index] = table->tokens[first + index];
    }
    return result;
}

void PinyinClear(struct PinyinComposition *composition)
{
    composition->length = 0;
    composition->letters[0] = '\0';
}

int PinyinAppend(struct PinyinComposition *composition, char letter)
{
    uint8_t length = composition->length;
    if (length >= 6 || letter < 'a' || letter > 'z')
        return 0;
    composition->letters[length] = letter;
    composition->letters[length + 1] = '\0';
    composition->length = length + 1;
    return 1;
}

int PinyinBackspace(struct PinyinComposition *composition)
{
    if (composition->length == 0)
        return 0;
    composition->letters[--composition->length] = '\0';
    return 1;
}
