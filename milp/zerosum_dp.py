#!/usr/bin/env python3
"""
Does the prob-1 round-1-inactive bit23 class seed a HIGH-PROBABILITY multi-round
differential better than generic best-DP (which sets R_b)? §10-D / round-count claims
best-DP slope ~ +7.7 bits/round, R_b≈9 for 2^-64. If the bit23 seed gives a markedly
flatter slope, it would PRESSURE the small variants (R_b=4,8).

Measure empirically (full nonlinear round, full 32-bit lanes) the best output-difference
probability after R rounds starting from bit23-even-support seeds, vs a random low-weight seed.
We use a large MC sample and take the most frequent output difference (DP lower bound).
Honesty: MC only lower-bounds the dominant DP; floor ~ 1/sqrt(trials). We report the
round-1->round-2 transition (where bit23 starts prob-1) which is the meaningful comparison.
"""
import numpy as np
from collections import Counter
from ssm_unobservable import (W, rotl, rotr, alpha_pow, P_PI, SIG_K, ROT_A, ROT_B, MASK)

N = 32
EPS = [1, -1, 1, -1, 1, -1, 1, -1]


def F(s):
    acc = s
    for (a, b) in [(7, 17), (3, 21), (9, 29)]:
        acc ^= rotl(s, a) & rotl(s, b)
    return acc & MASK


def rnd(words):
    xp = [rotl(words[i], ROT_A) for i in range(W)]
    S = 0
    for i in range(W):
        S = (S + xp[i]) & MASK if EPS[i] > 0 else (S - xp[i]) & MASK
    t = F(S)
    y = [rotr((xp[i] + t) & MASK, ROT_B) for i in range(W)]
    y = [alpha_pow(y[i], SIG_K[i]) for i in range(W)]
    return [y[P_PI[i]] for i in range(W)]


def best_dp(seed, R, trials=200000, seed_rng=0):
    rng = np.random.default_rng(seed_rng)
    cnt = Counter()
    for _ in range(trials):
        x = [int(rng.integers(0, 1 << N)) for _ in range(W)]
        xd = [x[i] ^ seed[i] for i in range(W)]
        for _ in range(R):
            x = rnd(x)
            xd = rnd(xd)
        od = tuple(x[i] ^ xd[i] for i in range(W))
        cnt[od] += 1
    od, c = cnt.most_common(1)[0]
    return c / trials, od


def main():
    import math
    print("=== best-DP from bit23-prob-1 seed vs generic low-weight, full nonlinear round ===")
    print(f"(MC floor ~ 2^-{0.5*math.log2(200000):.1f}; meaningful for R=1,2)\n")

    seeds = {
        "bit23@{0,2} (prob-1 R1 inactive)": [1 << 23, 0, 1 << 23, 0, 0, 0, 0, 0],
        "bit23 all-8 (prob-1 R1 inactive)": [1 << 23] * 8,
        "MSB@{0,1} (prob-1/2 inactive)": [1 << 31, 1 << 31, 0, 0, 0, 0, 0, 0],
        "generic single-bit lane0 bit0": [1, 0, 0, 0, 0, 0, 0, 0],
        "generic low-weight bit5 lane3": [0, 0, 0, 1 << 5, 0, 0, 0, 0],
    }
    for name, sd in seeds.items():
        line = f"  {name:38s}: "
        for R in (1, 2, 3):
            p, od = best_dp(sd, R, trials=200000, seed_rng=R)
            w = -math.log2(p) if p > 0 else float("inf")
            line += f"R{R}=2^-{w:4.1f}  "
        print(line)
    print("\nInterpretation: at R1 the bit23 seeds are 2^-0 (prob-1, Δt=0 => pure linear A).")
    print("At R2 they should COLLAPSE toward generic (F activates) — compare slope.")


if __name__ == "__main__":
    main()
