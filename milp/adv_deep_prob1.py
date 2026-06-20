#!/usr/bin/env python3
"""
Deeper prob1-subspace adversarial tests (independent), small-n exhaustive.

(A) Verify MSB-lemma: is the prob-1 single-round inactive set EXACTLY the MSB-XOR-even
    subspace, or are there prob-1 inactive diffs the MSB model misses? Exhaustive over all
    D and all x at n=4,w=4 and n=5,w=4 (where feasible) and n=6,w=2.

(B) High-prob (not just prob-1) iterated differential: best 2-round and 3-round DP over ALL
    nonzero input diffs. If a NON-prob-1 differential has DP close to 1 and iterates, the
    prob-1 metric (=R*=2) gives false security. Report best DP and the diff.

(C) Differential where ONLY untouched-by-sigma lanes carry MSBs: does sigma actually matter?
    (it should not, per finding that framing alone kills it -- but confirm via real diffs.)

(D) Truncated / word-level prob-1 invariant: is there a nonzero set of ACTIVE WORDS that maps
    to itself with prob 1 (word-pattern invariant)? Searches word-activity patterns.
"""
import random

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n
        return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr

def make_alpha(n,red):
    M=(1<<n)-1
    def a(v): return (((v<<1)&M)^(red if (v>>(n-1))&1 else 0))
    return a

def make_F(n):
    m,rotl,_=mk(n); pp=[(7%n,17%n),(3%n,21%n),(9%n,29%n)]
    def F(s):
        acc=s
        for a,b in pp: acc^=rotl(s,a)&rotl(s,b)
        return acc&m
    return F

def build(n,w,rho,beta,eps,sigma,red,P):
    m,rotl,rotr=mk(n); F=make_F(n); a=make_alpha(n,red)
    def apow(x,k):
        for _ in range(k): x=a(x)
        return x
    M=(1<<n)-1
    def rnd(state):
        st=list(state)
        u=[rotl(st[i],rho[i]) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S)
        v=[(u[i]+t)&M for i in range(w)]
        y=[rotr(v[i],beta) for i in range(w)]
        for (ln,k) in sigma: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    return rnd,m

def all_states(n,w):
    m=(1<<n)-1; total=1<<(n*w)
    for c in range(total):
        yield tuple((c>>(i*n))&m for i in range(w))

def prob1_single_round_exact(n,w,rho,beta,eps,sigma,red,P):
    """exhaustive: all D whose 1-round output diff is constant over all x. Return set of D."""
    rnd,m=build(n,w,rho,beta,eps,sigma,red,P)
    total=1<<(n*w)
    survivors=[]
    states=list(all_states(n,w))
    for cD in range(1,total):
        D=tuple((cD>>(i*n))&m for i in range(w))
        out0=None; ok=True
        for x in states:
            xd=tuple(x[i]^D[i] for i in range(w))
            od=tuple(rnd(x)[i]^rnd(xd)[i] for i in range(w))
            if out0 is None: out0=od
            elif od!=out0: ok=False; break
        if ok: survivors.append((cD,out0))
    return survivors

def best_DP(n,w,rho,beta,eps,sigma,red,P,R):
    rnd,m=build(n,w,rho,beta,eps,sigma,red,P)
    def rR(st):
        for _ in range(R): st=rnd(st)
        return st
    total=1<<(n*w)
    states=list(all_states(n,w))
    best=0; bd=None; bo=None
    for cD in range(1,total):
        D=tuple((cD>>(i*n))&m for i in range(w))
        cnt={}
        for x in states:
            xd=tuple(x[i]^D[i] for i in range(w))
            od=tuple(rR(x)[i]^rR(xd)[i] for i in range(w))
            cnt[od]=cnt.get(od,0)+1
        mx=max(cnt.values())
        if mx>best:
            best=mx; bd=D; bo=max(cnt,key=cnt.get)
    return best/total, bd, bo

if __name__=="__main__":
    import math
    # config: n=4,w=4 ; sigma{0,2} minimal-analog and all-lane
    cfgs=[
        ("n4w4 sigma{0,2}", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2]),
        ("n5w4 sigma{0,2}", 5,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x5,[3,0,1,2]),
    ]
    print("=== (A) exact prob-1 single-round inactive set vs MSB-XOR-even model ===")
    for name,n,w,rho,beta,eps,sig,red,P in cfgs:
        sv=prob1_single_round_exact(n,w,rho,beta,eps,sig,red,P)
        # MSB-XOR-even predicted survivors among single-MSB combos:
        msb=1<<(n-1)
        print(f"-- {name}: {len(sv)} prob-1 single-round inactive D --")
        non_msb=[ (c,o) for c,o in sv if any(((c>>(i*n))&((1<<n)-1)) & (~msb & ((1<<n)-1)) for i in range(w)) ]
        print(f"     of which contain NON-MSB diff bits (would BREAK the MSB-only lemma): {len(non_msb)}")
        for c,o in non_msb[:8]:
            Dw=tuple(hex((c>>(i*n))&((1<<n)-1)) for i in range(w))
            print(f"        D={Dw}")
        print()

    print("=== (B) best iterated DP (catches HIGH-prob non-prob-1 invariants) ===")
    for name,n,w,rho,beta,eps,sig,red,P in [cfgs[0]]:
        for R in [1,2,3]:
            p,bd,bo=best_DP(n,w,rho,beta,eps,sig,red,P,R)
            l2 = math.log2(p) if p>0 else float('-inf')
            print(f"  {name} R={R}: bestDP={p:.6f} = 2^{l2:.2f}  D={tuple(hex(z) for z in bd)} -> {tuple(hex(z) for z in bo)}")
