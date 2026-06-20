#!/usr/bin/env python3
"""
Final independent checks:
 (1) C1 invertibility: exhaustive permutation test at larger state than repo scripts.
     The tree-mode mask uniqueness k(path)=P(IV^encode(path)) REQUIRES P to be a bijection.
 (2) tree-mode mask injectivity: distinct encode(path) -> distinct mask, given P bijection.
 (3) confirm multi-round full permutation (compose round 2-3x) stays a permutation.
"""
import itertools, random

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr
def make_F(n,pairs=((7,17),(3,21),(9,29))):
    m,rotl,_=mk(n); pp=[((a%n),(b%n)) for a,b in pairs]
    def F(s):
        acc=s
        for a,b in pp: acc^=(rotl(s,a)&rotl(s,b))
        return acc&m
    return F
def alpha_factory(n,red):
    m=(1<<n)-1
    return lambda v: (((v<<1)&m)^(red if (v>>(n-1)) else 0))

def make_round(n,w,a_rot,b_rot,eps,sigma_lanes,red,P):
    m,rotl,rotr=mk(n); F=make_F(n); al=alpha_factory(n,red)
    def apow(x,k):
        for _ in range(k): x=al(x)
        return x
    def rnd(state,rc=0,rc_lane=0):
        ws=list(state); ws[rc_lane]^=rc; ws[rc_lane]&=m
        u=[rotl(ws[i],a_rot) for i in range(w)]; S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S); v=[(u[i]+t)&m for i in range(w)]
        y=[rotr(v[i],b_rot) for i in range(w)]
        for (ln,k) in sigma_lanes: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    return rnd,m

def full_perm(n,w,a_rot,b_rot,eps,SIG,red,P,Rrounds=1,rc_list=None):
    bits=n*w
    rnd,m=make_round(n,w,a_rot,b_rot,eps,SIG,red,P)
    seen=set(); tot=1<<bits
    rcs=rc_list or [0]*Rrounds
    for code in range(tot):
        st=tuple((code>>(i*n))&m for i in range(w))
        x=st
        for r in range(Rrounds): x=rnd(x,rc=rcs[r],rc_lane=r%w)
        seen.add(x)
    return len(seen),tot

if __name__=="__main__":
    PI=[7,4,1,6,3,0,5,2]
    eps2=[1,-1]; eps4=[1,-1,1,-1]
    print("=== C1 exhaustive permutation (independent impl) ===")
    # n=10,w=2 -> 20 bits (1M) ; n=4,w=5? need P perm of w. use w=4,n=5 (20b); w=2,n=10 (20b)
    cfgs=[
        (8,2,3,4,eps2,[(0,1)],0x1D,[1,0],1),
        (10,2,3,5,eps2,[(0,1)],0x409,[1,0],1),   # n=10 red 0x409 (x^10+x^3+1 area)
        (5,4,2,3,eps4,[(0,1),(2,3)],0x5,[3,0,1,2],1),
        (4,4,1,2,eps4,[(0,1),(2,3)],0x3,[3,0,1,2],2),   # 2-round compose
        (5,4,2,3,eps4,[(0,1),(2,3)],0x5,[3,0,1,2],3),   # 3-round compose, 20b
    ]
    for (n,w,a,b,eps,SIG,red,P,R) in cfgs:
        if n*w>20:
            print(f"  n={n} w={w} R={R}: skip ({n*w}b)"); continue
        rcs=[(i*0x9E+1)&((1<<n)-1) for i in range(R)]
        img,tot=full_perm(n,w,a,b,eps,SIG,red,P,Rrounds=R,rc_list=rcs)
        print(f"  n={n} w={w} R={R} ({n*w}b): images={img}/{tot} perm={img==tot}")

    print("\n=== (2) tree-mode mask injectivity: k=P(IV^encode) distinct for distinct encode ===")
    # mask(path) = round^Rmask(IV XOR encode). distinct encode -> distinct mask iff round is perm.
    n,w=8,4; a,b=3,4; red=0x1D
    rnd,m=make_round(n,w,a,b,eps4,[(0,1),(2,3)],red,[3,0,1,2])
    IV=tuple(0x55 for _ in range(w))
    masks={}
    coll=0
    for code in range(1<<(n*w)):  # encode space (32 bits too big -> use n=8,w=4 =32b too big). shrink:
        break
    # shrink to n=4,w=4 =16b for full injectivity sweep
    n,w=4,4; a,b=1,2; red=0x3
    rnd,m=make_round(n,w,a,b,eps4,[(0,1),(2,3)],red,[3,0,1,2])
    IV=tuple(0x5 for _ in range(w))
    seen={}; coll=0; tot=1<<(n*w)
    for code in range(tot):
        enc=tuple((code>>(i*n))&m for i in range(w))
        st=tuple(IV[i]^enc[i] for i in range(w))
        for _ in range(8): st=rnd(st,rc=0,rc_lane=0)  # Rmask=8
        if st in seen: coll+=1
        seen[st]=enc
    print(f"  n={n} w={w} Rmask=8: distinct encodes={tot}, distinct masks={len(seen)}, collisions={coll}")
    print(f"  => mask injective: {coll==0}  (depends ONLY on round being a permutation + encode injective)")
