#!/usr/bin/env python3
"""
ADVERSARIAL prob-1 inactive differential search — EMPIRICAL, no model assumption.

For the actual round (small n, full state exhaustion/sampling), find differences Δ
such that the round is "inactive" with probability 1 over R rounds, meaning the
difference propagation never activates F (ΔS stays such that the output difference
is purely linear / the trail holds with prob 1).

We test the strongest form: a difference Δ is "prob-1 inactive for R rounds" iff
for ALL inputs x, the output difference  rnd^R(x+Δ) - rnd^R(x)  (consistently) ...
Actually for ARX the right test of a prob-1 DIFFERENTIAL (Δ_in -> Δ_out with p=1):
  exists Δ_out s.t. for all x: rnd(x ^ Δ_in) ^ rnd(x) == Δ_out   (XOR-difference, p=1)
We scan all single + low-weight Δ_in and also the MSB-pattern Δ, measuring
#distinct output diffs. If ==1 over all x -> prob-1 differential (BAD if R>=2).

We use XOR differences (the F is GF(2), reduction/combiner is ARX-add).
This is the operational definition of a probability-1 differential.
"""
import itertools

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n
        return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr

def make_F(n,pairs):
    m,rotl,_=mk(n)
    pp=[(a%n,b%n) for a,b in pairs]
    def F(s):
        acc=s
        for a,b in pp: acc^=(rotl(s,a)&rotl(s,b))
        return acc&m
    return F

def alpha_fac(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a

def make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs):
    m,rotl,rotr=mk(n)
    F=make_F(n,pairs)
    al=alpha_fac(n,red)
    def apow(x,k):
        for _ in range(k): x=al(x)
        return x
    def rnd(state):
        ws=list(state)
        xp=[rotl(ws[i],a_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*xp[i])%(1<<n)
        t=F(S)
        v=[(xp[i]+t)&m for i in range(w)]
        y=[rotr(v[i],b_rot) for i in range(w)]
        for (lane,k) in sigma_lanes: y[lane]=apow(y[lane],k)
        return tuple(y[P[i]] for i in range(w))
    return rnd

def prob1_diffs(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs,R,cand_diffs,maxx=None):
    """For each candidate input diff, run R rounds, check if output XOR-diff is
    constant over all inputs x (=> prob-1 differential)."""
    m=(1<<n)-1
    rnd=make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs)
    def rndR(st):
        for _ in range(R): st=rnd(st)
        return st
    bits=n*w
    if maxx is None: maxx=1<<bits
    found=[]
    for d in cand_diffs:
        dw=tuple((d>>(i*n))&m for i in range(w))
        outdiffs=set()
        for code in range(maxx):
            st=tuple((code>>(i*n))&m for i in range(w))
            st2=tuple(st[i]^dw[i] for i in range(w))
            a=rndR(st); b=rndR(st2)
            od=tuple(a[i]^b[i] for i in range(w))
            outdiffs.add(od)
            if len(outdiffs)>1: break
        if len(outdiffs)==1:
            found.append((d,next(iter(outdiffs))))
    return found

if __name__=="__main__":
    PAIRS=[(7,17),(3,21),(9,29)]
    print("=== EMPIRICAL prob-1 XOR-differential scan (full state exhaustion) ===")
    # small full-state configs we can exhaust
    # n=4,w=4 (2^16), sigma 0,4? only 4 lanes -> sigma (0,1),(2,3) analog
    cfgs=[
        (4,4,1,1,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2],"n4w4"),
        (5,4,1,2,[1,-1,1,-1],[(0,1),(2,3)],0x5,[3,0,1,2],"n5w4"),
        (4,4,2,3,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2],"n4w4 a2b3"),
    ]
    for (n,w,a,b,eps,sig,red,P,lab) in cfgs:
        m=(1<<n)-1; bits=n*w
        # candidate diffs: all single-word single-bit, MSB pattern, all-MSB even-parity combos
        cands=set()
        for i in range(w):
            for bit in range(n):
                cands.add((1<<bit)<<(i*n))
        # MSB-pair patterns: ROTR_a(MSB) on even lanes (the claimed prob-1 class).
        # MSB of word = bit n-1. The reduction does ROTL_a then sign-sum. A word diff that
        # becomes MSB after ROTL_a is ROTR_a(2^(n-1)). Put on pairs of same-sign lanes.
        msb_pre = ( (1<<(n-1)) >> a ) | ( (1<<(n-1)) << (n-a) ) & m  # rotr_a(msb)
        msb_pre &= m
        # all even-parity combos of msb_pre across lanes (dim up to w)
        for r in range(1,w+1):
            for combo in itertools.combinations(range(w),r):
                if r%2==0:  # need parity-related; just try all even and odd
                    pass
                d=0
                for i in combo: d|=msb_pre<<(i*n)
                cands.add(d)
        cands.discard(0)
        for R in (1,2,3):
            f=prob1_diffs(n,w,a,b,eps,sig,red,P,PAIRS,R,sorted(cands))
            print(f"  [{lab}] R={R}: #prob-1 diffs={len(f)}"
                  + ("" if not f else "  e.g. "+",".join(hex(d) for d,_ in f[:6])))
