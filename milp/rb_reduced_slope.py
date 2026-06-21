#!/usr/bin/env python3
"""
R_b 차원 — 축소폭(n=8,16) 깊은-라운드 weight 기울기 (per-round DP 증가 추정).

목적: GPU full-word(N=2^30, floor~2^-25)는 R3쯤에서 floor에 닿아 깊은 라운드
weight 기울기를 못 본다. n=8 축소폭은 표본을 크게 잡아 floor를 낮추고(=깊은 라운드
DP 관측) per-round Δweight 의 점근 기울기를 추정한다. 이를 full-word(n=32)로
스케일(weight ∝ n 근사)해 R_b 필요라운드 외삽 근거를 만든다.

라운드는 rb_acc_collision.py 와 동일(yttrium LM). 표본 floor가 2^-22 (4M 표본)까지 내려간다.
"""
import random, math
from collections import Counter
from rb_acc_collision import make_round, permute

def emp_worst_dp(R, rnd, n, samples, ndelta=40):
    """ndelta개 입력차분 후보(단일/2비트/MSB쌍) 중 worst-δ best-DP."""
    msb = 1 << (n-1)
    plus=[0,2,4,6]; minus=[1,3,5,7]
    cands=[]
    for a_ in range(4):
        for b_ in range(a_+1,4):
            d=[0]*8; d[plus[a_]]=msb; d[plus[b_]]=msb; cands.append(tuple(d))
    for bit in (0, n//2, n-1):
        d=[0]*8; d[0]=1<<bit; cands.append(tuple(d))
    for w0 in range(8):
        d=[0]*8; d[w0]=msb; cands.append(tuple(d))
    best=0.0
    for d in cands:
        c=Counter()
        for _ in range(samples):
            x=[random.getrandbits(n) for _ in range(8)]
            y=[x[i]^d[i] for i in range(8)]
            ox=permute(x,R,rnd); oy=permute(y,R,rnd)
            dd=tuple(ox[i]^oy[i] for i in range(8))
            c[dd]+=1
        top=c.most_common(1)[0][1]/samples
        if top>best: best=top
    return best

if __name__=="__main__":
    random.seed(7)
    for (n,red,sig) in [(8,0x1D,[1,2,3,1,2,3,1,2]), (16,0x00B,[1,2,3,5,7,1,2,3])]:
        rnd,M=make_round(n,red,8 % n if n<32 else 8, 9 % n if n<32 else 9, sig)
        print(f"=== n={n} 축소폭 (state {8*n} bit), per-round weight 기울기 ===")
        SAMPLES = 2_000_000 if n==8 else 1_500_000
        floor = math.log2(SAMPLES)
        prev=None
        for R in range(1,7):
            p=emp_worst_dp(R,rnd,n,SAMPLES)
            w=-math.log2(p) if p>0 else 999
            slope = "" if prev is None else f"  Δw=+{w-prev:.1f}"
            atfloor = "  [≈floor]" if w>=floor-0.6 else ""
            print(f"  R={R}: worst-δ DP ≈ 2^-{w:.1f}{slope}{atfloor}")
            prev=w
        print(f"  (sample floor ~2^-{floor:.1f})\n")
