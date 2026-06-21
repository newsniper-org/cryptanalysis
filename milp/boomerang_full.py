#!/usr/bin/env python3
"""
yttrium-LM full boomerang over R = rb+rc rounds (n=8, w=8), and sandwich middle.
Imports faithful round from boomerang_bct.build.

Tests:
 (A) full boomerang return prob over R rounds, scanning candidate (a_in, d_out).
     Compare to straight-differential floor reference.
 (B) sandwich r over middle layer E_m = 1 round (the add+σ+π switch) with optimal
     diffs taken from the BCT-1 add entries, lifted through σ/π.
 (C) feistel-boomerang-switch (FBCT-style): does the broadcast t couple lanes so the
     switch differences must be simultaneously BCT-1 across all active lanes through
     the SAME S? Measure middle-layer return for multi-lane switch.

Honesty: empirical, n=8 reduced width; finite N => report log2 + raw counts.
"""
import random
import math
from boomerang_bct import build, SIG_ALL8, PI8, EPS8

N_DEFAULT = 1 << 20


def boomerang_prob(ctx, R, a_in, d_out, N, seed=0):
    rng = random.Random(seed)
    w = ctx['w']; M = ctx['M']; E = ctx['E']; Einv = ctx['Einv']
    cnt = 0
    for _ in range(N):
        x = [rng.randrange(M + 1) for _ in range(w)]
        xa = [(x[i] ^ a_in[i]) & M for i in range(w)]
        c1 = E(x, R); c2 = E(xa, R)
        c3 = [(c1[i] ^ d_out[i]) & M for i in range(w)]
        c4 = [(c2[i] ^ d_out[i]) & M for i in range(w)]
        p3 = Einv(c3, R); p4 = Einv(c4, R)
        if all(((p3[i] ^ p4[i]) & M) == a_in[i] for i in range(w)):
            cnt += 1
    return cnt, N


def sandwich_middle(ctx, rm, a_in, d_out, N, seed=0):
    """boomerang restricted to the middle rm rounds only (the switch region)."""
    return boomerang_prob(ctx, rm, a_in, d_out, N, seed)


def lg(p):
    return float('inf') if p <= 0 else -math.log2(p)


if __name__ == "__main__":
    n = 8
    red = 0x1D
    a, b = 8 % n, 9 % n  # = 0, 1
    ctx = build(n, red, a, b)
    M = ctx['M']; w = ctx['w']

    # sanity: roundtrip
    rng = random.Random(7)
    ok = True
    for _ in range(2000):
        x = [rng.randrange(M + 1) for _ in range(w)]
        if ctx['Einv'](ctx['E'](x, 5), 5) != x:
            ok = False; break
    print(f"[sanity] Einv∘E == id over 5 rounds: {ok}\n")

    def D(pairs):
        v = [0] * w
        for (lane, val) in pairs:
            v[lane] = val & M
        return v

    # ---- (B) sandwich middle: 1-round switch ----
    print("### (B) sandwich middle = 1 round; switch diffs from BCT-1 add entries ###")
    # MSB diff in single lane: ROTR_b shifts MSB; before add it is at xp MSB; after add
    # MSB add boomerang is BCT-1. Use a_in = MSB on lane 0, d_out scanned.
    N = 1 << 18
    cand_a = [D([(0, 0x80)]), D([(0, 0x80), (2, 0x80)]), D([(0, 0x01)]),
              D([(0, 0x80), (1, 0x80)])]
    cand_d = [D([(0, 0x80)]), D([(0, 0x01)]), D([(5, 0x80)]), D([(0, 0x80), (5, 0x80)]),
              D([(7, 0x40)])]
    for ai in cand_a:
        best = (0, None)
        for di in cand_d:
            c, NN = sandwich_middle(ctx, 1, ai, di, N)
            if c > best[0]:
                best = (c, di)
        c, di = best
        print(f"  a_in={['%02X' % v for v in ai]} -> best d_out={['%02X' % v for v in di]}"
              f"  r={c}/{N} = 2^-{lg(c / N):.2f}")

    # ---- (A) full boomerang over R = rb+rc ----
    print("\n### (A) full boomerang over R rounds (split rb=rc=R/2) ###")
    N = 1 << 20
    a_in = D([(0, 0x80)])
    d_out = D([(0, 0x80)])
    for R in [2, 3, 4, 5, 6]:
        c, NN = boomerang_prob(ctx, R, a_in, d_out, N)
        print(f"  R={R}: a=MSB0 d=MSB0  r={c}/{N} = 2^-{lg(c / N):.2f}")

    # scan a few d_out for R=4 to find best
    print("\n### (A') R=4 d_out scan (a_in=MSB lane0) ###")
    a_in = D([(0, 0x80)])
    best = (0, None)
    for lane in range(w):
        for val in [0x80, 0x40, 0x01, 0x02]:
            di = D([(lane, val)])
            c, NN = boomerang_prob(ctx, 4, a_in, di, 1 << 18)
            if c > best[0]:
                best = (c, di)
    c, di = best
    print(f"  best d_out={['%02X' % v for v in di]}  r={c}/{1 << 18} = 2^-{lg(c / (1 << 18)):.2f}")
