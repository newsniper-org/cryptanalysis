#!/usr/bin/env python3
"""
Vectorized exact best-DP per-round decay, w=2 zero-sum, both lanes sigma'd, 3-term F.
n up to ~11 (state 2n bits) exhaustive. Goal: clean per-round weight slope at large-ish field.
"""
import numpy as np, math

def run(n, a, b, red, k0, k1, Pswap=True, Rmax=5):
    M = (1<<n)-1
    msb = 1<<(n-1)
    full = 1<<n
    idx = np.arange(full, dtype=np.uint64)
    def rotl(x,k):
        k%=n
        if k==0: return x
        return ((x<<np.uint64(k)) | (x>>np.uint64(n-k))) & np.uint64(M)
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    # alpha multiply table
    def alpha(v):
        top = (v>>np.uint64(n-1)) & np.uint64(1)
        return ((v<<np.uint64(1)) & np.uint64(M)) ^ (np.uint64(red)*top)
    def apow(v,k):
        for _ in range(k): v=alpha(v)
        return v
    # 3-term F
    TERMS=[(7%n,17%n),(3%n,21%n),(9%n,29%n)]
    def F(s):
        acc=s.copy()
        for x,y in TERMS:
            acc = acc ^ (rotl(s,x)&rotl(s,y))
        return acc & np.uint64(M)
    # state index encode: s = w0 | w1<<n  ; total 2n bits
    N2 = 1<<(2*n)
    s_all = np.arange(N2, dtype=np.uint64)
    w0 = s_all & np.uint64(M)
    w1 = (s_all >> np.uint64(n)) & np.uint64(M)
    def round_fn(w0,w1):
        u0=rotl(w0,a); u1=rotl(w1,a)
        S=(u0 - u1) & np.uint64(M)   # eps=[+,-]
        t=F(S)
        v0=(u0 + t)&np.uint64(M); v1=(u1+t)&np.uint64(M)
        y0=rotr(v0,b); y1=rotr(v1,b)
        y0=apow(y0,k0); y1=apow(y1,k1)
        if Pswap: return y1,y0
        return y0,y1
    # iterate
    cur0,cur1=w0,w1
    outs=[]
    for R in range(1,Rmax+1):
        cur0,cur1=round_fn(cur0,cur1)
        out = (cur0 | (cur1<<np.uint64(n))).astype(np.uint64)
        outs.append(out.copy())
    # best DP per R over all nonzero diffs
    res=[]
    for R in range(1,Rmax+1):
        out=outs[R-1]
        best=0
        # for each diff D (1..N2-1): pairs (s, s^D), output diff = out[s]^out[s^D]
        # group counts of output-diff value; max count / N2
        for D in range(1, N2):
            sd = s_all ^ np.uint64(D)
            od = out ^ out[sd]
            # max frequency
            cnts = np.bincount(od.astype(np.int64), minlength=1)
            mx = cnts.max()
            if mx>best: best=mx
        res.append(best/N2)
    return res

if __name__=="__main__":
    # n=8: N2=2^16, diff loop 2^16 * bincount(2^16) -> ~4e9, too slow. Restrict to n<=7 exact,
    # and for n=8 sample the diff set to MSB-pairs + single bits.
    print("###### exact best-DP per-round, w=2 zero-sum both-sigma 3-term F ######")
    for n,a,b,red,k0,k1 in [(6,2,3,0x43,1,2),(7,2,3,0x89,1,2)]:
        r=run(n,a,b,red,k0,k1,Rmax=5)
        print(f"-- n={n} (state {2*n}-bit) a={a} b={b} --")
        prev=None
        for i,p in enumerate(r,1):
            l2=math.log2(p) if p>0 else float('-inf')
            slope="" if prev is None else f"  Δw={(-l2)-prev:+.2f}"
            print(f"   R={i}: bestDP=2^{l2:6.2f}{slope}")
            prev=-l2
        print()
