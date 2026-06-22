#!/usr/bin/env python3
"""Cross-axis probe of (A,B) candidates for linear corr + RX-prob.
Tests whether the differential ranking (8,9)~strong-cluster vs (12,29) strongest
is contradicted on linear / rotational axes. Reuses exact methodology from
ysip_linear.py and ysip_rotational.py but sweeps multiple (A,B)."""
import math
import numpy as np

M = np.uint64(0xFFFFFFFFFFFFFFFF)


def rotl(x, k):
    k %= 64
    return x if k == 0 else ((x << np.uint64(k)) | (x >> np.uint64(64 - k))) & M


def rotr(x, k):
    return rotl(x, (64 - (k % 64)) % 64)


def ysip_round(v, mode, A, B):
    v0, v1, v2, v3 = v

    def comb(x, y):
        return (x + y) & M if mode == "siphash" else rotr((rotl(x, A) + y) & M, B)

    v0 = comb(v0, v1); v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32)
    v2 = comb(v2, v3); v3 = rotl(v3, 16); v3 ^= v2
    v0 = comb(v0, v3); v3 = rotl(v3, 21); v3 ^= v0
    v2 = comb(v2, v1); v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32)
    return [v0, v1, v2, v3]


def runR(v, R, mode, A, B):
    for _ in range(R):
        v = ysip_round(v, mode, A, B)
    return v


def bits_pm(words):
    N = words[0].shape[0]
    out = np.empty((N, 256), dtype=np.int8)
    for w in range(4):
        x = words[w]
        for b in range(64):
            out[:, w * 64 + b] = ((x >> np.uint64(b)) & np.uint64(1)).astype(np.int8)
    return 1 - 2 * out


def best_corr(R, mode, A, B, N, seed=0):
    rng = np.random.default_rng(seed)
    x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
    Xpm = bits_pm([a.copy() for a in x]).astype(np.float32)
    y = runR([a.copy() for a in x], R, mode, A, B)
    Ypm = bits_pm(y).astype(np.float32)
    C = (Xpm.T @ Ypm) / N
    return float(np.abs(C).max())


def rx_prob(gamma, R, mode, A, B, N, seed=0):
    rng = np.random.default_rng(seed)
    x = [rng.integers(0, 1 << 64, size=N, dtype=np.uint64) for _ in range(4)]
    xr = [rotl(x[i], gamma) for i in range(4)]
    cx = runR([a.copy() for a in x], R, mode, A, B)
    cxr = runR([a.copy() for a in xr], R, mode, A, B)
    match = np.ones(N, dtype=bool)
    for i in range(4):
        match &= (cxr[i] == rotl(cx[i], gamma))
    return int(match.sum()) / N


def best_rx(R, mode, A, B, gammas, N, seed=0):
    best = (0.0, None)
    for g in gammas:
        p = rx_prob(g, R, mode, A, B, N, seed=seed)
        if p > best[0]:
            best = (p, g)
    return best


CANDS = [(8, 9), (16, 21), (12, 29), (7, 16), (8, 21)]

if __name__ == "__main__":
    print("=== LINEAR best 1-bit corr (N=2^20, lower=stronger) ===")
    N = 1 << 20
    print(f"  floor~2^-{-math.log2(1/math.sqrt(N)):.1f}")
    hdr = "  R  | " + " | ".join(f"{a},{b}".rjust(10) for a, b in CANDS)
    print(hdr)
    for R in range(1, 4):
        cells = []
        for (A, B) in CANDS:
            c = best_corr(R, "ysip", A, B, N, seed=R + 100 * A + B)
            cells.append(f"2^-{-math.log2(c):.2f}".rjust(10))
        print(f"  {R}  | " + " | ".join(cells))

    print("\n=== RX-prob best (N=2^18, higher p=weaker) ===")
    N = 1 << 18
    gammas = [1, 2, 3, 4, 8, 13, 16, 17, 21, 32]
    print(hdr)
    for R in range(1, 4):
        cells = []
        for (A, B) in CANDS:
            p, g = best_rx(R, "ysip", A, B, gammas, N, seed=R + 100 * A + B)
            floor = 3.0 / N
            s = "<=fl" if p <= floor else f"2^-{-math.log2(p):.2f}"
            cells.append(s.rjust(10))
        print(f"  {R}  | " + " | ".join(cells))
