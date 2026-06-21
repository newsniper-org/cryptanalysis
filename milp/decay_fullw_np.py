#!/usr/bin/env python3
"""
Vectorized SAMPLED best-DP at FULL width w=8, n=8 (state 64-bit), real all-8 sigma, 3-term F.
numpy-vectorized over samples. Measures worst-delta DP at R=1,2,3 to extract full-width slope.
Compares all-8 sigma vs partial sigma{0,4} on the worst delta class (MSB-pair).
"""
import numpy as np, math

def make_round(n, a, b, red, sigk):
    M=np.uint64((1<<n)-1)
    def rotl(x,k):
        k%=n
        if k==0: return x
        return ((x<<np.uint64(k))|(x>>np.uint64(n-k)))&M
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    def alpha(v):
        top=(v>>np.uint64(n-1))&np.uint64(1)
        return ((v<<np.uint64(1))&M)^(np.uint64(red)*top)
    def apow(v,k):
        for _ in range(k): v=alpha(v)
        return v
    TERMS=[(7%n,17%n),(3%n,21%n),(9%n,29%n)]
    EPS=[1,-1,1,-1,1,-1,1,-1]
    P=[7,4,1,6,3,0,5,2]
    def F(s):
        acc=s.copy()
        for x,y in TERMS: acc=acc^(rotl(s,x)&rotl(s,y))
        return acc&M
    def rnd(ws):
        # ws: list of 8 numpy arrays
        u=[rotl(ws[i],a) for i in range(8)]
        S=np.zeros_like(ws[0])
        for i in range(8):
            S = (S + u[i])&M if EPS[i]>0 else (S - u[i])&M
        t=F(S)
        v=[(u[i]+t)&M for i in range(8)]
        y=[rotr(v[i],b) for i in range(8)]
        y=[apow(y[i],sigk[i]) for i in range(8)]
        return [y[P[i]] for i in range(8)]
    return rnd, int(M)

def worst_dp(n,a,b,red,sigk, deltas, R, nsamp, seed):
    rnd,M=make_round(n,a,b,red,sigk)
    rng=np.random.default_rng(seed)
    best=0; bD=None
    for D in deltas:
        ws=[rng.integers(0, M+1, size=nsamp, dtype=np.uint64) for _ in range(8)]
        wsd=[ws[i]^np.uint64(D[i]) for i in range(8)]
        a1=ws; a2=wsd
        for _ in range(R):
            a1=rnd(a1); a2=rnd(a2)
        # output diff packed into a python-side hashable: combine 8 lanes -> use tuple via stacking
        od=np.zeros(nsamp, dtype=object)
        # pack into 64-bit via shifting (n=8 -> 8 lanes *8 =64 fits)
        packed=np.zeros(nsamp, dtype=np.uint64)
        for i in range(8):
            packed |= ((a1[i]^a2[i])&np.uint64(M))<<np.uint64(i*n)
        vals,cnts=np.unique(packed, return_counts=True)
        mx=cnts.max()
        if mx>best: best=mx; bD=D
    return best/nsamp, bD

if __name__=="__main__":
    n=8; a,b=2,3; red=0x11d
    msb=1<<(n-1); mid=1<<(n//2)
    # worst delta candidates: MSB-pairs across same-sign lanes (eps + lanes 0,2,4,6; - lanes 1,3,5,7)
    plus=[0,2,4,6]; minus=[1,3,5,7]
    deltas=[]
    for i in range(len(plus)):
        for j in range(i+1,len(plus)):
            D=[0]*8; D[plus[i]]=msb; D[plus[j]]=msb; deltas.append(tuple(D))
    for i in range(len(minus)):
        for j in range(i+1,len(minus)):
            D=[0]*8; D[minus[i]]=msb; D[minus[j]]=msb; deltas.append(tuple(D))
    # single MSB
    for l in range(8):
        D=[0]*8; D[l]=msb; deltas.append(tuple(D))
    ALL8=[1,2,3,5,7,11,13,17]
    SIG04=[1,0,0,0,3,0,0,0]
    NS=1<<20
    print(f"###### full-width(w=8) n=8 sampled worst-DP, nsamp=2^{int(math.log2(NS))} ######")
    print(f"# {len(deltas)} MSB/single deltas; floor~2^-{int(math.log2(NS))}\n")
    for name,sigk in [("all-8 σ",ALL8),("sig{0,4}",SIG04)]:
        print(f"-- {name} --")
        prev=None
        for R in [1,2,3]:
            p,bD=worst_dp(n,a,b,red,sigk,deltas,R,NS, 1000+R)
            l2=math.log2(p) if p>0 else float('-inf')
            slope="" if prev is None else f"  Δw={(-l2)-prev:+.2f}"
            print(f"   R={R}: worst-δ DP=2^{l2:6.2f}  δ={tuple(hex(z) for z in bD)}{slope}", flush=True)
            prev=-l2
        print()
