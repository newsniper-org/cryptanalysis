#!/usr/bin/env python3
"""
ADVERSARIAL verification of the yttrium Lai-Massey-ARX proposal.
Lens: invertibility (round permutation + zero-sum S recovery), prob1-subspace,
farfalle-bridge.

I re-implement the round EXACTLY per the proposal's round_equations / inversion_procedure
(NOT trusting the proposal's own helper files), parameterized by (n, w, rho, beta, eps,
sigma_lanes, sigma_k, red, P), so I can run n=8/16 exhaustively.

round(state, r):
  (i)  state[r mod w] ^= RC[r]
  u_i = ROTL_{rho_i}(state_i)
  S = sum_i eps_i * u_i  (mod 2^n)
  t = F(S)
  v_i = u_i + t (mod 2^n)
  y_i = ROTR_beta(v_i)
  sigma: y[ln] = alpha^k (y[ln]) for (ln,k) in sigma  (applied AFTER ROTR, per proposal)
  pi: new_i = y[P[i]]
"""
import random, itertools

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n
        return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr

def make_alpha(n,red):
    M=(1<<n)-1
    def a(v): return (((v<<1)&M)^(red if (v>>(n-1))&1 else 0))
    return a

def make_F(n):
    m,rotl,_=mk(n); pp=[(7%n,17%n),(3%n,21%n),(9%n,29%n)]
    def F(s):
        acc=s
        for a,b in pp: acc^=rotl(s,a)&rotl(s,b)
        return acc&m
    return F

def build_round(n,w,rho,beta,eps,sigma,red,P,RC=None):
    m,rotl,rotr=mk(n); F=make_F(n); a=make_alpha(n,red)
    def apow(x,k):
        if k>=0:
            for _ in range(k): x=a(x)
            return x
        else:
            raise ValueError("use inverse explicitly")
    M=(1<<n)-1
    def Sval(state):
        s=0
        for i in range(w): s=(s+eps[i]*rotl(state[i],rho[i]))%(1<<n)
        return s
    def rnd(state, r=0):
        st=list(state)
        if RC is not None:
            st[r%w]^=RC[r%len(RC)]
        u=[rotl(st[i],rho[i]) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S)
        v=[(u[i]+t)&M for i in range(w)]
        y=[rotr(v[i],beta) for i in range(w)]
        for (ln,k) in sigma: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    # build alpha inverse map by brute (n small)
    amap={x:a(x) for x in range(1<<n)}
    ainv={v:x for x,v in amap.items()}
    assert len(ainv)==(1<<n), "alpha not a permutation!"
    def apow_inv(x,k):
        for _ in range(k): x=ainv[x]
        return x
    Pinv=[0]*w
    for i in range(w): Pinv[P[i]]=i
    def rnd_inv(state, r=0):
        # invert pi
        y=[0]*w
        for i in range(w): y[P[i]]=state[i]
        # invert sigma
        for (ln,k) in sigma: y[ln]=apow_inv(y[ln],k)
        # invert ROTR_beta -> ROTL_beta
        v=[rotl(y[i],beta) for i in range(w)]
        # recover S via zero-sum
        S=0
        for i in range(w): S=(S+eps[i]*v[i])%(1<<n)
        t=F(S)
        u=[(v[i]-t)&M for i in range(w)]
        st=[rotr(u[i],rho[i]) for i in range(w)]
        if RC is not None:
            st[r%w]^=RC[r%len(RC)]
        return tuple(st)
    return rnd, rnd_inv, Sval, M

def test_permutation(n,w,rho,beta,eps,sigma,red,P):
    rnd,rnd_inv,Sval,M=build_round(n,w,rho,beta,eps,sigma,red,P)
    seen={}
    total=1<<(n*w)
    if total>(1<<22):
        return None  # too big for full perm
    collide=None
    for c in range(total):
        st=tuple((c>>(i*n))&M for i in range(w))
        o=rnd(st)
        if o in seen:
            collide=(seen[o],st,o); break
        seen[o]=st
    is_perm=(collide is None) and (len(seen)==total)
    return is_perm, collide, len(seen), total

def test_roundtrip(n,w,rho,beta,eps,sigma,red,P,RC,trials=20000):
    rnd,rnd_inv,Sval,M=build_round(n,w,rho,beta,eps,sigma,red,P,RC)
    bad=0; ex=None
    for _ in range(trials):
        st=tuple(random.randint(0,M) for _ in range(w))
        r=random.randint(0,63)
        o=rnd(st,r)
        back=rnd_inv(o,r)
        if back!=st:
            bad+=1
            if ex is None: ex=(st,r,o,back)
    return bad, ex

if __name__=="__main__":
    random.seed(1)
    # Proposal's stated full-perm cases. Use proposal's small params.
    cases=[
        # (n,w,rho,beta,eps,sigma,red,P)  -- mirror proposal la_test_code part (B)
        (4,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
        (5,2,[0,2],2,[1,-1],[(0,1)],0x5,[1,0]),
        (4,4,[0,1,2,3],1,[1,-1,1,-1],[(0,1),(2,1)],0x3,[3,0,1,2]),
        (5,4,[0,1,2,3],2,[1,-1,1,-1],[(0,1),(2,1)],0x5,[3,0,1,2]),
    ]
    print("=== PERMUTATION TEST (full exhaustive where feasible) ===")
    for (n,w,rho,beta,eps,sigma,red,P) in cases:
        res=test_permutation(n,w,rho,beta,eps,sigma,red,P)
        if res is None:
            print(f"  n={n} w={w}: state too big, skip")
        else:
            is_perm,coll,seen,total=res
            print(f"  n={n} w={w} state={n*w}b: perm={is_perm} seen={seen}/{total} collide={coll}")

    print("\n=== ROUNDTRIP TEST (with random RC) ===")
    RC=[random.randint(0,(1<<31)-1) for _ in range(64)]
    for (n,w,rho,beta,eps,sigma,red,P) in cases:
        RCn=[x & ((1<<n)-1) for x in RC]
        bad,ex=test_roundtrip(n,w,rho,beta,eps,sigma,red,P,RCn,trials=30000)
        print(f"  n={n} w={w}: roundtrip mismatch={bad}/30000  ex={ex}")
