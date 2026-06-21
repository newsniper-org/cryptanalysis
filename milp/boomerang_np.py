#!/usr/bin/env python3
"""
Vectorized (numpy) yttrium-LM boomerang/sandwich at n=8, w=8.
Faithful to yttrium_lm_diff.cu round; uint32 arrays masked to n bits.

Outputs:
  [sanity] roundtrip
  (B) 1-round and 2-round sandwich-middle boomerang return rate (the switch region)
  (A) full R-round boomerang return rate vs R
  ABLATIONS: no-σ, broadcast-off (per-lane t), non-zero-sum reduction
to pinpoint which algebra interaction governs the switch.

Honesty: empirical with N samples; report raw count + 2^-rate. n=8 reduced width.
"""
import numpy as np
import math

N_BITS = 8
M = (1 << N_BITS) - 1
RED = 0x1D
A, B = 8 % N_BITS, 9 % N_BITS  # 0,1
PI8 = [7, 4, 1, 6, 3, 0, 5, 2]
PINV = [0] * 8
for _i in range(8):
    PINV[PI8[_i]] = _i
SIGK = [1, 2, 3, 5, 7, 11, 13, 17]
EPS = [1, -1, 1, -1, 1, -1, 1, -1]
FTERMS = [(7, 17), (3, 21), (9, 29)]


def rotl(x, k):
    k %= N_BITS
    if k == 0:
        return x & M
    return ((x << k) | (x >> (N_BITS - k))) & M


def rotr(x, k):
    return rotl(x, (N_BITS - (k % N_BITS)) % N_BITS)


def alpha(v):
    top = (v >> (N_BITS - 1)) & 1
    return (((v << 1) & M) ^ (top * RED)) & M


def alpha_inv(v):
    # red bit0==1 required
    odd = (v & 1).astype(bool)
    res = np.where(odd, ((v ^ RED) >> 1) | (1 << (N_BITS - 1)), v >> 1)
    return res & M


def alfp(v, k):
    for _ in range(k):
        v = alpha(v)
    return v


def alfp_inv(v, k):
    for _ in range(k):
        v = alpha_inv(v)
    return v


def F(s):
    acc = np.zeros_like(s)
    for (p, q) in FTERMS:
        acc ^= rotl(s, p) & rotl(s, q)
    return (s ^ acc) & M


def rnd(state, broadcast=True, use_sigma=True, eps=EPS):
    # state: (w=8, N) uint
    xp = [rotl(state[i], A) for i in range(8)]
    if broadcast:
        S = np.zeros_like(xp[0], dtype=np.int64)
        for i in range(8):
            S = S + xp[i].astype(np.int64) if eps[i] > 0 else S - xp[i].astype(np.int64)
        S = (S & M).astype(state.dtype)
        t = F(S)
        tv = [t] * 8
    else:
        tv = [F(xp[i]) for i in range(8)]
    y = [rotr((xp[i] + tv[i]) & M, B) for i in range(8)]
    if use_sigma:
        for lane in range(8):
            y[lane] = alfp(y[lane], SIGK[lane])
    out = np.empty_like(state)
    for i in range(8):
        out[i] = y[PI8[i]]
    return out


def rnd_inv(state, use_sigma=True, eps=EPS):
    # inverse of broadcast-true round
    y = np.empty_like(state)
    for i in range(8):
        y[PI8[i]] = state[i]
    if use_sigma:
        for lane in range(8):
            y[lane] = alfp_inv(y[lane], SIGK[lane])
    v = [rotl(y[i], B) for i in range(8)]
    S = np.zeros_like(v[0], dtype=np.int64)
    for i in range(8):
        S = S + v[i].astype(np.int64) if eps[i] > 0 else S - v[i].astype(np.int64)
    S = (S & M).astype(state.dtype)
    t = F(S)
    xp = [(v[i] - t) & M for i in range(8)]
    out = np.empty_like(state)
    for i in range(8):
        out[i] = rotr(xp[i], A)
    return out


def E(state, R, **kw):
    for _ in range(R):
        state = rnd(state, **kw)
    return state


def Einv(state, R, **kw):
    for _ in range(R):
        state = rnd_inv(state, **kw)
    return state


