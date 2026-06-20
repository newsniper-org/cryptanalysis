#!/usr/bin/env python3
"""
'바닥(2^-14)'의 정체 규명 + 정확법 전환.
(A) 바닥 ∝ 1/N (통계적 표본 해상도)임을 N sweep으로 입증 — 부동소수점 무관.
(B) 정확한 V_7 비활성 차분 δ 추출 → σ-GLM은 prob-1(결정적), ARX는 prob-1 소멸.
    prob-1 검출은 '모든 표본이 동일 출력차분'(np.unique==1) → 표본수와 무관하게 정확.
"""
import numpy as np
MASK=np.uint64(0xFFFFFFFF); RED=np.uint64(0x400007); P_PI=[7,4,1,6,3,0,5,2]
ARX_L,ARX_R=8,3
def rotl(x,k):
    k%=32
    return x&MASK if k==0 else ((x<<np.uint64(k))|(x>>np.uint64(32-k)))&MASK
def rotr(x,k): return rotl(x,(32-k)%32)
def alpha(y):
    top=(y>>np.uint64(31))&np.uint64(1); return ((y<<np.uint64(1))&MASK)^(top*RED)
def alpha_pow(y,k):
    for _ in range(k): y=alpha(y)
    return y
def Ffun(s,terms):
    o=s.copy()
    for (a,b) in terms: o^=rotl(s,a)&rotl(s,b)
    return o&MASK
def permute(state,rounds,comb,terms,sigma):
    st=[state[i].copy() for i in range(8)]
    for _ in range(rounds):
        S=st[0].copy()
        for i in range(1,8): S=S^st[i]
        t=Ffun(S,terms)
        new=[st[i]^t for i in range(8)] if comb=='xor' else \
            [rotr((rotl(st[i],ARX_L)+t)&MASK,ARX_R) for i in range(8)]
        for (lane,k) in sigma: new[lane]=alpha_pow(new[lane],k)
        st=[new[P_PI[i]] for i in range(8)]
    return np.stack(st)

F3=[(7,17),(3,21),(9,29)]; SIG=[(0,1),(4,3)]

# ---------- (A) 바닥 ∝ 1/N ----------
def best_dp_count(rounds,comb,terms,sigma,N,seed=0):
    rng=np.random.default_rng(seed)
    base=rng.integers(0,1<<32,size=(8,N),dtype=np.uint64)
    d=np.zeros(8,dtype=np.uint64); d[0]=np.uint64(1)   # 단일 활성 차분
    diff=permute(base,rounds,comb,terms,sigma)^permute(base^d[:,None],rounds,comb,terms,sigma)
    _,c=np.unique(diff.T,axis=0,return_counts=True)
    return int(c.max())
print("=== (A) '바닥'은 통계(1/N)지 부동소수점이 아님 — ARX R=8, N sweep ===")
for N in (20000,200000,2000000):
    cmax=best_dp_count(8,'arx',F3,SIG,N)
    print(f"  N={N:>9}: counts.max()={cmax:>3} (정수,정확)  → DP≈{cmax}/{N}=2^-{np.log2(N/cmax):.1f}  (바닥이 N 따라 내려감)")

# ---------- (B) 정확한 V_7 δ ----------
def lin(v):  # σ-GLM 비활성(t=0) 선형 라운드: σ∘π
    w=list(v); w[0]=alpha_pow(int(w[0]),1)&0xFFFFFFFF; w[4]=alpha_pow(int(w[4]),3)&0xFFFFFFFF
    return [w[P_PI[i]] for i in range(8)]
def xorsum(v):
    s=0
    for x in v: s^=int(x)
    return s&0xFFFFFFFF
# alpha_pow on python int
def alpha_i(y):
    top=(y>>31)&1; return (((y<<1)&0xFFFFFFFF)^(RED_i if top else 0))
RED_i=0x400007
def alpha_pow_i(y,k):
    for _ in range(k): y=alpha_i(y)
    return y
def lin_i(v):
    w=list(v); w[0]=alpha_pow_i(v[0],1); w[4]=alpha_pow_i(v[4],3)
    return [w[P_PI[i]] for i in range(8)]
def xs_i(v):
    s=0
    for x in v: s^=x
    return s
def gf2_kernel_vec(rows, ncols):
    piv={}                                   # pivot_col -> reduced row (leading bit = pivot_col)
    for r in rows:
        cur=r
        for c in sorted(piv, reverse=True):
            if (cur>>c)&1: cur^=piv[c]
        if cur:
            piv[cur.bit_length()-1]=cur
    # 완전 RREF: 각 pivot 행에서 다른 pivot 열 제거
    pcols=sorted(piv)
    for c in pcols:
        pr=piv[c]
        for c2 in pcols:
            if c2!=c and (pr>>c2)&1: pr^=piv[c2]
        piv[c]=pr
    pivset=set(pcols)
    free=next((c for c in range(ncols) if c not in pivset),None)
    if free is None: return 0
    vec=1<<free
    for c in pcols:
        if (piv[c]>>free)&1: vec|=1<<c
    return vec
# build constraint matrix C: column k = stacked xorsum(lin^r e_k), r=0..6 (224 bit); rows=224
NC=256; R=7
Mrows=[0]*(32*R)
for k in range(NC):
    wi=k//32; bit=k%32
    v=[0]*8; v[wi]=1<<bit
    cur=v
    for r in range(R):
        xs=xs_i(cur)
        for b in range(32):
            if (xs>>b)&1: Mrows[r*32+b]|=(1<<k)
        cur=lin_i(cur)
delta_int=gf2_kernel_vec(Mrows,NC)
dverts=[(delta_int>>(i*32))&0xFFFFFFFF for i in range(8)]
# verify δ ∈ V_7
ok=[]
cur=dverts
for r in range(9):
    ok.append(xs_i(cur)==0); cur=lin_i(cur)
print(f"\n=== (B) 정확한 V_7 δ = {[hex(x) for x in dverts]} ===")
print(f"  δ∈V_r 검증: r=0..8 의 xorsum==0? {ok}  (R<8 True, R≥8 False 기대)")

def is_prob1(rounds,comb,N=4096,seed=1):
    rng=np.random.default_rng(seed)
    base=rng.integers(0,1<<32,size=(8,N),dtype=np.uint64)
    dd=np.array(dverts,dtype=np.uint64)
    diff=permute(base,rounds,comb,F3,SIG)^permute(base^dd[:,None],rounds,comb,F3,SIG)
    nuniq=np.unique(diff.T,axis=0).shape[0]
    return nuniq==1, nuniq
print("\n  같은 δ를 σ-GLM(XOR) vs ARX 에 통과 — prob-1(결정적)인가? (표본 무관, 정확)")
print(f"  {'R':>3} | {'σ-GLM XOR':<22} | {'Amaryllises+ARX':<22}")
for r in (2,4,6,7,8,10):
    px,nx=is_prob1(r,'xor'); pa,na=is_prob1(r,'arx')
    sx=f"prob-1 ✅" if px else f"비결정({nx} 출력차분)"
    sa=f"prob-1 ❌" if pa else f"비결정({na} 출력차분)"
    print(f"  {r:>3} | {sx:<22} | {sa:<22}")
