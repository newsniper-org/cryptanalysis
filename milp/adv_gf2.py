#!/usr/bin/env python3
"""
Adversarial lens: prob1-subspace via GF(2). The proposal's BIGGEST hand-wave is dismissing
its own GF(2)-LA proxy (R*~8-9) as 'irrelevant because additive pass prob ~0.5'.

I scrutinize this directly. The GF(2)-LA proxy in inactive_subspace.py computes a LINEAR map
Lin = pi o sigma and asks for diffs d with XORsum(rho-rotated Lin^r d)=0 for all r<R. But that
proxy is for the OLD XOR-broadcast. For the NEW additive design it is NOT the right linearization.

The RIGHT question for prob-1 in the NEW design:
  Is there a nonzero input diff d that propagates through R rounds with probability 1
  (a prob-1 differential characteristic)? That requires, at each round, dS being a CONSTANT
  independent of x AND that constant feeding through F deterministically.

There are TWO sub-cases of prob-1 propagation:
  (P1) dS = 0 for all x  -> dt=0 -> round linear on d (proposal's "additive-inactive").
  (P2) dS = CONST != 0 for all x -> dt = F(S+const)^F(S) which is NOT generally constant
       (F nonlinear) -> usually breaks prob-1. So (P1) is the main prob-1 channel. Good.

So I directly enumerate prob-1 differential characteristics over R rounds by EXHAUSTIVE
diff-propagation with the actual round (small n), tracking diffs that stay deterministic.
This is the gold standard and supersedes any proxy.
"""
import random
from adv_invert import build_round, mk

def prob1_char_depth(n,w,rho,beta,eps,sigma,red,P,Rmax=6,sample=None):
    rnd,_,_,M=build_round(n,w,rho,beta,eps,sigma,red,P)
    total=1<<(n*w)
    full = total<=(1<<20)
    def xs():
        if full:
            for cx in range(total): yield tuple((cx>>(i*n))&M for i in range(w))
        else:
            for _ in range(sample or 3000): yield tuple(random.randint(0,M) for _ in range(w))
    # find all input diffs that go through 1 round deterministically (prob-1)
    def det_out(D, rfix=0):
        outd=None
        for x in xs():
            o1=rnd(x,rfix); o2=rnd(tuple(x[i]^D[i] for i in range(w)),rfix)
            od=tuple(o1[i]^o2[i] for i in range(w))
            if outd is None: outd=od
            elif od!=outd: return None
        return outd
    # round 1 prob-1 diffs
    cur={}
    res={}
    cands = range(1,total) if full else None
    if not full:
        # can't enumerate all diffs; sample candidate diffs (low weight) - but for prob-1 we
        # really need exhaustive; restrict to full cases only
        return None
    surv1=[]
    for c in range(1,total):
        D=tuple((c>>(i*n))&M for i in range(w))
        od=det_out(D,0)
        if od is not None and any(od):
            surv1.append((D,od))
    res[1]=len(surv1)
    # iterate: a diff chain D0->D1->...; at each round the input diff must be prob-1 deterministic
    # track set of diffs reachable by a prob-1 chain of length R
    frontier={D:od for (D,od) in surv1}
    Rstar = 1 if not surv1 else None
    for R in range(2,Rmax+1):
        nxt={}
        for D,od in frontier.items():
            # od is the diff entering round R; check it's prob-1 deterministic at round R
            od2=det_out(od, (R-1))
            if od2 is not None and any(od2):
                nxt[od]=od2
        res[R]=len(nxt)
        frontier=nxt
        if not nxt and Rstar is None: Rstar=R
        if not nxt: break
    return res, Rstar

if __name__=="__main__":
    random.seed(11)
    SIG=[(0,1),(2,3),(4,5),(6,7)]
    PPI=[7,4,1,6,3,0,5,2]
    EPS=[1,-1,1,-1,1,-1,1,-1]
    RHO_full=[0,5,11,17,23,3,13,29]

    print("=== prob-1 differential characteristic depth (EXHAUSTIVE, gold standard) ===")
    # use full w=8 structure where state<=20 bits: n=2 (16b) only fully feasible
    for n,red in [(2,0x3)]:
        rho=[r%n for r in RHO_full]; beta=1
        out=prob1_char_depth(n,8,rho,beta,EPS,SIG,red,PPI,Rmax=8)
        print(f"  n={n} w=8 (16b) full: {out}")

    # smaller w but bigger n for cross-check
    for (n,w,rho,beta,eps,sigma,red,P) in [
        (4,4,[0,1,2,3],2,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2]),
        (5,4,[0,1,2,3],2,[1,-1,1,-1],[(0,1),(2,3)],0x5,[3,0,1,2]),
        (4,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
    ]:
        out=prob1_char_depth(n,w,rho,beta,eps,sigma,red,P,Rmax=8)
        print(f"  n={n} w={w} ({n*w}b) full: {out}")
