#!/usr/bin/env python3
"""
DL best-beta-per-round (adaptive output mask = captures the DL hull) at large N.
Worst delta class (same-sign MSB pairs), single-bit betas (64) exhaustive => clean floor.
This is the operative DL distinguisher correlation: max_beta |E[(-1)^{beta.(P(x)^P(x+d))}]|.

n=8 exact replica. Reports best-DL per round + which (delta,beta) achieves it.
Multiple-testing floor for 12 deltas x 64 betas ~ sqrt(2 ln(768))/sqrt(N).
"""
import numpy as np, math, sys
from dl_yttrium import make_round, SIGK

def run(N, Rmax, n=8, a=0, b=1, red=0x1D):
    perm, M = make_round(n, a, b, red, SIGK)
    msb = 1 << (n - 1)
    plus = [0, 2, 4, 6]; minus = [1, 3, 5, 7]
    deltas = []
    for grp in (plus, minus):
        for i in range(4):
            for j in range(i + 1, 4):
                d = [0] * 8; d[grp[i]] = msb; d[grp[j]] = msb; deltas.append(tuple(d))
    floor = math.sqrt(2 * math.log(12 * 64)) / math.sqrt(N)
    print(f"### DL best-beta(single-bit) per round, n={n} N=2^{math.log2(N):.0f} ###")
    print(f"# multiple-testing floor ~ 2^-{-math.log2(floor):.1f} (12 deltas x 64 betas)\n", flush=True)
    prev = None
    for R in range(1, Rmax + 1):
        best = 0.0; binfo = None
        rng = np.random.default_rng(500 + R)
        for D in deltas:
            x = [rng.integers(0, M + 1, size=N, dtype=np.uint64) for _ in range(8)]
            y = [x[i] ^ np.uint64(D[i]) for i in range(8)]
            ox = perm(x, R); oy = perm(y, R)
            for bl in range(8):
                dl = (ox[bl] ^ oy[bl]) & np.uint64(M)
                for bb in range(n):
                    s = int(((dl >> np.uint64(bb)) & np.uint64(1)).sum())
                    c = abs(1.0 - 2.0 * s / N)
                    if c > best: best = c; binfo = (D, bl, bb)
        w = -math.log2(best) if best > 0 else float('inf')
        sl = "" if prev is None else f"  dW={w-prev:+.2f}"
        flag = "  <=floor(upper bound)" if best <= floor * 2 else ""
        print(f"R={R}: best-DL=2^-{w:.2f}{sl}{flag}  @delta_lanes={[hex(z) for z in binfo[0] if z]} outlane={binfo[1]} outbit={binfo[2]}", flush=True)
        prev = w

if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 1 << 24
    Rmax = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    run(N, Rmax)
