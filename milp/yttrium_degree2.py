#!/usr/bin/env python3
"""
yttrium-LM 대수 차수 성장 (정확 Möbius, numpy 가속) + 가역성 점검 + 최소차수 추적.

핵심: integral/cube distinguisher 의 결정자는 "출력비트의 (최소) ANF 차수가
입력차수 N-1 에 도달하는 라운드". 차수가 d면 (d+1)-차원 cube 합이 항상 0 (구별자).
가역치환이면 모든 출력비트는 균형(balanced) → 차수 ≤ N-1.
"""
import numpy as np


def make_round(n, w, red, sig_k, P, A, B, eps):
    M = (1 << n) - 1
    def rotl(x, k):
        k %= n
        return ((x << k) | (x >> (n - k))) & M if k else x & M
    def rotr(x, k):
        return rotl(x, (n - (k % n)) % n)
    def alpha(v):
        top = v >> (n - 1)
        return (((v << 1) & M) ^ (red if top else 0))
    def alfp(v, k):
        for _ in range(k):
            v = alpha(v)
        return v
    if n >= 8:
        TERMS = [(7 % n, 17 % n), (3 % n, 21 % n), (9 % n, 29 % n)]
    else:
        TERMS = [(1, 2 % n), (3 % n, (n - 1)), (2 % n, (n - 2) % n or 1)]
    def F(s):
        acc = 0
        for (r1, r2) in TERMS:
            acc ^= rotl(s, r1) & rotl(s, r2)
        return s ^ acc
    def rnd(words):
        xp = [rotl(words[i], A) for i in range(w)]
        S = 0
        for i in range(w):
            S = (S + xp[i]) & M if eps[i] > 0 else (S - xp[i]) & M
        t = F(S)
        y = [rotr((xp[i] + t) & M, B) for i in range(w)]
        y = [alfp(y[i], sig_k[i]) for i in range(w)]
        new = [y[P[i]] for i in range(w)]
        return new
    return rnd, M


def mobius_degrees(n, w, red, sig_k, P, A, B, eps, Rmax, verbose=True, label=""):
    N = n * w
    rnd, M = make_round(n, w, red, sig_k, P, A, B, eps)
    size = 1 << N
    # build identity mapping state array
    cur = np.arange(size, dtype=np.int64)
    out = []
    bijective = True
    popc = np.array([bin(i).count("1") for i in range(size)], dtype=np.int16)
    for R in range(1, Rmax + 1):
        nxt = np.empty(size, dtype=np.int64)
        for x in range(size):
            st = int(cur[x])
            ws = [(st >> (i * n)) & M for i in range(w)]
            ws2 = rnd(ws)
            v = 0
            for i in range(w):
                v |= (ws2[i] & M) << (i * n)
            nxt[x] = v
        cur = nxt
        if len(np.unique(cur)) != size:
            bijective = False
        # per-bit Möbius via numpy XOR butterfly
        maxdeg = 0
        mindeg = N
        degs = []
        for b in range(N):
            tt = ((cur >> b) & 1).astype(np.uint8)
            i = 1
            while i < size:
                # for indices with bit i set, XOR with index^i
                idx = np.arange(size)
                mask = (idx & i) != 0
                tt[mask] ^= tt[idx[mask] ^ i]
                i <<= 1
            nz = np.nonzero(tt)[0]
            d = int(popc[nz].max()) if nz.size else 0
            degs.append(d)
            maxdeg = max(maxdeg, d)
            mindeg = min(mindeg, d)
        out.append((maxdeg, mindeg, degs))
        if verbose:
            print(f"  R={R}: max_deg={maxdeg:3d}  min_deg={mindeg:3d}  bijective={bijective}  (N-1={N-1})")
    return out, N, bijective


if __name__ == "__main__":
    print(f"### yttrium-LM 축소폭 ANF 차수 성장 (정확 Möbius) ###\n")
    configs = [
        ("w2 n6", 6, 2, 0x43, [1, 2], [1, 0], 3, 4, [1, -1]),
        ("w2 n8 (A,B)=(8,9)", 8, 2, 0x1D, [1, 2], [1, 0], 8, 9, [1, -1]),
        ("w4 n4", 4, 4, 0x13, [1, 2, 3, 1], [3, 0, 1, 2], 1, 2, [1, -1, 1, -1]),
        ("w4 n5", 5, 4, 0x25, [1, 2, 3, 1], [3, 0, 1, 2], 2, 3, [1, -1, 1, -1]),
    ]
    for (lab, n, w, red, sk, P, A, B, eps) in configs:
        print(f"== {lab}: N={n*w} ==")
        mobius_degrees(n, w, red, sk, P, A, B, eps, 6, label=lab)
        print()
