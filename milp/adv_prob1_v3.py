#!/usr/bin/env python3
"""
Deeper adversarial probing (independent), small n exhaustive + targeted full-n.

(D) Exhaustive best R-round differential probability over ALL nonzero input diffs, small n.
    This catches HIGH-probability (not necessarily prob-1) iterated differentials/invariants
    that the prob-1 subspace metric ignores. If best 2R/3R DP stays close to 1, the design has
    a high-prob invariant despite prob-1 subspace dying at R=2.

(E) Verify the R=1 prob-1 MSB-inactive survivors at full n=32 empirically: do they actually
    pass round-1 with prob 1 as a differential? (sanity on the model.)

(F) Iterated additive-inactive (author's core metric) reimplemented independently at small n,
    exhaustive, to cross-check the claimed R*=2~3 and survivor counts.
"""
import random, math
from adv_yttrium_check import build, mk, make_F, make_alpha, make_alpha_inv

def best_Rround_DP(n,w,rho,beta,eps,sigma,red,P,R):
    rnd,inv,Sval,m=build(n,w,rho,eps,sigma,P,beta,red)
    def rndR(st):
        for r in range(R): st=rnd(st,rc=0,rl=r%w)
        return st
    total=1<<(n*w)
    best=0; bd=None; bo=None
    for c in range(1,total):
        D=tuple((c>>(i*n))&m for i in range(w))
        cnt={}
        for cx in range(total):
            x=tuple((cx>>(i*n))&m for i in range(w))
            xd=tuple(x[i]^D[i] for i in range(w))
            od=tuple(rndR(x)[i]^rndR(xd)[i] for i in range(w))
            cnt[od]=cnt.get(od,0)+1
        mx=max(cnt.values())
        if mx>best: best=mx; bd=D; bo=max(cnt,key=cnt.get)
    return best/total, bd, bo

def additive_inactive_iter(n,w,rho,beta,eps,sigma,red,P,Rmax):
    """independent reimpl: prob-1 additive-inactive differential characteristic depth.
       survivor at R: nonzero D s.t. over ALL x the round maps D -> a fixed D' with ΔS=0 each step."""
    rnd,inv,Sval,m=build(n,w,rho,eps,sigma,P,beta,red)
    total=1<<(n*w); full=(n*w)<=16
    def xs():
        if full:
            for c in range(total): yield tuple((c>>(i*n))&m for i in range(w))
        else:
            for _ in range(3000): yield tuple(random.randint(0,m) for _ in range(w))
    # R=1: ΔS=0 for all x
    surv=[]
    for c in range(1,total):
        D=tuple((c>>(i*n))&m for i in range(w))
        if all(Sval(tuple(x[i]^D[i] for i in range(w)))==Sval(x) for x in xs()):
            surv.append(c)
    res={1:len(surv)}; cur=surv; Rstar=1 if not surv else None
    for R in range(2,Rmax+1):
        nxt=set()
        for c in cur:
            D=tuple((c>>(i*n))&m for i in range(w)); outd=None; ok=True
            for x in xs():
                od=tuple(rnd(x)[i]^rnd(tuple(x[j]^D[j] for j in range(w)))[i] for i in range(w))
                if outd is None: outd=od
                elif od!=outd: ok=False;break
            if ok and outd and any(outd):
                oc=sum(outd[i]<<(i*n) for i in range(w))
                if all(Sval(tuple(x[i]^outd[i] for i in range(w)))==Sval(x) for x in xs()):
                    nxt.add(oc)
        res[R]=len(nxt); cur=list(nxt)
        if not nxt and Rstar is None: Rstar=R
        if not nxt: break
    return res,Rstar

if __name__=="__main__":
    random.seed(7)
    print("=== (D) exhaustive best R-round DP (small n, catches high-prob invariants) ===")
    cfgs=[
        ("n3w2",3,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
        ("n4w2",4,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
    ]
    for name,n,w,rho,beta,eps,sig,red,P in cfgs:
        for R in [1,2,3]:
            p,bd,bo=best_Rround_DP(n,w,rho,beta,eps,sig,red,P,R)
            print(f"  {name} R={R}: bestDP={p:.5f} (2^{math.log2(p):.2f})  Din={[hex(z) for z in bd]} Dout={[hex(z) for z in bo]}")

    print()
    print("=== (F) independent iterated additive-inactive depth (small n exhaustive) ===")
    cfgs2=[
        ("n4w2",4,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
        ("n4w4",4,4,[0,1,2,3],1,[1,-1,1,-1],[(0,1),(2,1)],0x3,[3,0,1,2]),
        ("n5w2",5,2,[0,2],2,[1,-1],[(0,1)],0x5,[1,0]),
    ]
    for name,n,w,rho,beta,eps,sig,red,P in cfgs2:
        res,Rstar=additive_inactive_iter(n,w,rho,beta,eps,sig,red,P,6)
        print(f"  {name}: survivors/R={res}  R*={Rstar}")
