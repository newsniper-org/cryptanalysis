#!/usr/bin/env python3
"""
Focused DL confirmation: take the SINGLE best (delta,beta) found by the search
and measure its DL correlation at large N (no multiple-testing floor inflation),
across R, to extract the clean DL slope and project depth.

Round = exact replica (verify_n8_slope.py reduced n=8, a=0 b=1, all-8 sigma).
Also tests a few hand-picked candidate (delta,beta) pairs in the MSB-pair class.
"""
import numpy as np, math, sys
from dl_yttrium import make_round, parity64, SIGK

def dl_corr_fixed(perm, M, n, D, beta, R, N, seed):
    rng = np.random.default_rng(seed)
    x = [rng.integers(0, M + 1, size=N, dtype=np.uint64) for _ in range(8)]
    y = [x[i] ^ np.uint64(D[i]) for i in range(8)]
    ox = perm(x, R); oy = perm(y, R)
    pb = np.zeros(N, dtype=np.uint64)
    for i in range(8):
        if beta[i]: pb ^= (ox[i] ^ oy[i]) & np.uint64(beta[i])
    p = parity64(pb); s = int(p.sum())
    return abs(1.0 - 2.0 * s / N)

if __name__ == "__main__":
    n = 8; a, b = 0, 1; red = 0x1D
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 1 << 24
    Rmax = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    perm, M = make_round(n, a, b, red, SIGK)
    msb = 1 << (n - 1)
    # candidate DL pairs: worst-DP-class input (same-sign MSB pair), output single-bit / low-weight masks
    cands = [
        # (name, delta, beta)
        ("d=MSB{0,2}, b=bit0.lane0", [msb,0,msb,0,0,0,0,0], [1,0,0,0,0,0,0,0]),
        ("d=MSB{0,2}, b=MSB.lane0",  [msb,0,msb,0,0,0,0,0], [msb,0,0,0,0,0,0,0]),
        ("d=MSB{0,2}, b=lw(1,_,_,8)",[msb,0,msb,0,0,0,0,0], [1,0,0,8,0,0,0,0]),
        ("d=MSB{0,4}, b=bit0.lane0", [msb,0,0,0,msb,0,0,0], [1,0,0,0,0,0,0,0]),
        ("d=MSB{1,3}, b=bit0.lane0", [0,msb,0,msb,0,0,0,0], [1,0,0,0,0,0,0,0]),
    ]
    floor = 1.0 / math.sqrt(N)
    print(f"### Focused DL slope, n={n} N=2^{math.log2(N):.0f} floor~2^-{-math.log2(floor):.1f}, (a,b)=({a},{b}) ###\n")
    for name, D, beta in cands:
        print(f"-- {name} --", flush=True)
        prev = None
        for R in range(1, Rmax + 1):
            c = dl_corr_fixed(perm, M, n, D, beta, R, N, seed=1000 + R)
            w = -math.log2(c) if c > 0 else float('inf')
            sl = "" if prev is None else f"  dW={w-prev:+.2f}"
            flag = "  <=floor" if c <= floor * 3 else ""
            print(f"   R={R}: |C_DL|=2^-{w:.2f}{sl}{flag}", flush=True)
            prev = w
        print()
