"""Deterministic, same-size IPS patches for authenticated 16 MiB local inputs."""
EOF_OFFSET = int.from_bytes(b'EOF', 'big')


def encode_patch(before, after):
    if len(before) != len(after) or len(after) > 0x1000000:
        raise ValueError('IPS requires equal-size images of at most 16 MiB')
    output = bytearray(b'PATCH')
    cursor = 0
    while cursor < len(after):
        if before[cursor] == after[cursor]:
            cursor += 1
            continue
        start = cursor - 1 if cursor == EOF_OFFSET else cursor
        cursor += 1
        while cursor < len(after) and before[cursor] != after[cursor] and cursor - start < 65535:
            cursor += 1
        chunk = after[start:cursor]
        output += start.to_bytes(3, 'big') + len(chunk).to_bytes(2, 'big') + chunk
    return bytes(output + b'EOF')


def apply_patch(before, patch):
    if not patch.startswith(b'PATCH'):
        raise ValueError('Invalid IPS header')
    output = bytearray(before)
    cursor = 5
    while True:
        if cursor + 3 > len(patch):
            raise ValueError('Truncated IPS record')
        if patch[cursor:cursor + 3] == b'EOF':
            if cursor + 3 != len(patch):
                raise ValueError('Unsupported IPS footer')
            return bytes(output)
        if cursor + 5 > len(patch):
            raise ValueError('Truncated IPS size')
        offset = int.from_bytes(patch[cursor:cursor + 3], 'big')
        size = int.from_bytes(patch[cursor + 3:cursor + 5], 'big')
        cursor += 5
        if not size or cursor + size > len(patch) or offset + size > len(output):
            raise ValueError('Invalid or out-of-bounds IPS payload')
        output[offset:offset + size] = patch[cursor:cursor + size]
        cursor += size
