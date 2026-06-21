#!/usr/bin/env python3
"""Lean/fast: σ-on vs σ-off boomerang decay + the prob-1 trace. N modest so it finishes."""
import math
from boomerang_np import boomerang_rate, D, lg

diffs = {
    "MSB0": D([(0, 0x80)]),
    "MSB0+MSB4": D([(0, 0x80), (4, 0x80)]),
    "MSB0+MSB2": D([(0, 0x80), (2, 0x80)]),
    "MSB2+MSB6": D([(2, 0x80), (6, 0x80)]),
    "MSB0+MSB1": D([(0, 0x80), (1, 0x80)]),
    "ALLPLUS": D([(0, 0x80), (2, 0x80), (4, 0x80), (6, 0x80)]),
}
keys = list(diffs)


def scan(R, N, use_sigma):
    best = (0, None, None)
    for an in keys:
        for dn in keys:
            c, NN = boomerang_rate(R, diffs[an], diffs[dn], N, use_sigma=use_sigma)
            if c > best[0]:
                best = (c, an, dn)
    return best


if __name__ == "__main__":
    N = 1 << 20
    print(f"### WITH σ (recommended) best boomerang vs R, N=2^{int(math.log2(N))} ###")
    for R in [1, 2, 3, 4]:
        c, an, dn = scan(R, N, True)
        print(f"  R={R}: best a={an:10s} d={dn:10s} r={c}/{N} = 2^-{lg(c, N):.2f}")

    print(f"\n### prob-1 trace a=MSB0+MSB4 d=MSB0 vs R ###")
    for R in [1, 2, 3, 4]:
        c, NN = boomerang_rate(R, diffs["MSB0+MSB4"], diffs["MSB0"], N, use_sigma=True)
        print(f"  R={R}: r={c}/{N} = 2^-{lg(c, N):.2f}")

    Na = 1 << 18
    print(f"\n### ABLATION NO σ: best boomerang vs R, N=2^{int(math.log2(Na))} ###")
    print("# isolates σ's role: w/o σ does the free switch survive deeper?")
    for R in [1, 2, 3, 4, 5, 6]:
        c, an, dn = scan(R, Na, False)
        print(f"  R={R} (no σ): best a={an:10s} d={dn:10s} r={c}/{Na} = 2^-{lg(c, Na):.2f}")
