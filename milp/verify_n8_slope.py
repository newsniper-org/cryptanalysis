#!/usr/bin/env python3
"""Independent verification of n=8 reduced-width per-round worst-delta best-DP decay."""
import numpy as np, math

n = 8
M = (1 << n) - 1
red = 0x1D
EPS = [1, -1, 1, -1, 1, -1, 1, -1]
PI = [7, 4, 1, 6, 3, 0, 5, 2]
# DISTINCT powers (= full-width all-8 정신). 반복-power [1,2,3,1,2,3,1,2] 는 plus-pair
# lanes(0,6)에 가짜 prob-1 고정점을 만드는 artifact 라 금지(적대검증 지적, 정정).
SIGK = [1, 2, 3, 5, 7, 11, 13, 17]
Fterms = [(1, 4), (2, 6), (3, 7)]
a, b = 8 % n, 9 % n  # = 0, 1


def rotl(x, k):
    k %= n
    if k == 0:
        return x & M
    return ((x << k) | (x >> (n - k))) & M


def rotr(x, k):
    return rotl(x, (n - (k % n)) % n)


def alpha(v):
    top = (v >> (n - 1)) & 1
    return (((v << 1) & M) ^ (top * red)) & M


def alfp(v, k):
    for _ in range(k):
        v = alpha(v)
    return v


def F(s):
    acc = s.copy()
    for (p, q) in Fterms:
        acc = acc ^ (rotl(s, p) & rotl(s, q))
    return acc & M


def rnd(state):
    xp = [rotl(state[i], a) for i in range(8)]
    S = np.zeros_like(xp[0])
    for i in range(8):
        S = (S + xp[i]) & M if EPS[i] > 0 else (S - xp[i]) & M
    t = F(S)
    y = [rotr((xp[i] + t) & M, b) for i in range(8)]
    y = [alfp(y[i], SIGK[i]) for i in range(8)]
    return [y[PI[i]] for i in range(8)]


def permute(state, R):
    s = list(state)
    for _ in range(R):
        s = rnd(s)
    return s


def emp_worst(R, N, seed=0):
    rng = np.random.default_rng(seed)
    msb = 1 << (n - 1)
    plus = [0, 2, 4, 6]
    minus = [1, 3, 5, 7]
    cands = []
    for grp in (plus, minus):
        for i in range(4):
            for j in range(i + 1, 4):
                d = [0] * 8
                d[grp[i]] = msb
                d[grp[j]] = msb
                cands.append(tuple(d))
    for bit in (0, n // 2, n - 1):
        d = [0] * 8
        d[0] = 1 << bit
        cands.append(tuple(d))
    best = 0.0
    bestd = None
    for d in cands:
        x = [rng.integers(0, 1 << n, size=N, dtype=np.uint64) for _ in range(8)]
        y = [(x[i] ^ np.uint64(d[i])) for i in range(8)]
        ox = permute(x, R)
        oy = permute(y, R)
        # pack 8 lanes x 8 bits = 64-bit key in uint64
        key = np.zeros(N, dtype=np.uint64)
        for i in range(8):
            key |= ((ox[i] ^ oy[i]).astype(np.uint64) << np.uint64(n * i))
        _, counts = np.unique(key, return_counts=True)
        top = counts.max() / N
        if top > best:
            best = top
            bestd = d
    return best, bestd


if __name__ == "__main__":
    N = 4_000_000
    print(f"n=8 reduced-width worst-delta best-DP (vectorized, N={N}):")
    prev = None
    for R in range(1, 7):
        p, _ = emp_worst(R, N, seed=R)
        w = -math.log2(p)
        sl = "" if prev is None else f"  dW=+{w-prev:.2f}"
        print(f"  R={R}: 2^-{w:.2f}{sl}")
        prev = w
    print(f"  sample floor ~ 2^-{math.log2(N):.1f}")
