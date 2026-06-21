#!/usr/bin/env python3
"""
Does the prob-1 fixed-point (seen at w=2) vanish as width grows to w=4, w=8?
This is THE question for collision paths (a)/(b): the worst-case high-DP differential.

We exhaustively search for prob-1 (DP=1) single-round AND R-round inactive diffs at:
  w=2 (state small), w=4 (state n*4), and sample-check w=8.
Then measure best-DP decay at w=4 with restricted but broad delta-sets.
"""
import math, random
from adv_deep_prob1 import build, all_states

def prob1_Rround(n,w,rho,beta,eps,sigma,red,P,R,maxstates=None):
    """Exhaustive over D if n*w<=16; returns prob-1 (DP=1) diffs at R rounds."""
    rnd,m=build(n,w,rho,beta,eps,sigma,red,P)
    M=(1<<n)-1
    states=list(all_states(n,w))
    if maxstates and len(states)>maxstates:
        rng=random.Random(1); states=[tuple(rng.getrandbits(n) for _ in range(w)) for _ in range(maxstates)]
    def rR(s):
        for _ in range(R): s=rnd(s)
        return s
    imgcache={}
    def IR(s):
        if s not in imgcache: imgcache[s]=rR(s)
        return imgcache[s]
    found=[]
    for cD in range(1,1<<(n*w)):
        D=tuple((cD>>(i*n))&M for i in range(w))
        o0=None;ok=True
        for s in states:
            sd=tuple(s[k]^D[k] for k in range(w))
            od=tuple(IR(s)[i]^IR(sd)[i] for i in range(w))
            if o0 is None:o0=od
            elif od!=o0:ok=False;break
        if ok:found.append((D,o0))
    return found

if __name__=="__main__":
    print("###### prob-1 fixed-point vs WIDTH (does it vanish at w=4?) ######\n")
    # w=2 (reproduce), w=4 (real-ish). all-8-style sigma = every lane sigma'd.
    cfgs=[
        ("n4w2 both-sig", 4,2,[1,1],2,[1,-1],[(0,1),(1,2)],0x13,[1,0], 2),
        ("n4w4 all-lane-sig", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(1,2),(2,3),(3,1)],0x13,[3,0,1,2], 2),
        ("n4w4 sig{0,2} (partial)", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x13,[3,0,1,2], 2),
    ]
    for name,n,w,rho,beta,eps,sig,red,P,Rmax in cfgs:
        print(f"-- {name} (state {n*w}-bit) --")
        for R in range(1,Rmax+1):
            f=prob1_Rround(n,w,rho,beta,eps,sig,red,P,R)
            print(f"   R={R}: #prob-1(DP=1) diffs = {len(f)}", end="")
            if f and len(f)<=6:
                print("  ", [tuple(hex(z) for z in D) for D,_ in f])
            else:
                print()
        print()
