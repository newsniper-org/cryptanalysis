#!/usr/bin/env python3
"""
n=32 (full word) MSB-invariant 직접 검증 — 작은 n 전수에서 규명한 'MSB-쌍 불변'이
실제 워드폭에서 σ 구성에 의해 R≤2 에 소멸하는지.

규명된 사실(작은 n 전수, yttrium_probe_invariant.py):
  유일한 prob-1 inactive 차분류 = "ROTL_α 이후 MSB만 ±짝으로 뒤집는" 차분.
  즉 Δ_i = ROTR_α(2^(n-1)) = 2^(n-1-α mod n) 를 active lane 들에 짝수개 깔면
       ΔS = Σε_i·(±2^(n-1)) ≡ 0 (mod 2^n)  (부호가 짝수개 상쇄).
  이 차분이 prob-1 inactive (모든 x에서 ΔS=0): Δt=0 → 라운드 선형.

R≤2 소멸 조건:
  1라운드 후 차분이 다시 MSB-쌍 inactive 로 남지 않아야(=ΔS_2≠0 강제) 한다.
  비활성 1라운드의 선형작용:  per-lane  L = ROTR_β∘ROTL_α (Δt=0),  그 후 σ(GF α-곱), π.
  σ 가 적용된 lane 의 MSB 비트는 α-곱(<<1 (+red))으로 *하위로 이동/확산*되어
  다음 reduction 의 ROTL_α 정렬에서 MSB 에 안 맞음 → ΔS_2≠0.
  σ 미적용 lane 의 MSB 는 L=회전으로 위치만 바뀌고 다음 ROTL_α 로 다시 MSB 가능 → 살아남음.

따라서: 모든 lane 에 σ(distinct α-power) 적용해야 모든 MSB-쌍이 R≤2 에 죽는다 — 이를
n=32 에서 직접 확인.

방법: MSB-pair inactive 차분 공간은 GF(2)-선형(차분이 단일 비트 MSB-after-rot 의 부분집합,
짝수 패리티). 그 공간에서 1라운드 선형작용 적용 후 다시 reduction-inactive 인 부분공간을
GF(2) rank 로 정확히 계산. (이건 정확—MSB 차분은 carry 없이 ΔS 에 ±2^(n-1) 만 기여하고
그 부호상쇄는 GF(2) 패리티로 환원.)
"""

def rotl(x,k,n):
    k%=n; m=(1<<n)-1
    return ((x<<k)|(x>>(n-k)))&m if k else x&m
def rotr(x,k,n): return rotl(x,(n-(k%n))%n,n)
def make_alpha(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a

def gf2_rank(cols):
    basis=[]
    for v in cols:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)

def measure(n,w,red,sigma,P,alpha_rot,beta_rot,Rmax):
    """
    full GF(2)-LA on the *signed-sum* reduction's mod-2 image, with the CORRECT yttrium
    linear layer (per-lane combiner rotation ROTR_β∘ROTL_α, then σ, then π).
    reduction functional over GF(2): r(Δ) = ⊕_i ROTL_α(Δ_i)   [signed-sum mod 2; |ε|=1].
    Lin(Δ): per-lane L=ROTR_β∘ROTL_α ; σ (α-mult, GF(2)-linear) ; π.
    inactive subspace V_R = {Δ: r(Lin^k Δ)=0, k<R}. dim->0 at R*.
    NOTE: GF(2)-LA captures *all* linear invariants incl. the MSB one's parity image.
    """
    N=n*w; m=(1<<n)-1
    a=make_alpha(n,red)
    def apow(v,k):
        for _ in range(k): v=a(v)
        return v
    def words(s): return [(s>>(i*n))&m for i in range(w)]
    def pack(ws):
        s=0
        for i,x in enumerate(ws): s|=(x&m)<<(i*n)
        return s
    def Lin(s):
        ws=words(s)
        ws=[rotr(rotl(ws[i],alpha_rot,n),beta_rot,n) for i in range(w)]   # combiner linear part
        for (lane,k) in sigma: ws[lane]=apow(ws[lane],k)
        return pack([ws[P[i]] for i in range(w)])
    def red(s):
        ws=words(s); r=0
        for x in ws: r^=rotl(x,alpha_rot,n)
        return r
    Rstar=None; out=[]
    for R in range(1,Rmax+1):
        cols=[]
        for k in range(N):
            cur=1<<k; col=0
            for r in range(R):
                col|=red(cur)<<(r*n); cur=Lin(cur)
            cols.append(col)
        d=N-gf2_rank(cols)
        out.append((R,d))
        if d==0 and Rstar is None: Rstar=R
        if d==0: break
    return out,Rstar

def run(name,n,w,red,sigma,P,A,B,Rmax=12):
    o,Rs=measure(n,w,red,sigma,P,A,B,Rmax)
    print(f"== {name}: σ={sigma}, (α,β)=({A},{B}) ==")
    for R,d in o:
        tag="  <- R*" if d==0 else ""
        print(f"   R={R:2d}: dim(inactive)={d:4d}{tag}")
    print(f"   => R* = {Rs}\n")
    return Rs

if __name__=="__main__":
    P=[7,4,1,6,3,0,5,2]; RED=0x400007
    print("[현행 SPEC σ{0,4}]  (불충분 예상: 미적용 lane 의 MSB 불변 잔존)")
    run("σ{0,4}",32,8,RED,[(0,1),(4,3)],P,8,9)
    print("[제안: 전 lane σ, distinct α-powers 1..8]  (R≤2 소멸 목표)")
    run("σ all 1..8",32,8,RED,[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8)],P,8,9)
    print("[제안 대안: 전 lane σ, odd distinct powers]")
    run("σ all odd",32,8,RED,[(0,1),(1,3),(2,5),(3,7),(4,9),(5,11),(6,13),(7,15)],P,8,9)
    print("[β=3 변형]")
    run("σ all 1..8 (8,3)",32,8,RED,[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8)],P,8,3)
