#!/usr/bin/env python3
"""
yttrium per-round best-DP decay (reduced-width, exhaustive) — DIMENSION: differential decay+composition.

Goal: measure how worst-case differential probability (best-DP over all nonzero input diffs)
decays PER ROUND at reduced width, to extract a per-round weight slope w(R)=-log2(DP_R),
then extrapolate to full width (n=32,w=8) and compose for collision paths (a)/(b).

Round model = yttrium-LM (matches adv_deep_prob1.build and yttrium_lm_diff.cu perm):
  xp_i = ROTL_a(x_i); S = Σ ε_i xp_i (mod 2^n), ε=[+,-,...]; t=F(S);
  y_i  = ROTR_b(xp_i ⊞ t); y_i = α^{k_i} y_i (all-8 σ); π permute.

We scale rotations with n (a=ceil(n/4), b=a+1 mimic ROTL8/ROTR9 at n=32) but ALSO run the
true (a,b)=(8,9) where n>=... not meaningful at small n, so we report scaled+fixed both.
"""
import math, random
from adv_deep_prob1 import build, all_states, mk

def best_DP_full(n, w, rho, beta, eps, sigma, red, P, R):
    """Exhaustive best-DP over ALL nonzero input diffs and ALL states. Feasible n*w<=16."""
    rnd, m = build(n, w, rho, beta, eps, sigma, red, P)
    states = list(all_states(n, w))
    # iterate R rounds once per state
    img = list(states)
    for _ in range(R):
        img = [rnd(s) for s in img]
    idx = {s: i for i, s in enumerate(states)}
    M = (1 << n) - 1
    total = 1 << (n * w)
    # precompute packed output for fast xor
    def pack(t):
        v = 0
        for i in range(w):
            v |= t[i] << (i * n)
        return v
    out = [pack(img[i]) for i in range(len(states))]
    best = 0; bd = None; bo = None
    for cD in range(1, total):
        D = [(cD >> (i * n)) & M for i in range(w)]
        cnt = {}
        for i, s in enumerate(states):
            sd = tuple(s[k] ^ D[k] for k in range(w))
            od = out[i] ^ out[idx[sd]]
            cnt[od] = cnt.get(od, 0) + 1
        mx = max(cnt.values())
        if mx > best:
            best = mx; bd = tuple(D); bo = max(cnt, key=cnt.get)
    return best / total, bd, bo

def best_DP_sampled(n, w, rho, beta, eps, sigma, red, P, R, Dlist, nsamp):
    """For larger width: estimate DP for a fixed list of input diffs via random-state sampling.
       Returns per-diff best output-diff fraction."""
    rnd, m = build(n, w, rho, beta, eps, sigma, red, P)
    M = (1 << n) - 1
    def rR(s):
        for _ in range(R):
            s = rnd(s)
        return s
    results = []
    rng = random.Random(0xC0FFEE)
    for D in Dlist:
        cnt = {}
        for _ in range(nsamp):
            s = tuple(rng.getrandbits(n) for _ in range(w))
            sd = tuple(s[k] ^ D[k] for k in range(w))
            od = tuple(rR(s)[i] ^ rR(sd)[i] for i in range(w))
            cnt[od] = cnt.get(od, 0) + 1
        mx = max(cnt.values())
        results.append((D, mx / nsamp))
    return results

def all8_sigma():
    return [(0,1),(1,2),(2,3),(3,5),(4,7),(5,11),(6,13),(7,17)]

def part_sigma_04():
    return [(0,1),(4,3)]

if __name__ == "__main__":
    PI8 = [7,4,1,6,3,0,5,2]
    EPS8 = [1,-1,1,-1,1,-1,1,-1]
    print("###### yttrium per-round best-DP decay (reduced width, EXHAUSTIVE) ######")
    print("# state n*w<=16 fully exhaustible. (a,b) scaled to mimic ROTL/ROTR ratio.\n")

    # n=4,w=4 : state 16-bit, w=4 (half the real width). a=1,b=2 (ratio ~ 8:9 scaled).
    # eps zero-sum needs even w. red 0x13 primitive deg4? use 0x13=x^4+x+1 (primitive).
    configs = [
        # name, n, w, rho(list a), beta b, eps, sigma, red, P
        ("n4w4 all-8sig", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(1,2),(2,3),(3,1)],0x13,[3,0,1,2]),
        ("n4w4 sig{0,2}", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x13,[3,0,1,2]),
    ]
    for name,n,w,rho,beta,eps,sig,red,P in configs:
        print(f"-- {name} (state {n*w}-bit) --")
        prev = None
        for R in [1,2,3,4]:
            p,bd,bo = best_DP_full(n,w,rho,beta,eps,sig,red,P,R)
            l2 = math.log2(p) if p>0 else float('-inf')
            slope = "" if prev is None else f"  Δw={(-l2)-prev:+.2f}"
            print(f"   R={R}: bestDP=2^{l2:6.2f} ({p:.6f})  D={tuple(hex(z) for z in bd)}{slope}")
            prev = -l2 if p>0 else prev
        print()
