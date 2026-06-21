#!/usr/bin/env python3
"""n=16 (state 128-bit), full width w=8, all-8 sigma, worst MSB-pair delta only.
Measure R=1,2,3 to see slope scaling vs n=8. a=4,b=5 (ratio ~8:9). red primitive deg16."""
import numpy as np, math
from decay_fullw_np import make_round

def worst_dp_n16(n,a,b,red,sigk, deltas, R, nsamp, seed):
    rnd,M=make_round(n,a,b,red,sigk)
    rng=np.random.default_rng(seed)
    best=0; bD=None
    for D in deltas:
        ws=[rng.integers(0, M+1, size=nsamp, dtype=np.uint64) for _ in range(8)]
        wsd=[ws[i]^np.uint64(D[i]) for i in range(8)]
        a1=ws; a2=wsd
        for _ in range(R):
            a1=rnd(a1); a2=rnd(a2)
        # n=16 -> 8 lanes *16=128 too wide for uint64. Hash lane tuple via two uint64 halves.
        lo=np.zeros(nsamp,dtype=np.uint64); hi=np.zeros(nsamp,dtype=np.uint64)
        for i in range(4):
            lo|=((a1[i]^a2[i])&np.uint64(M))<<np.uint64(i*n)
        for i in range(4,8):
            hi|=((a1[i]^a2[i])&np.uint64(M))<<np.uint64((i-4)*n)
        # combine lo,hi into structured for unique
        comb=np.empty(nsamp, dtype=[('lo','<u8'),('hi','<u8')])
        comb['lo']=lo; comb['hi']=hi
        vals,cnts=np.unique(comb, return_counts=True)
        mx=cnts.max()
        if mx>best: best=mx; bD=D
    return best/nsamp, bD

if __name__=="__main__":
    n=16; a,b=4,5; red=0x1002d  # x^16+x^5+x^3+x^2+1 primitive
    msb=1<<(n-1)
    ALL8=[1,2,3,5,7,11,13,17]
    deltas=[]
    plus=[0,2,4,6]
    for i in range(len(plus)):
        for j in range(i+1,len(plus)):
            D=[0]*8; D[plus[i]]=msb; D[plus[j]]=msb; deltas.append(tuple(D))
    NS=1<<22
    print(f"###### n=16 (state 128-bit) full-width w=8 all-8 σ, worst MSB-pair, nsamp=2^{int(math.log2(NS))} ######\n")
    prev=None
    for R in [1,2,3]:
        p,bD=worst_dp_n16(n,a,b,red,ALL8,deltas,R,NS, 7000+R)
        l2=math.log2(p) if p>0 else float('-inf')
        slope="" if prev is None else f"  Δw={(-l2)-prev:+.2f}"
        print(f"   R={R}: worst-δ DP=2^{l2:6.2f}  δ={tuple(hex(z) for z in bD)}{slope}", flush=True)
        prev=-l2
