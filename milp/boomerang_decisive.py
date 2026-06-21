#!/usr/bin/env python3
"""
Decisive yttrium-LM boomerang measurements (lean/fast). Reuses round from boomerang_np.
Focus: the rounds-of-coverage question.
  - 1,2,3,4-round switch boomerang, best over a focused diff grid (incl. the prob-1
    zero-sum MSB-pair found in (B): a=MSB0+MSB4 -> d=MSB0).
  - ablation NO σ: how many MORE rounds the switch survives w/o σ (isolates σ's role).
Smaller N=2^20, focused diffs => completes fast.
"""
import math
import numpy as np
from boomerang_np import boomerang_rate, D, lg

# focused diff grid: the prob-1 pair + single MSB + a couple multilane
diffs = {
    "MSB0": D([(0, 0x80)]),
    "MSB0+MSB4": D([(0, 0x80), (4, 0x80)]),  # zero-sum same-sign pair (ε both +)
    "MSB0+MSB2": D([(0, 0x80), (2, 0x80)]),  # also both ε=+
    "MSB2+MSB6": D([(2, 0x80), (6, 0x80)]),
    "MSB0+MSB1": D([(0, 0x80), (1, 0x80)]),  # opposite-sign pair (ε +,-)
    "ALLPLUS_MSB": D([(0, 0x80), (2, 0x80), (4, 0x80), (6, 0x80)]),
}
keys = list(diffs)


def scan(R, N, use_sigma=True):
    best = (0, None, None)
    for an in keys:
        for dn in keys:
            c, NN = boomerang_rate(R, diffs[an], diffs[dn], N, use_sigma=use_sigma)
            if c > best[0]:
                best = (c, an, dn)
    return best, N


if __name__ == "__main__":
    print("### WITH σ (recommended round): best boomerang over focused grid ###")
    for R in [1, 2, 3, 4]:
        N = 1 << 20 if R <= 2 else 1 << 22
        (c, an, dn), NN = scan(R, N, use_sigma=True)
        print(f"  R={R}: best a={an:14s} d={dn:10s} r={c}/{NN} = 2^-{lg(c, NN):.2f}")

    print("\n### specifically a=MSB0+MSB4, d=MSB0 across R (the prob-1 1rnd switch) ###")
    for R in [1, 2, 3, 4, 5]:
        N = 1 << 22
        c, NN = boomerang_rate(R, diffs["MSB0+MSB4"], diffs["MSB0"], N, use_sigma=True)
        print(f"  R={R}: r={c}/{NN} = 2^-{lg(c, NN):.2f}")

    print("\n### ABLATION: NO σ — how deep does the switch stay prob-1? ###")
    for R in [1, 2, 3, 4, 5, 6]:
        N = 1 << 20
        (c, an, dn), NN = scan(R, N, use_sigma=False)
        print(f"  R={R} (no σ): best a={an:14s} d={dn:10s} r={c}/{NN} = 2^-{lg(c, NN):.2f}")
