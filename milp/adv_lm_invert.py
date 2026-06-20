#!/usr/bin/env python3
"""
ADVERSARIAL invertibility check of yttrium-LM-ARX proposal.
Faithful re-implementation from the proposal JSON (NOT reusing author's code),
to independently find non-permutation / inversion-failure / prob-1 subspace.

Round (per proposal):
  ι:  state[r mod w] ^= RC[r]
  x'_i = ROTL_a(state_i)
  S = sum_i eps_i * x'_i   (mod 2^n),  sum eps_i = 0
  t = F(S)
  v_i = x'_i + t (mod 2^n)
  y_i = ROTR_b(v_i)
  σ: y_i = alpha^{k_i} * y_i  (GF(2^n))
  π: new[i] = y[P[i]]
"""
import random, itertools

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n
        return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr

def make_F(n, pairs):
    m,rotl,_=mk(n)
    pp=[(a%n,b%n) for a,b in pairs]
    def F(s):
        acc=s
        for a,b in pp:
            acc ^= (rotl(s,a)&rotl(s,b))
        return acc&m
    return F

def alpha_fac(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a

def alpha_inv_fac(n,red):
    # reverse LFSR step: a(v) = (v<<1 ^ (red if msb else 0)) & m.
    # given w = a(v), recover v. low bit of w tells us if reduction happened:
    # if msb(v)=1 then w = (v<<1 & m) ^ red ; else w = v<<1 & m (even, lsb 0).
    # red has lsb 1 (primitive). So bit0(w)=msb(v). Then v = ((w ^ (red if bit0(w) else 0)) >> 1) | (bit0(w)<<(n-1))
    m=(1<<n)-1
    def ainv(w):
        msb = w & 1
        t = (w ^ (red if msb else 0)) & m
        return (t>>1) | (msb<<(n-1))
    return ainv

def make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs,rc_lane=0):
    m,rotl,rotr=mk(n)
    F=make_F(n,pairs)
    al=alpha_fac(n,red)
    ai=alpha_inv_fac(n,red)
    def apow(x,k):
        for _ in range(k): x=al(x)
        return x
    def apow_inv(x,k):
        for _ in range(k): x=ai(x)
        return x
    def rnd(state,rc=0):
        ws=list(state)
        ws[rc_lane]=(ws[rc_lane]^rc)&m
        xp=[rotl(ws[i],a_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*xp[i])%(1<<n)
        t=F(S)
        v=[(xp[i]+t)&m for i in range(w)]
        y=[rotr(v[i],b_rot) for i in range(w)]
        for (lane,k) in sigma_lanes: y[lane]=apow(y[lane],k)
        return tuple(y[P[i]] for i in range(w))
    def inv(state,rc=0):
        out=list(state)
        y=[0]*w
        for i in range(w): y[P[i]]=out[i]
        for (lane,k) in sigma_lanes: y[lane]=apow_inv(y[lane],k)
        v=[rotl(y[i],b_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*v[i])%(1<<n)
        t=F(S)
        xp=[(v[i]-t)&m for i in range(w)]
        ws=[rotr(xp[i],a_rot) for i in range(w)]
        ws[rc_lane]=(ws[rc_lane]^rc)&m
        return tuple(ws)
    return rnd,inv

def full_perm(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs):
    bits=n*w
    if bits>22:
        return None,None,None
    rnd,inv=make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs)
    m=(1<<n)-1
    seen=set(); coll=None
    def packy(y):
        s=0
        for i,x in enumerate(y): s|=(x&m)<<(i*n)
        return s
    for code in range(1<<bits):
        st=tuple((code>>(i*n))&m for i in range(w))
        y=packy(rnd(st,rc=0))
        if y in seen and coll is None:
            coll=("dup",st,y)
        seen.add(y)
    isperm=(len(seen)==(1<<bits))
    return isperm,len(seen),coll

def roundtrip(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs,trials=50000):
    rnd,inv=make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P,pairs)
    m=(1<<n)-1
    bad=0; example=None
    for _ in range(trials):
        st=tuple(random.randint(0,m) for _ in range(w))
        rc=random.randint(0,m)
        back=inv(rnd(st,rc=rc),rc=rc)
        if back!=st:
            bad+=1
            if example is None: example=(st,back)
    return bad,example

