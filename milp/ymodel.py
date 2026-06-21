#!/usr/bin/env python3
"""Bit-exact Python model of yttrium permute() (full round w/ RC, framing, F, sigma, pi).
Validated against cargo example dump_permute vectors."""
N_LANE = 32
W = 8
MASK = (1 << N_LANE) - 1
RED = 0x400007
SIG_K = [1, 2, 3, 4, 5, 6, 7, 9]
P_PI = [7, 4, 1, 6, 3, 0, 5, 2]
ROT_A = 8
ROT_B = 9
EPS_PLUS = [True, False, True, False, True, False, True, False]
SHA256_K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]


def rc(r):
    return SHA256_K[r] if r < 64 else (SHA256_K[r % 64] ^ (r & MASK))


def rotl(x, k):
    k %= N_LANE
    return ((x << k) | (x >> (N_LANE - k))) & MASK if k else x & MASK


def rotr(x, k):
    return rotl(x, (N_LANE - (k % N_LANE)) % N_LANE)


def alpha(y):
    top = y >> (N_LANE - 1)
    return ((y << 1) & MASK) ^ (RED if top else 0)


def alpha_pow(y, k):
    for _ in range(k):
        y = alpha(y)
    return y


def f(s):
    acc = s
    for (a, b) in [(7, 17), (3, 21), (9, 29)]:
        acc ^= rotl(s, a) & rotl(s, b)
    return acc & MASK


def zerosum_reduce(xp):
    s = 0
    for i in range(W):
        if EPS_PLUS[i]:
            s = (s + xp[i]) & MASK
        else:
            s = (s - xp[i]) & MASK
    return s


def round_full(state, r):
    st = list(state)
    st[r % W] ^= rc(r)
    xp = [rotl(st[i], ROT_A) for i in range(W)]
    s = zerosum_reduce(xp)
    t = f(s)
    y = [0] * W
    for i in range(W):
        v = rotr((xp[i] + t) & MASK, ROT_B)
        y[i] = alpha_pow(v, SIG_K[i])
    return [y[P_PI[i]] for i in range(W)]


def permute(state, rounds):
    st = list(state)
    for r in range(rounds):
        st = round_full(st, r)
    return st


_VECTORS = [
    ([0x01234567, 0x89abcdef, 0xdeadbeef, 0xcafebabe, 1, 2, 3, 0xffffffff], 1,
     [0xd3641be1, 0xc91a422d, 0x0a72e415, 0x24a9083d, 0x34e2f6e2, 0x3f170f19, 0x9a7484bd, 0x68ad8c2d]),
    ([0x01234567, 0x89abcdef, 0xdeadbeef, 0xcafebabe, 1, 2, 3, 0xffffffff], 8,
     [0x8c301736, 0xe54a47dd, 0x5e8b08ef, 0x85180b63, 0x25f2abca, 0x7b5428fc, 0x5a9a41c7, 0x92971d87]),
    ([0, 0, 0, 0, 0, 0, 0, 0], 3,
     [0x2f0aca8b, 0xa26d72aa, 0x99e2311c, 0x311a1cf1, 0xc4123df6, 0x0e745cb1, 0xfff21ca5, 0x3a845264]),
    ([1, 0, 0, 0, 0, 0, 0, 0], 6,
     [0xcf66fa90, 0xfdef477f, 0x21f02e58, 0x694a9770, 0x98d138f9, 0x15c5da92, 0xe541b7e9, 0xc48709c2]),
]


def selftest():
    ok = True
    for inp, r, exp in _VECTORS:
        got = permute(inp, r)
        if got != exp:
            ok = False
            print(f"MISMATCH R={r}: got {[hex(x) for x in got]} exp {[hex(x) for x in exp]}")
    return ok


if __name__ == "__main__":
    print("model selftest vs cargo dump_permute:", "PASS" if selftest() else "FAIL")
