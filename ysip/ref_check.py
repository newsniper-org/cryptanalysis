#!/usr/bin/env python3
"""
YSip 독립 레퍼런스 (SPEC-draft.md 기준; Rust 구현을 베끼지 않고 사양만 보고 작성).
교차구현 KAT 검증용 — Rust `examples/gen_kat.rs` 출력과 bit-exact 일치해야 사양이 모호하지 않다.

실행: python3 ref_check.py            # KAT 벡터 출력 (Rust gen_kat 와 diff)
"""
M = (1 << 64) - 1
A, B = 8, 9
IV = [0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1]


def rotl(x, k):
    k %= 64
    return ((x << k) | (x >> (64 - k))) & M if k else x & M


def rotr(x, k):
    return rotl(x, (64 - k % 64) % 64)


def rar(x, y):
    return rotr((rotl(x, A) + y) & M, B)


def rnd(v):
    v0, v1, v2, v3 = v
    v0 = rar(v0, v1); v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32)
    v2 = rar(v2, v3); v3 = rotl(v3, 16); v3 ^= v2
    v0 = rar(v0, v3); v3 = rotl(v3, 21); v3 ^= v0
    v2 = rar(v2, v1); v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32)
    return [v0, v1, v2, v3]


def ysip(key16, c, d, data):
    k0 = int.from_bytes(key16[0:8], "little")
    k1 = int.from_bytes(key16[8:16], "little")
    v = [IV[0] ^ k0, IV[1] ^ k1, IV[2] ^ k0, IV[3] ^ k1]
    n = len(data)
    full = n - (n % 8)
    i = 0
    while i < full:
        m = int.from_bytes(data[i:i + 8], "little")
        v[3] ^= m
        for _ in range(c):
            v = rnd(v)
        v[0] ^= m
        i += 8
    tail = int.from_bytes(data[full:], "little")  # 잔여 (<8) LE
    b = ((n & 0xff) << 56) | tail
    v[3] ^= b
    for _ in range(c):
        v = rnd(v)
    v[0] ^= b
    v[2] ^= 0xff
    for _ in range(d):
        v = rnd(v)
    return (v[0] ^ v[1] ^ v[2] ^ v[3]) & M


KEYS = {
    "k00": bytes(16),
    "kff": bytes([0xff] * 16),
    "kseq": bytes(range(16)),
}
LENS = [0, 1, 7, 8, 9, 15, 16, 31, 32, 63, 64]


def msg(n):
    return bytes((i * 0x9d + 7) & 0xff for i in range(n))


if __name__ == "__main__":
    print("# YSip KAT (독립 Python 레퍼런스). 형식: variant key len = tag_u64_hex (tag_le_bytes_hex)")
    for vname, (c, d) in [("YSip-2-4", (2, 4)), ("YSip-3-6", (3, 6))]:
        for kname, key in KEYS.items():
            for n in LENS:
                t = ysip(key, c, d, msg(n))
                print(f"{vname} {kname} {n:2d} = {t:016x} ({t.to_bytes(8, 'little').hex()})")
