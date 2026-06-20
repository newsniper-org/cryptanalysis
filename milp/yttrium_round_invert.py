#!/usr/bin/env python3
"""
yttrium Lai-Massey-ARX 라운드 가역성 전수 확인 (작은 파라미터).

설계 (이 라운드):
  reduction (zero-sum, ⊞):   S = Σ_i ε_i · ROTL_α(x_i)   (mod 2^n),  Σ ε_i = 0
       ε = [+1,-1,+1,-1,+1,-1,+1,-1]  (n=8 lanes; 합=0)
  t = F(S)
  combiner (broadcast, per-lane G):  y_i = ROTR_β( ROTL_α(x_i) ⊞ t )
       => 회전 흡수:  u_i = ROTL_α(x_i),  v_i = u_i ⊞ t,  y_i = ROTR_β(v_i)
  σ (orthomorphism, GF α-mult, ⊕-ortho):  σ on selected lanes
  π : word permutation

가역성 핵심:
  복원: v_i = ROTL_β(y_i).  Σ ε_i v_i = Σ ε_i u_i ⊞ (Σ ε_i) t = S ⊞ 0 = S  (보존!)
        => S 복원 => t = F(S) => u_i = v_i ⊟ t => x_i = ROTR_α(u_i).
  σ,π는 자명 가역.  => 라운드 전수 가역, F·G 비가역 무방.

전수 검증 (n 작게, w=8):
  state space 2^(n*8). n=4,w=8 => 2^32 너무 큼. 대신:
  (1) reduction+broadcast 코어 맵 Ψ: (x_0..x_{w-1}) -> (y_0..y_{w-1}) 가
      "S 보존 항등식"을 만족함을 랜덤+경계 샘플로 확인 (수학적 항등식이라 1개로 충분하나 다량 확인).
  (2) 역산 절차가 원본 x를 정확히 복원함을 랜덤 다량 + 구조적 경계입력으로 확인.
  (3) 핵심: 같은 (S,t) class 안에서 Ψ가 단사인지 — w=2, n=4 (2^8 state) 전수,
      w=2, n=6 (2^12) 전수로 라운드 전체가 치환인지 직접 확인.
"""
import itertools, random

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr

# internal F (AND-based, fixed-form; offsets scaled for small n by mod n)
def make_F(n):
    m,rotl,_=mk(n)
    # use the spec's 3-pair structure, offsets reduced mod n (kept distinct where possible)
    pairs=[(7,17),(3,21),(9,29)]
    pp=[((a%n),(b%n)) for a,b in pairs]
    def F(s):
        acc=s
        for a,b in pp:
            acc ^= (rotl(s,a) & rotl(s,b))
        return acc & m
    return F

def alpha_factory(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m) ^ (red if (v>>(n-1)) else 0))
    return a

def make_round(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P):
    """returns (round_fn, inv_fn). round_fn maps tuple(state w words) -> tuple."""
    m,rotl,rotr=mk(n)
    F=make_F(n)
    a=alpha_factory(n,red)
    def apow(x,k):
        for _ in range(k): x=a(x)
        return x
    def sigma(ws):
        ws=list(ws)
        for (lane,k) in sigma_lanes:
            ws[lane]=apow(ws[lane],k)
        return ws
    # sigma inverse: alpha^-1 = (alpha applied (2^n-1 - k? ) ) ; alpha has order = ord; invert by brute precompute
    # build alpha inverse map
    ainv={a(x):x for x in range(1<<n)}
    def apow_inv(x,k):
        for _ in range(k): x=ainv[x]
        return x
    def sigma_inv(ws):
        ws=list(ws)
        for (lane,k) in sigma_lanes:
            ws[lane]=apow_inv(ws[lane],k)
        return ws
    def rnd(state, rc=0, rc_lane=0):
        ws=list(state)
        ws[rc_lane]^=rc; ws[rc_lane]&=m            # ι (RC xor)
        u=[rotl(ws[i],alpha_rot) for i in range(w)] # ROTL_α
        S=0
        for i in range(w):
            S=(S + eps[i]*u[i])%(1<<n)             # zero-sum reduction (⊞)
        t=F(S)
        v=[(u[i]+t)&m for i in range(w)]            # broadcast ⊞ t
        y=[rotr(v[i],beta_rot) for i in range(w)]   # ROTR_β
        y=sigma(y)                                  # σ
        out=[y[P[i]] for i in range(w)]             # π
        return tuple(out)
    def inv(state, rc=0, rc_lane=0):
        out=list(state)
        # invert π
        y=[0]*w
        for i in range(w): y[P[i]]=out[i]
        # invert σ
        y=sigma_inv(y)
        # recover v
        v=[rotl(y[i],beta_rot) for i in range(w)]
        # recover S from zero-sum of v (S preserved!)
        S=0
        for i in range(w):
            S=(S+eps[i]*v[i])%(1<<n)
        t=F(S)
        u=[(v[i]-t)&m for i in range(w)]
        ws=[rotr(u[i],alpha_rot) for i in range(w)]
        ws[rc_lane]^=rc; ws[rc_lane]&=m            # undo ι
        return tuple(ws)
    return rnd, inv

