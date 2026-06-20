#!/usr/bin/env python3
"""
Part (B)에서 살아남은 prob-1 inactive Δ 의 정체 규명 + σ(orthomorphism)이 그것을 죽이는지.

가설: S = Σ ε_i ROTL_α(x_i) (mod 2^n). |ε_i|=1, Σε_i=0.
  Δ 가 각 active lane 의 *MSB* 만 (ROTL_α 이후 MSB) ± 짝으로 뒤집으면 ΔS = ±2^(n-1)∓2^(n-1)=0.
  => MSB-쌍 차분은 prob-1 inactive. 이것이 깨야 할 Lai-Massey 잔존 불변.

σ(GF α-곱)이 lane 0,4 에 적용되어 MSB 를 하위로 흩뿌리면(α-곱은 <<1 + 조건부 red)
다음 라운드 reduction 에서 ΔS≠0 이 되어 불변이 깨져야 한다. 어느 σ-레인/거듭제곱이
모든 MSB-쌍 불변을 R≤2 에 죽이는지 작은 n 전수로 측정.
"""
import itertools

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr
def make_alpha(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a
def make_F(n):
    m,rotl,_=mk(n); pp=[((7%n),(17%n)),((3%n),(21%n)),((9%n),(29%n))]
    def F(s):
        acc=s
        for a,b in pp: acc^=(rotl(s,a)&rotl(s,b))
        return acc&m
    return F

def round_state(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,state):
    m,rotl,rotr=mk(n); F=make_F(n); alpha=make_alpha(n,red)
    def apow(x,k):
        for _ in range(k): x=alpha(x)
        return x
    ws=list(state)
    u=[rotl(ws[i],alpha_rot) for i in range(w)]
    S=0
    for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
    t=F(S)
    v=[(u[i]+t)&m for i in range(w)]
    y=[rotr(v[i],beta_rot) for i in range(w)]
    for (lane,k) in sigma_lanes: y[lane]=apow(y[lane],k)
    return tuple(y[P[i]] for i in range(w))

def Sval(n,w,alpha_rot,eps,state):
    m,rotl,_=mk(n)
    u=[rotl(state[i],alpha_rot) for i in range(w)]
    s=0
    for i in range(w): s=(s+eps[i]*u[i])%(1<<n)
    return s

def survivors(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,Rmax):
    """모든 비영 Δ 중, R 라운드 동안 (모든 x에서 ΔS=0 & x-독립 출력차분) 유지되는 Δ 추적."""
    m=(1<<n)-1
    allx=[tuple((c>>(i*n))&m for i in range(w)) for c in range(1<<(n*w))]
    def is_round1_inactive(D):
        for x in allx:
            xd=tuple(x[i]^D[i] for i in range(w))
            if Sval(n,w,alpha_rot,eps,xd)!=Sval(n,w,alpha_rot,eps,x): return False
        return True
    cur=[]
    for c in range(1,1<<(n*w)):
        D=tuple((c>>(i*n))&m for i in range(w))
        if is_round1_inactive(D): cur.append(D)
    res={1:list(cur)}
    for R in range(2,Rmax+1):
        nxt=[]
        for D in cur:
            od=None; ok=True
            for x in allx:
                a=round_state(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,x)
                b=round_state(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,tuple(x[i]^D[i] for i in range(w)))
                d=tuple(a[i]^b[i] for i in range(w))
                if od is None: od=d
                elif d!=od: ok=False; break
            if ok and od is not None and any(od):
                # require output diff also round-1 inactive
                if is_round1_inactive(od): nxt.append(D)
        res[R]=list(nxt); cur=nxt
        if not nxt: break
    return res

def show(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,Rmax=4):
    r=survivors(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,Rmax)
    counts={R:len(v) for R,v in r.items()}
    samp=r[1][:6]
    print(f"  [n={n},w={w},(α,β)=({alpha_rot},{beta_rot}),σ={sigma_lanes}] survivors/R={counts}")
    print(f"     round-1 inactive Δ (sample, hex per lane): {[tuple(hex(z) for z in D) for D in samp]}")
    return counts

if __name__=="__main__":
    print("== 살아남은 Δ 의 정체 (MSB-쌍 가설) + σ 효과 ==")
    print("[no σ] (불변 그대로 살아야 함)")
    show(4,2,1,1,[1,-1],[],0x3,[1,0])
    show(4,4,1,1,[1,-1,1,-1],[],0x3,[3,0,1,2])
    print("[σ on lane0 only, α^1]")
    show(4,2,1,1,[1,-1],[(0,1)],0x3,[1,0])
    show(4,4,1,1,[1,-1,1,-1],[(0,1)],0x3,[3,0,1,2])
    print("[σ on ALL lanes, distinct powers] — MSB 분쇄 시도")
    show(4,2,1,1,[1,-1],[(0,1),(1,2)],0x3,[1,0])
    show(4,4,1,1,[1,-1,1,-1],[(0,1),(1,2),(2,3),(3,1)],0x3,[3,0,1,2])
    print("[σ on every ACTIVE-pair lane, ensure no two share canceling structure]")
    show(5,2,1,2,[1,-1],[(0,1),(1,2)],0x5,[1,0])
    show(5,4,1,2,[1,-1,1,-1],[(0,1),(1,2),(2,3),(3,1)],0x5,[3,0,1,2])
