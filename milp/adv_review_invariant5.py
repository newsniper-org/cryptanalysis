#!/usr/bin/env python3
"""
Characterize the S-inactive differentials found at n=16, and check whether ANY of them
survive prob-1 for R>=2 (which would refute the C3 claim of R*=2 prob-1 inactivity).
Also widen candidate diffs to catch non-MSB prob-1 classes.
"""
import random, itertools

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
    def rnd(state):
        ws=list(state); u=[rotl(ws[i],a_rot) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S); v=[(u[i]+t)&m for i in range(w)]
        y=[rotr(v[i],b_rot) for i in range(w)]
        for (ln,k) in sigma_lanes: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    def Lfun(state):
        u=[rotl(state[i],a_rot) for i in range(w)]; S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        return S
    return rnd,Lfun,m,rotl,rotr

def classify_msb(n,a_rot,D):
    """is D_i = ROTR_a(2^{n-1}) (the MSB-pre image) on even lanes? print which lanes nonzero."""
    _,rotl,rotr=mk(n)
    msb_pre=rotr(1<<(n-1),a_rot)
    info=[]
    for i,d in enumerate(D):
        if d==0: continue
        tag="MSBpre" if d==msb_pre else ("MSB" if d==(1<<(n-1)) else "other")
        info.append((i,'%x'%d,tag))
    return info

if __name__=="__main__":
    random.seed(99)
    n,w=16,8; a_rot,b_rot=5,6; red=0x2B
    eps=[1,-1,1,-1,1,-1,1,-1]; PI=[7,4,1,6,3,0,5,2]; SIG=[(0,1),(4,3)]
    rnd,Lfun,m,rotl,rotr=make_round(n,w,a_rot,b_rot,eps,SIG,red,PI)
    msb_pre=rotr(1<<(n-1),a_rot)
    print(f"n={n} a={a_rot}: ROTR_a(MSB)=msb_pre={msb_pre:x}, MSB={1<<(n-1):x}")

    # build candidate diffs: single-bit, MSB-pre on even-lane pairs, plus 2-lane same-bit
    cands=[]
    for ln in range(w):
        for bit in range(n):
            D=[0]*w; D[ln]=1<<bit; cands.append(tuple(D))
    for (i,j) in itertools.combinations(range(w),2):
        for bit in range(n):
            D=[0]*w; D[i]=1<<bit; D[j]=1<<bit; cands.append(tuple(D))
    # MSB-pre pairs (the proposal's prob-1 class): even lanes with eps cancel
    even=[0,2,4,6]
    for (i,j) in itertools.combinations(even,2):
        D=[0]*w; D[i]=msb_pre; D[j]=msb_pre; cands.append(tuple(D))

    def Rrnd_S(x,R):
        Ss=[]
        for r in range(R): Ss.append(Lfun(x)); x=rnd(x)
        return x,Ss

    for R in [1,2,3,4]:
        survivors=[]
        for D in cands:
            if all(d==0 for d in D): continue
            ok=True; Sd_const=None
            for _ in range(1200):
                x=tuple(random.randint(0,m) for _ in range(w))
                x2=tuple((x[i]+D[i])&m for i in range(w))
                _,S1=Rrnd_S(x,R); _,S2=Rrnd_S(x2,R)
                Sd=tuple((S1[r]-S2[r])&m for r in range(R))
                if Sd_const is None: Sd_const=Sd
                elif Sd!=Sd_const: ok=False; break
            if ok and all(s==0 for s in Sd_const):
                survivors.append(D)
        print(f"R={R}: ALL-rounds-S-inactive prob1 diffs = {len(survivors)}")
        for D in survivors[:6]:
            print(f"   D classify: {classify_msb(n,a_rot,D)}")
        if R>=2 and survivors:
            print("   *** prob-1 S-inactive survives R>=2 -> contradicts C3 if non-trivial ***")
