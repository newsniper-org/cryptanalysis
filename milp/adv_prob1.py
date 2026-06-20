#!/usr/bin/env python3
"""
Adversarial lens: prob1-subspace. THE core claim of the design.

The proposal claims additive prob-1 S-invariant subspaces die at R*=2~3, dismissing the
GF(2)-LA proxy (which still reports R*~8-9) as "irrelevant because actual additive pass
prob ~ 0.5".

I attack from several angles:
 (A) Independently measure additive prob-1 inactive subspace depth (full exhaustive small n).
     A prob-1 inactive diff d at round R: for ALL x, the output diff after R rounds is the
     SAME constant (input d propagates deterministically AND keeps dS=0 each round).
     Actually the proposal's definition: d survives if dS=0 prob-1 each round (=> dt=0 =>
     round acts linearly on d). Let me measure BOTH:
       (A1) "dS=0 at round 1 for all x" = additive-inactive 1-round diffs.
       (A2) iterated: a diff that keeps dS=0 every round for R rounds AND propagates
            deterministically (prob-1 differential characteristic through the round).
 (B) Look for HIGH-probability (not prob-1) iterated differentials / invariants that the
     prob-1 metric misses. Measure best 2-round differential prob over all single-active diffs
     exhaustively at small n.
 (C) The dangerous case the proposal flags itself: "single rho => additive survivors don't
     die". Verify that distinct-rho actually helps, and check whether the SPECIFIC proposed
     rho has accidental structure.
"""
import random, itertools
from adv_invert import build_round, mk, make_F

def additive_inactive_1round(n,w,rho,eps):
    """All nonzero diffs d such that dS=0 for ALL x (additive). dS = sum eps_i*ROTL_rho(x_i^d_i)
    - sum eps_i*ROTL_rho(x_i). Since ROTL is GF(2)-linear AND we then take signed modular sum,
    dS depends on x in general (carries). prob-1 dS=0 requires the carry-difference to vanish
    for all x."""
    m,rotl,_=mk(n)
    def Sval(state):
        s=0
        for i in range(w): s=(s+eps[i]*rotl(state[i],rho[i]))%(1<<n)
        return s
    total=1<<(n*w)
    survivors=[]
    # exhaustive over diffs; for each diff check all x (small)
    full = total<=(1<<20)
    for c in range(1,total):
        D=tuple((c>>(i*n))&m for i in range(w))
        ok=True
        if full:
            xs=range(total)
        else:
            xs=[random.randint(0,total-1) for _ in range(4000)]
        for cx in xs:
            x=tuple((cx>>(i*n))&m for i in range(w))
            xd=tuple(x[i]^D[i] for i in range(w))
            if Sval(xd)!=Sval(x):
                ok=False; break
        if ok: survivors.append(D)
    return survivors

def best_2round_diff(n,w,rho,beta,eps,sigma,red,P):
    """Exhaustive best 2-round differential probability over all nonzero input diffs (small n).
    For each input diff, push the FULL input space through 2 rounds, find the most frequent
    output diff."""
    rnd,_,_,M=build_round(n,w,rho,beta,eps,sigma,red,P)
    def rnd2(st): return rnd(rnd(st,0),1)
    total=1<<(n*w)
    if total>(1<<18): return None
    best=0; bestd=None; besto=None
    for c in range(1,total):
        D=tuple((c>>(i*n))&M for i in range(w))
        cnt={}
        for cx in range(total):
            x=tuple((cx>>(i*n))&M for i in range(w))
            xd=tuple(x[i]^D[i] for i in range(w))
            od=tuple(rnd2(x)[i]^rnd2(xd)[i] for i in range(w))
            cnt[od]=cnt.get(od,0)+1
        mx=max(cnt.values());
        if mx>best:
            best=mx; bestd=D; besto=max(cnt,key=cnt.get)
    return best/total, bestd, besto

if __name__=="__main__":
    random.seed(5)
    SIG=[(0,1),(2,3),(4,5),(6,7)]
    PPI=[7,4,1,6,3,0,5,2]
    EPS=[1,-1,1,-1,1,-1,1,-1]
    RHO_full=[0,5,11,17,23,3,13,29]

    print("=== (A1) additive prob-1 inactive 1-round diffs (full structure, small n) ===")
    for n,red in [(3,0x3),(4,0x3),(5,0x5)]:
        rho=[r%n for r in RHO_full]
        surv=additive_inactive_1round(n,8,rho,EPS)
        print(f"  n={n} w=8 rho={rho}: #1-round additive-inactive diffs = {len(surv)}")
        if surv and len(surv)<=6:
            for s in surv: print(f"      {tuple(hex(z) for z in s)}")

    print("\n=== (C) compare distinct-rho vs single-rho (additive survivors) ===")
    for n,red in [(4,0x3)]:
        rho_d=[r%n for r in RHO_full]
        rho_s=[1]*8  # single (non-distinct) rho
        sd=additive_inactive_1round(n,8,rho_d,EPS)
        ss=additive_inactive_1round(n,8,rho_s,EPS)
        print(f"  n={n}: distinct-rho 1-round survivors={len(sd)}  single-rho={len(ss)}")

    print("\n=== (B) best 2-round differential prob (exhaustive, very small) ===")
    for (n,w,rho,beta,eps,sigma,red,P) in [
        (3,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
        (4,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
    ]:
        res=best_2round_diff(n,w,rho,beta,eps,sigma,red,P)
        if res:
            p,d,o=res
            import math
            print(f"  n={n} w={w}: best 2R DP={p:.5f} (2^{math.log2(p):.2f})  din={tuple(hex(z) for z in d)} dout={tuple(hex(z) for z in o)}")