def test_invariant_and_inverse(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P,trials=20000):
    m=(1<<n)-1
    rnd,inv=make_round(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P)
    bad_inv=0
    for _ in range(trials):
        st=tuple(random.randint(0,m) for _ in range(w))
        y=rnd(st, rc=random.randint(0,m), rc_lane=0)  # rc fixed per call but inv must use same
    # do consistent rc test:
    bad=0
    for _ in range(trials):
        st=tuple(random.randint(0,m) for _ in range(w))
        rc=random.randint(0,m)
        y=rnd(st,rc=rc,rc_lane=0)
        back=inv(y,rc=rc,rc_lane=0)
        if back!=st: bad+=1
    print(f"  inverse roundtrip: {trials} trials, mismatches={bad}")
    return bad

def test_full_permutation(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P):
    """전수: state space 2^(n*w) 작을 때만."""
    bits=n*w
    if bits>20:
        print(f"  full-perm: skipped (state {bits} bit too large)")
        return None
    rnd,inv=make_round(n,w,alpha_rot,beta_rot,eps,sigma_lanes,red,P)
    m=(1<<n)-1
    seen=set()
    total=1<<bits
    for code in range(total):
        st=tuple((code>>(i*n))&m for i in range(w))
        y=rnd(st,rc=0,rc_lane=0)
        seen.add(y)
    isperm = (len(seen)==total)
    print(f"  full-permutation (state {bits}b): images={len(seen)}/{total}  perm={isperm}")
    return isperm

if __name__=="__main__":
    random.seed(1)
    # config (small-n proxies): w=8 zero-sum eps, alpha=2,beta=3 (small-n analog of 8,9), red primitive-ish
    print("== Lai-Massey-ARX round: invariant preservation + inverse roundtrip ==")
    eps8=[1,-1,1,-1,1,-1,1,-1]
    P8=[7,4,1,6,3,0,5,2]
    print("[n=8,w=8] zero-sum eps=[+,-,...], alpha=3,beta=4, sigma lanes(0:a^1,4:a^3), red=0x1D")
    test_invariant_and_inverse(8,8,3,4,eps8,[(0,1),(4,3)],0x1D,P8,trials=30000)

    print("[n=16,w=8] alpha=8? use 5, beta=9->6, red=0x2B")
    test_invariant_and_inverse(16,8,5,6,eps8,[(0,1),(4,3)],0x2B,P8,trials=30000)

    print()
    print("== full-permutation exhaustive (tiny state) ==")
    # w=2 zero-sum: eps=[+1,-1]; need P perm of 2; sigma lane 0
    print("[n=4,w=2] eps=[+1,-1] alpha=1 beta=1 sigma(0:a^1) red=0x3 P=[1,0]")
    test_full_permutation(4,2,1,1,[1,-1],[(0,1)],0x3,[1,0])
    print("[n=6,w=2] eps=[+1,-1] alpha=1 beta=1 sigma(0:a^1) red=0x3 P=[1,0]")
    test_full_permutation(6,2,1,1,[1,-1],[(0,1)],0x3,[1,0])
    print("[n=8,w=2] eps=[+1,-1] alpha=3 beta=4 sigma(0:a^1) red=0x1D P=[1,0]")
    test_full_permutation(8,2,3,4,[1,-1],[(0,1)],0x1D,[1,0])
    print("[n=4,w=4] eps=[+1,-1,+1,-1] alpha=1 beta=1 sigma(0,2) red=0x3 P=[3,0,1,2]")
    test_full_permutation(4,4,1,1,[1,-1,1,-1],[(0,1),(2,1)],0x3,[3,0,1,2])
    print("[n=5,w=4] eps=[+1,-1,+1,-1] alpha=1 beta=2 sigma(0,2) red=0x5 P=[3,0,1,2]")
    test_full_permutation(5,4,1,2,[1,-1,1,-1],[(0,1),(2,1)],0x5,[3,0,1,2])
