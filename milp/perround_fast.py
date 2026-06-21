#!/usr/bin/env python3
"""Fast per-round best-DP decay at small width (w=2, fully exhaustive, all R)."""
import math
from adv_deep_prob1 import build, all_states

def best_DP_full(n, w, rho, beta, eps, sigma, red, P, R):
    rnd, m = build(n, w, rho, beta, eps, sigma, red, P)
    states = list(all_states(n, w))
    img = list(states)
    for _ in range(R):
        img = [rnd(s) for s in img]
    M = (1 << n) - 1
    total = 1 << (n * w)
    def pack(t):
        v = 0
        for i in range(w):
            v |= t[i] << (i * n)
        return v
    out = [pack(img[i]) for i in range(len(states))]
    best = 0; bd = None
    for cD in range(1, total):
        # state index = cD's complement walk; pair (s, s^D)
        cnt = {}
        for s in range(total):
            sd = s ^ cD
            od = out[s] ^ out[sd]
            cnt[od] = cnt.get(od, 0) + 1
        mx = max(cnt.values())
        if mx > best:
            best = mx; bd = cD
    return best / total, bd

if __name__ == "__main__":
    # NOTE: pack uses index = sum w_i<<(i*n); states are in that exact order, so s==packed index.
    cfgs = [
        # all-8-style sigma compressed to w lanes; w=2 -> two lanes both sigma'd
        ("n4w2 sig-both", 4,2,[1,1],2,[1,-1],[(0,1),(1,2)],0x13,[1,0]),
        ("n5w2 sig-both", 5,2,[1,2],3,[1,-1],[(0,1),(1,2)],0x25,[1,0]),
        ("n6w2 sig-both", 6,2,[1,2],3,[1,-1],[(0,1),(1,2)],0x43,[1,0]),
        ("n7w2 sig-both", 7,2,[2,2],3,[1,-1],[(0,1),(1,2)],0x83,[1,0]),
        ("n8w2 sig-both", 8,2,[2,3],3,[1,-1],[(0,1),(1,2)],0x11d,[1,0]),
    ]
    print("###### w=2 exhaustive per-round best-DP (zero-sum 2-lane, both lanes sigma) ######")
    for name,n,w,rho,beta,eps,sig,red,P in cfgs:
        print(f"-- {name} (state {n*w}-bit) --")
        prev=None
        Rmax = 5 if n*w<=14 else 4
        for R in range(1,Rmax+1):
            p,bd = best_DP_full(n,w,rho,beta,eps,sig,red,P,R)
            l2 = math.log2(p) if p>0 else float('-inf')
            slope = "" if prev is None else f"  Δw={(-l2)-prev:+.2f}"
            print(f"   R={R}: bestDP=2^{l2:6.2f}  D=0x{bd:x}{slope}")
            prev = -l2
        print()