if __name__=="__main__":
    random.seed(12345)
    # validate alpha inverse derivation across n
    for n in (4,6,8,10,12,16):
        for red in ([0x3] if n==4 else [0x1D] if n==8 else [0x2B] if n==16 else [ (1<<(n-1))|0x7 ]):
            al=alpha_fac(n,red); ai=alpha_inv_fac(n,red)
            ok=all(ai(al(x))==x for x in range(min(1<<n, 1<<16)))
            print(f"  alpha-inv self-check n={n} red={hex(red)}: {'OK' if ok else 'FAIL'}")
    # n=32 sample
    al=alpha_fac(32,0x400007); ai=alpha_inv_fac(32,0x400007)
    ok32=all(ai(al(random.randint(0,(1<<32)-1)))==v for v in [random.randint(0,(1<<32)-1) for _ in range(100000)] for _ in [0]) if False else None
    ok32=all(ai(al(x))==x for x in (random.randint(0,(1<<32)-1) for _ in range(200000)))
    print(f"  alpha-inv self-check n=32 red=0x400007 (200k random): {'OK' if ok32 else 'FAIL'}")
    print()
    PAIRS=[(7,17),(3,21),(9,29)]
    PI=[7,4,1,6,3,0,5,2]
    eps_alt=[1,-1,1,-1,1,-1,1,-1]
    print("=== FULL-PERMUTATION EXHAUSTIVE (independent re-impl) ===")
    # tiny states with full 8-lane structure where possible, plus w=2 alt eps
    cfgs=[
        # (n,w,a,b,eps,sigma,red,P,label)
        (4,2,1,1,[1,-1],[(0,1)],0x3,[1,0],"n4w2 sig0"),
        (6,2,1,1,[1,-1],[(0,1)],0x3,[1,0],"n6w2 sig0"),
        (8,2,3,4,[1,-1],[(0,1)],0x1D,[1,0],"n8w2 sig0"),
        (10,2,3,4,[1,-1],[(0,1)],0x9,[1,0],"n10w2 sig0"),
        (4,4,1,1,[1,-1,1,-1],[(0,1),(2,1)],0x3,[3,0,1,2],"n4w4"),
        (5,4,1,2,[1,-1,1,-1],[(0,1),(2,1)],0x5,[3,0,1,2],"n5w4"),
        # ALL-lane sigma (proposal recommended full-lane k=1..8)
        (4,4,1,1,[1,-1,1,-1],[(0,1),(1,2),(2,3),(3,4)],0x3,[3,0,1,2],"n4w4 ALLsig"),
        # zero eps lane present? proposal requires |eps|=1 all; test what if a lane has eps but combiner still adds t
    ]
    for (n,w,a,b,eps,sig,red,P,lab) in cfgs:
        isperm,cnt,coll=full_perm(n,w,a,b,eps,sig,red,P,PAIRS)
        if isperm is None:
            print(f"  [{lab}] skipped (too large)")
        else:
            print(f"  [{lab}] state={n*w}b images={cnt}/{1<<(n*w)} perm={isperm}"
                  + (f"  COLLISION {coll[0]} & {coll[1]} -> {coll[2]}" if coll else ""))

    print()
    print("=== ROUNDTRIP (full 8-lane, larger n) ===")
    for (n,a,b,red) in [(8,3,4,0x1D),(16,5,6,0x2B),(32,8,9,0x400007)]:
        bad,ex=roundtrip(n,8,a,b,eps_alt,[(0,1),(4,3)],red,PI,PAIRS,trials=40000)
        print(f"  [n={n} w=8 sig0,4] mismatches={bad}/40000"+(f" EX {ex}" if ex else ""))
        # all-lane sigma
        allsig=[(i,i+1) for i in range(8)]
        bad2,ex2=roundtrip(n,8,a,b,eps_alt,allsig,red,PI,PAIRS,trials=40000)
        print(f"  [n={n} w=8 ALLsig] mismatches={bad2}/40000"+(f" EX {ex2}" if ex2 else ""))
