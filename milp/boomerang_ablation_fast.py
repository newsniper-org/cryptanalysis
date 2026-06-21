#!/usr/bin/env python3
"""FAST no-σ ablation at N=2^16 + the add-BCT->σ mechanism (cheap). Finishes ~1min."""
import math
from boomerang_np import boomerang_rate, D, lg

diffs = {
    "MSB0": D([(0, 0x80)]),
    "MSB0+MSB4": D([(0, 0x80), (4, 0x80)]),
    "MSB0+MSB2": D([(0, 0x80), (2, 0x80)]),
    "MSB2+MSB6": D([(2, 0x80), (6, 0x80)]),
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
    N = 1 << 16
    print(f"### ABLATION NO σ: best boomerang vs R, N=2^{int(math.log2(N))} (fast) ###")
    for R in [1, 2, 3, 4, 5, 6]:
        c, an, dn = scan(R, N, False)
        print(f"  R={R} (no σ): best a={an:10s} d={dn:10s} r={c}/{N} = 2^-{lg(c, N):.2f}")
    print(f"\n### WITH σ same N for apples-to-apples ###")
    for R in [1, 2, 3]:
        c, an, dn = scan(R, N, True)
        print(f"  R={R} (σ on): best a={an:10s} d={dn:10s} r={c}/{N} = 2^-{lg(c, N):.2f}")
