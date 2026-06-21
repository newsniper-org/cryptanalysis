#!/usr/bin/env python3
"""Probe the prob-1 MSB-pair invariant seen at n=5,6 w=2. Why DP=1? Does it survive sigma?"""
import math
from adv_deep_prob1 import build, all_states

def trace_DP(n,w,rho,beta,eps,sigma,red,P,D,R):
    rnd,m=build(n,w,rho,beta,eps,sigma,red,P)
    states=list(all_states(n,w))
    img=list(states)
    for _ in range(R): img=[rnd(s) for s in img]
    M=(1<<n)-1
    cnt={}
    for i,s in enumerate(states):
        sd=tuple(s[k]^D[k] for k in range(w))
        # find index of sd
        pass
    # direct: recompute
    cnt={}
    def rR(s):
        for _ in range(R): s=rnd(s)
        return s
    for s in states:
        sd=tuple(s[k]^D[k] for k in range(w))
        od=tuple(rR(s)[i]^rR(sd)[i] for i in range(w))
        cnt[od]=cnt.get(od,0)+1
    mx=max(cnt.values()); bo=max(cnt,key=cnt.get)
    return mx/len(states), bo, cnt

n,w=5,2
M=(1<<n)-1
msb=1<<(n-1)
# D=0x88 means lane0=0x8, lane1=0x8? pack=sum w_i<<(i*n). 0x88 = 0b10001000.
# lane0 = 0x88 & 0x1f = 0x08; lane1 = (0x88>>5)&0x1f = 0x04. Hmm not MSB.
D=( (0x88)&M, (0x88>>n)&M )
print(f"n={n} w={w} D=0x88 -> lanes {tuple(hex(z) for z in D)}, MSB={hex(msb)}")
for cfg_name, sig in [("sig-both",[(0,1),(1,2)]), ("sig-none",[]), ("all8-ish",[(0,1),(1,2)])]:
    for R in [1,2,3]:
        p,bo,cnt=trace_DP(n,w,[1,2],3,[1,-1],sig,0x25,[1,0],D,R)
        print(f"  {cfg_name} R={R}: DP=2^{math.log2(p):.2f} -> out {tuple(hex(z) for z in bo)} ({len(cnt)} out-classes)")
    print()

# What IS the prob-1 diff at n=5? scan single+pair MSB combos
print("=== scan: which D give DP=1 at R=3 (sig-both) ===")
rnd,m=build(n,w,[1,2],3,[1,-1],[(0,1),(1,2)],0x25,[1,0])
states=list(all_states(n,w))
def rR(s,R):
    for _ in range(R): s=rnd(s)
    return s
found=[]
for cD in range(1,1<<(n*w)):
    D=tuple((cD>>(i*n))&M for i in range(w))
    o0=None;ok=True
    for s in states:
        sd=tuple(s[k]^D[k] for k in range(w))
        od=tuple(rR(s,3)[i]^rR(sd,3)[i] for i in range(w))
        if o0 is None:o0=od
        elif od!=o0:ok=False;break
    if ok:found.append((D,o0))
print(f"  prob-1 (DP=1) diffs at R=3: {len(found)}")
for D,o in found[:10]:
    print(f"    D={tuple(hex(z) for z in D)} -> {tuple(hex(z) for z in o)}")
