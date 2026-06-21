#!/usr/bin/env python3
"""yttrium-large(u64,16-lane) per-round best-DP slope — reduced-width 검증.

GPU n=64 N=2^30은 R2(2^-21.5)서 fold-floor(~2^-23)에 닿아 slope 측정 불가.
reduced-width(n=16, 16-lane)로 특성-DP를 직접 카운트(floor 1/N) → slope 외삽 앵커.
(u32에서 reduced n=8 slope +7.4 ≈ GPU n=32 +7.7로 전이 검증된 기법.)

구조 = large.rs와 동형(워드폭만 n=16): 16-lane, ε=[+,−]×8, a/b=8/9,
F 3-term 오프셋 mod16=(7,1)(3,5)(9,13), σ all-16 α^k k=[1..15,17] GF(2^16) red 0x2B,
π=[7,12,1,6,11,0,5,10,15,4,9,14,3,8,13,2]. 16×16=256bit 출력을 4×u64로 pack→np.unique.
실행: python3 verify_large_slope.py
"""
import numpy as np, math

n = 16
M = (1 << n) - 1
red = 0x2B  # GF(2^16) primitive
W = 16
EPS = [1 if i % 2 == 0 else -1 for i in range(W)]
PI = [7, 12, 1, 6, 11, 0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2]
SIGK = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17]
FT = [(7, 1), (3, 5), (9, 13)]  # mod 16
a, b = 8, 9


def rotl(x, k):
    k %= n
    return ((x << k) | (x >> (n - k))) & M if k else x & M


def rotr(x, k):
    return rotl(x, (n - (k % n)) % n)


def alpha(v):
    top = (v >> (n - 1)) & 1
    return (((v << np.uint32(1)) & M) ^ (top * red)) & M


def alfp(v, k):
    for _ in range(k):
        v = alpha(v)
    return v


def F(s):
    acc = s.copy()
    for (p, q) in FT:
        acc = acc ^ (rotl(s, p) & rotl(s, q))
    return acc & M


def rnd(state):
    xp = [rotl(state[i], a) for i in range(W)]
    S = np.zeros_like(xp[0])
    for i in range(W):
        S = (S + xp[i]) & M if EPS[i] > 0 else (S - xp[i]) & M
    t = F(S)
    y = [rotr((xp[i] + t) & M, b) for i in range(W)]
    y = [alfp(y[i], SIGK[i]) for i in range(W)]
    return [y[PI[i]] for i in range(W)]


def permute(state, R):
    s = list(state)
    for _ in range(R):
        s = rnd(s)
    return s


def emp_worst(R, N, seed=0):
    rng = np.random.default_rng(seed)
    msb = 1 << (n - 1)
    plus = [i for i in range(W) if i % 2 == 0]
    minus = [i for i in range(W) if i % 2 == 1]
    cands = []
    # MSB-쌍(같은부호 인접쌍) 일부 + 단일비트 — 판별력 있는 소수만
    for grp in (plus, minus):
        for i in range(0, len(grp) - 1, 2):
            d = [0] * W
            d[grp[i]] = msb
            d[grp[i + 1]] = msb
            cands.append(tuple(d))
    for bit in (0, n - 1):
        d = [0] * W
        d[0] = 1 << bit
        cands.append(tuple(d))
    best = 0.0
    for d in cands:
        x = [rng.integers(0, 1 << n, size=N, dtype=np.uint32) for _ in range(W)]
        y = [(x[i] ^ np.uint32(d[i])) for i in range(W)]
        ox = permute(x, R)
        oy = permute(y, R)
        # 256-bit 출력차를 64-bit로 XOR-fold (floor~1/N; fold 충돌 N^2/2^64 무시가능)
        key = np.zeros(N, dtype=np.uint64)
        for i in range(W):
            key ^= ((ox[i] ^ oy[i]).astype(np.uint64) << np.uint64(n * (i % 4)))
        _, counts = np.unique(key, return_counts=True)
        top = counts.max() / N
        if top > best:
            best = top
    return best


if __name__ == "__main__":
    N = 600_000
    print(f"yttrium-large reduced(n=16,16-lane) worst-δ best-DP (N={N}, floor~2^-{math.log2(N):.0f}):")
    prev = None
    slopes = []
    for R in range(1, 5):
        p = emp_worst(R, N, seed=R)
        w = -math.log2(p) if p > 0 else math.log2(N)
        sl = ""
        if prev is not None:
            slopes.append(w - prev)
            sl = f"  dW=+{w-prev:.2f}"
        print(f"  R={R}: 2^-{w:.2f}{sl}")
        prev = w
    if slopes:
        print(f"\n대표 slope(R2→R3 등 floor 전): {slopes}")
        print("→ 이 slope를 GPU n=64 R2 앵커(2^-21.5)와 결합해 R_b(2^-128) 외삽.")
