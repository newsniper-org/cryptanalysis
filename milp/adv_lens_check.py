#!/usr/bin/env python3
"""
Independent adversarial verification, lens = prob1-subspace (primary),
plus invertibility and farfalle-bridge sanity.

Round (per proposal), parameterized for small-n exhaustive runs:
  (i)  state[r mod w] ^= RC[r]            (skip RC for diff analysis; XOR cancels in diffs)
  u_i = ROTL_rho(state_i)
  S   = sum_i eps_i * u_i  (mod 2^n)
  t   = F(S)
  v_i = u_i + t (mod 2^n)
  y_i = ROTR_beta(v_i)
  sigma: y[ln] = alpha^k(y[ln]) for (ln,k) in sigma   (GF(2^n) alpha-mult)
  pi  : new_i = y[P[i]]

PRIMARY QUESTION (prob1-subspace lens):
 Does there exist a NONZERO input difference D such that for ALL states x the round
 output difference is constant (prob-1 differential), iterated to R>=2 ?
 The author's LA only models the *MSB-pair* family (forces non-MSB diff bits = 0).
 We instead search EXHAUSTIVELY over ALL nonzero D at small n -- catching any prob-1
 inactive class the MSB-only model could miss.
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
    # verify alpha is a permutation (orthomorphism prerequisite)
    img=set(a(x) for x in range(1<<n))
    alpha_perm=(len(img)==(1<<n))
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
    return rnd, m, alpha_perm

def round_R(rnd, st, R):
    for _ in range(R): st=rnd(st)
    return st

def prob1_inactive_exhaustive(n,w,rho,beta,eps,sigma,red,P,Rmax):
    """
    For each R, count nonzero input diffs D that are prob-1 (output diff constant over ALL x)
    AND that diff propagates to a NONZERO constant output diff (a true iterated prob-1 class).
    We require the *whole R-round map* to send D to a single constant output diff over all x.
    state must be small (n*w <= ~16 for full exhaustive over both D and x).
    """
    rnd,m,_=build(n,w,rho,beta,eps,sigma,red,P)
    bits=n*w
    total=1<<bits
    assert bits<=18, "too big for double-exhaustive"
    res={}
    for R in range(1,Rmax+1):
        survivors=[]
        for cD in range(1,total):
            D=tuple((cD>>(i*n))&m for i in range(w))
            out0=None; ok=True
            for cx in range(total):
                x=tuple((cx>>(i*n))&m for i in range(w))
                xd=tuple(x[i]^D[i] for i in range(w))
                oR=round_R(rnd,x,R); oRd=round_R(rnd,xd,R)
                od=tuple(oR[i]^oRd[i] for i in range(w))
                if out0 is None: out0=od
                elif od!=out0: ok=False; break
            if ok:
                survivors.append((cD,out0))
        res[R]=survivors
    return res

if __name__=="__main__":
    random.seed(0)
    # small-n proxies of the design. We test BOTH:
    #   (A) minimal sigma {0,4}-analog (only 2 lanes touched)  -- author's "minimal" claim
    #   (B) all-lane sigma                                      -- author's "conservative" claim
    print("=== prob1-subspace: EXHAUSTIVE over all nonzero D (not just MSB-pair) ===")
    print("    survivor = D whose R-round output diff is CONSTANT over ALL states (prob-1).")
    print()

    # n=4,w=4 (16-bit state) -- full double-exhaustive feasible (2^16 * 2^16 ~ 4e9 worst; we early-break)
    # alpha/beta small analogs of (8,9): use rho all = alpha_rot, beta. eps zero-sum.
    configs=[
        # name, n,w, rho(list), beta, eps, sigma, red, P
        ("n4w4 sigma{0,2} (minimal-analog)", 4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2]),
        ("n4w4 sigma all-lane",               4,4,[1,1,1,1],2,[1,-1,1,-1],[(0,1),(1,2),(2,3),(3,4)],0x3,[3,0,1,2]),
    ]
    for name,n,w,rho,beta,eps,sig,red,P in configs:
        rnd,m,ap=build(n,w,rho,beta,eps,sig,red,P)
        print(f"-- {name}  (alpha_perm={ap}) --")
        res=prob1_inactive_exhaustive(n,w,rho,beta,eps,sig,red,P,3)
        for R in sorted(res):
            sv=res[R]
            nz=[(hex(c),tuple(hex(z) for z in o)) for c,o in sv if any(o)]
            print(f"   R={R}: total prob-1 survivors={len(sv)}  with NONZERO out-diff={len(nz)}")
            for c,o in (sv[:6]):
                Dwords=tuple(hex((c>>(i*n))&m) for i in range(w))
                print(f"       D={Dwords} -> outdiff={tuple(hex(z) for z in o)}")
        print()