def boomerang_rate(R, a_in, d_out, N, use_sigma=True, eps=EPS, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.integers(0, M + 1, size=(8, N), dtype=np.uint16)
    a = np.array(a_in, dtype=np.uint16).reshape(8, 1)
    d = np.array(d_out, dtype=np.uint16).reshape(8, 1)
    xa = x ^ a
    c1 = E(x, R, use_sigma=use_sigma, eps=eps)
    c2 = E(xa, R, use_sigma=use_sigma, eps=eps)
    p3 = Einv((c1 ^ d) & M, R, use_sigma=use_sigma, eps=eps)
    p4 = Einv((c2 ^ d) & M, R, use_sigma=use_sigma, eps=eps)
    ok = np.all(((p3 ^ p4) & M) == a, axis=0)
    return int(ok.sum()), N


def lg(c, N):
    return float('inf') if c == 0 else -math.log2(c / N)


def D(pairs):
    v = [0] * 8
    for (lane, val) in pairs:
        v[lane] = val & M
    return v


if __name__ == "__main__":
    print("yttrium-LM boomerang (n=8 reduced width, numpy). A,B=", A, B)
    # sanity
    rng = np.random.default_rng(1)
    x = rng.integers(0, M + 1, size=(8, 5000), dtype=np.uint16)
    rt = np.array_equal(Einv(E(x, 6), 6), x)
    print(f"[sanity] Einv∘E==id over 6 rounds: {rt}\n")

    diffs = [D([(0, 0x80)]), D([(0, 0x01)]), D([(3, 0x80)]),
             D([(0, 0x80), (4, 0x80)]), D([(0, 0x80), (1, 0x80)]),
             D([(0, 0x80), (2, 0x80)]), D([(2, 0x80), (6, 0x80)])]
    names = ["MSB0", "lsb0", "MSB3", "MSB0+MSB4", "MSB0+MSB1", "MSB0+MSB2", "MSB2+MSB6"]
    N = 1 << 22

    print(f"### (B) 1-round switch boomerang (full recommended round), N=2^{int(math.log2(N))} ###")
    for ai, an in zip(diffs, names):
        best = (0, None)
        for di, dn in zip(diffs, names):
            c, NN = boomerang_rate(1, ai, di, N)
            if c > best[0]:
                best = (c, dn)
        print(f"  a={an:10s} best d={best[1]:10s}  r={best[0]}/{N} = 2^-{lg(best[0], N):.2f}")

    print(f"\n### (B') 2-round switch boomerang, N=2^{int(math.log2(N))} ###")
    best = (0, None, None)
    for ai, an in zip(diffs, names):
        for di, dn in zip(diffs, names):
            c, NN = boomerang_rate(2, ai, di, N)
            if c > best[0]:
                best = (c, an, dn)
    print(f"  best a={best[1]} d={best[2]}  r={best[0]}/{N} = 2^-{lg(best[0], N):.2f}")

    print(f"\n### (A) full boomerang vs R (a=MSB0, d=MSB0), N=2^{int(math.log2(N))} ###")
    for R in [1, 2, 3, 4, 5]:
        c, NN = boomerang_rate(R, D([(0, 0x80)]), D([(0, 0x80)]), N)
        print(f"  R={R}: r={c}/{N} = 2^-{lg(c, N):.2f}")

    print(f"\n### (A') full boomerang vs R, best over diff grid, N=2^20 ###")
    Ns = 1 << 20
    for R in [2, 3, 4]:
        best = (0, None, None)
        for ai, an in zip(diffs, names):
            for di, dn in zip(diffs, names):
                c, NN = boomerang_rate(R, ai, di, Ns)
                if c > best[0]:
                    best = (c, an, dn)
        print(f"  R={R}: best a={best[1]} d={best[2]} r={best[0]}/{Ns} = 2^-{lg(best[0], Ns):.2f}")

    print(f"\n### ABLATION 1: NO σ — 1,2,3-round switch, N=2^20 ###")
    for R in [1, 2, 3]:
        best = (0, None, None)
        for ai, an in zip(diffs, names):
            for di, dn in zip(diffs, names):
                c, NN = boomerang_rate(R, ai, di, 1 << 20, use_sigma=False)
                if c > best[0]:
                    best = (c, an, dn)
        print(f"  R={R} (no σ): best a={best[1]} d={best[2]} r={best[0]}/{1 << 20} = 2^-{lg(best[0], 1 << 20):.2f}")

    # (non-zero-sum reduction omitted: it is non-invertible per yttrium_lm_invert.py,
    #  so the inverse-boomerang is ill-defined. Zero-sum is a hard structural requirement.)
