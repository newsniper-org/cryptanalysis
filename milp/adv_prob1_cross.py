#!/usr/bin/env python3
"""
Cross-check: empirical R=2 prob-1 differential scan with a!=b (non-degenerate),
using a width as large as affordable, to validate the model's R*=2 at real-ish params.
Also: scan for prob-1 differentials through ACTIVE F (F-cancellation) which the
linear-inactive model would not catch.

We exhaust n=4,w=8 (2^32 too big) -> instead sample x heavily per candidate diff,
and exhaust n=4,w=6 / n=5,w=4 fully. Key: use a!=b like the real design.
"""
import itertools, random
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
    m,rotl,rotr=mk(n); F=make_F(n,pairs); al=alpha_fac(n,red)
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

def scan(n,w,a,b,eps,sig,red,P,pairs,R,sample=None):
    m=(1<<n)-1
    rnd=make_round(n,w,a,b,eps,sig,red,P,pairs)
    def rndR(st):
        for _ in range(R): st=rnd(st)
        return st
    # candidate diffs: all single-bit (n*w of them) + all-MSB-pre combos
    cands=set()
    for i in range(w):
        for bit in range(n): cands.add((1<<bit)<<(i*n))
    # pairs/quadruples of msb-pre on lanes
    _,rotl,rotr=mk(n)
    msbpre=rotr(1<<(n-1),a)
    for r in range(2,w+1,2):
        for combo in itertools.combinations(range(w),r):
            d=0
            for i in combo: d|=msbpre<<(i*n)
            cands.add(d)
    cands.discard(0)
    surv=[]
    bits=n*w
    full = (sample is None and bits<=22)
    for d in cands:
        dw=tuple((d>>(i*n))&m for i in range(w))
        ods=set()
        if full:
            xs=range(1<<bits)
        else:
            xs=(random.randint(0,(1<<bits)-1) for _ in range(sample))
        for code in xs:
            st=tuple((code>>(i*n))&m for i in range(w))
            st2=tuple(st[i]^dw[i] for i in range(w))
            x=rndR(st); y=rndR(st2)
            ods.add(tuple(x[i]^y[i] for i in range(w)))
            if len(ods)>1: break
        if len(ods)==1: surv.append(d)
    return surv, ("full" if full else f"sample={sample}")

if __name__=="__main__":
    random.seed(7)
    PAIRS=[(7,17),(3,21),(9,29)]
    print("=== a!=b non-degenerate empirical R=2 prob-1 scan ===")
    cfgs=[
        # (n,w,a,b,eps,sig,red,P,sample,label)
        (4,4,1,2,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2],None,"n4w4 a1b2"),
        (4,4,1,3,[1,-1,1,-1],[(0,1),(2,3)],0x3,[3,0,1,2],None,"n4w4 a1b3"),
        (5,4,2,3,[1,-1,1,-1],[(0,1),(2,3)],0x5,[3,0,1,2],None,"n5w4 a2b3"),
        # 8-lane (matches real lane count + sig{0,4} + PI), sampled (2^32 too big)
        (4,8,1,2,[1,-1,1,-1,1,-1,1,-1],[(0,1),(4,3)],0x3,[7,4,1,6,3,0,5,2],400000,"n4w8 a1b2 sig0,4 PI"),
        (4,8,3,1,[1,-1,1,-1,1,-1,1,-1],[(0,1),(4,3)],0x3,[7,4,1,6,3,0,5,2],400000,"n4w8 a3b1 sig0,4 PI"),
    ]
    for (n,w,a,b,eps,sig,red,P,samp,lab) in cfgs:
        for R in (2,3):
            surv,mode=scan(n,w,a,b,eps,sig,red,P,PAIRS,R,sample=samp)
            print(f"  [{lab}] R={R} ({mode}): #prob-1 survivors={len(surv)}"
                  +("" if not surv else "  "+",".join(hex(x) for x in surv[:6])))
