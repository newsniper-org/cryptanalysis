#!/usr/bin/env python3
"""
Per-round best-DP SLOPE via sampled DP over a broad delta-set, at n=8/n=16 (real-ish field).
Mirrors yttrium_lm_diff.cu delta-set: single-bit, 2-bit, MSB-pairs (zero-sum same-sign).
Sampling estimates DP for each delta; we take worst-delta per R and the per-round slope.

Honest: sampled DP has a floor ~ 1/nsamp. We use nsamp up to 2^20 -> floor ~2^-20.
The slope (per-round weight gain) before hitting floor is the extrapolation basis.
"""
import math, random
from adv_deep_prob1 import build, all_states

def make_round(n,w,rho,beta,eps,sigma,red,P):
    rnd,m=build(n,w,rho,beta,eps,sigma,red,P)
    return rnd

def sampled_DP(rnd,n,w,D,R,nsamp,seed):
    rng=random.Random(seed)
    def rR(s):
        for _ in range(R): s=rnd(s)
        return s
    cnt={}
    for _ in range(nsamp):
        s=tuple(rng.getrandbits(n) for _ in range(w))
        sd=tuple(s[k]^D[k] for k in range(w))
        a=rR(s); b=rR(sd)
        od=tuple(a[i]^b[i] for i in range(w))
        cnt[od]=cnt.get(od,0)+1
    mx=max(cnt.values())
    return mx/nsamp

def build_deltas(n,w):
    M=(1<<n)-1; msb=1<<(n-1)
    Ds=[]
    # single-bit, a few positions per lane
    pos=[0, n//4, n//2, n-1]
    for wd in range(w):
        for p in pos:
            D=[0]*w; D[wd]=1<<p; Ds.append(tuple(D))
    # MSB pairs across lanes (zero-sum same-sign candidates): lanes (0,2),(0,1),(1,3)...
    for a in range(w):
        for b in range(a+1,w):
            D=[0]*w; D[a]=msb; D[b]=msb; Ds.append(tuple(D))
    # bit23-analog pair (ROTR shifted MSB): use bit n-1-? approx -> lane pair with mid bit
    mid=1<<(n//2)
    for a in range(w):
        for b in range(a+1,w):
            D=[0]*w; D[a]=mid; D[b]=mid; Ds.append(tuple(D))
    return Ds

if __name__=="__main__":
    PI8=[7,4,1,6,3,0,5,2]
    EPS8=[1,-1,1,-1,1,-1,1,-1]
    ALL8=[(0,1),(1,2),(2,3),(3,5),(4,7),(5,11),(6,13),(7,17)]
    SIG04=[(0,1),(4,3)]
    # n=8, w=8: real width, 1/4 word-size. red 0x11d (x^8+x^4+x^3+x^2+1 primitive). a=2,b=3 (ratio~8:9).
    # n=16,w=8: half word-size. red 0x1002d primitive deg16. a=4,b=5.
    cfgs=[
        ("n8 w8 all-8 (a,b)=(2,3)",  8, 8,[2]*8,3,EPS8,ALL8, 0x11d, PI8),
        ("n8 w8 sig{0,4}",            8, 8,[2]*8,3,EPS8,SIG04,0x11d, PI8),
        ("n16 w8 all-8 (a,b)=(4,5)",16, 8,[4]*8,5,EPS8,ALL8, 0x1002d, PI8),
    ]
    NS = 1<<16   # 65536 samples -> floor ~ 2^-16
    print(f"###### sampled worst-delta best-DP per round (nsamp=2^{int(math.log2(NS))}, floor~2^-{int(math.log2(NS))}) ######\n")
    for name,n,w,rho,beta,eps,sig,red,P in cfgs:
        rnd=make_round(n,w,rho,beta,eps,sig,red,P)
        Ds=build_deltas(n,w)
        print(f"-- {name}  ({len(Ds)} deltas, state {n*w}-bit) --")
        prev=None
        for R in [1,2,3,4]:
            worst=0; wD=None
            for D in Ds:
                p=sampled_DP(rnd,n,w,D,R,NS, hash((name,R))&0xffffffff)
                if p>worst: worst=p; wD=D
            l2=math.log2(worst) if worst>0 else float('-inf')
            slope="" if prev is None else f"  Δw={(-l2)-prev:+.2f}"
            print(f"   R={R}: worst-δ DP=2^{l2:6.2f}  δ={tuple(hex(z) for z in wD)}{slope}", flush=True)
            prev=-l2
        print()
