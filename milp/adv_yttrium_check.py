#!/usr/bin/env python3
"""
Adversarial independent re-implementation of the proposed yttrium Lai-Massey-ARX round.
Lens: prob1-subspace (primary), invertibility, farfalle-bridge.

Round (per proposal):
  (ι)  state[r mod 8] ^= RC[r]
  u_i = ROTL_{rho_i}(state_i)            rho=[0,5,11,17,23,3,13,29]
  S   = sum_i eps_i * u_i  (mod 2^32)    eps=[+1,-1,+1,-1,+1,-1,+1,-1]
  t   = F(S)                              F = 3-term AND
  v_i = u_i + t   ; y_i = ROTR_beta(v_i)  beta=9
  sigma: y0=a^1 y0, y2=a^3 y2, y4=a^5 y4, y6=a^7 y6   (GF(2^32), red 0x400007)
  pi: new_i = y_{P[i]}                    P=[7,4,1,6,3,0,5,2]
"""
import random

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr

def make_F(n):
    m,rotl,_=mk(n); pp=[((7%n),(17%n)),((3%n),(21%n)),((9%n),(29%n))]
    def F(s):
        acc=s
        for a,b in pp: acc^=(rotl(s,a)&rotl(s,b))
        return acc&m
    return F

def make_alpha(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a

# full-size params
N=32; W=8
RHO=[0,5,11,17,23,3,13,29]
EPS=[1,-1,1,-1,1,-1,1,-1]
SIGMA=[(0,1),(2,3),(4,5),(6,7)]   # (lane, k) -> alpha^k
PI=[7,4,1,6,3,0,5,2]
BETA=9
RED=0x400007

def make_alpha_inv(n,red):
    # forward alpha = mult by x in GF(2^n): (v<<1) ^ (red if msb(v) else 0).
    # inverse = div by x: if y odd -> v=((y^red)>>1)|(1<<(n-1)); else v=y>>1.
    assert red & 1 == 1
    top=1<<(n-1)
    def ainv(y):
        if y & 1:
            return ((y ^ red) >> 1) | top
        else:
            return y >> 1
    return ainv

def build(n,w,rho,eps,sigma,P,beta,red):
    m,rotl,rotr=mk(n); F=make_F(n); a=make_alpha(n,red); ai=make_alpha_inv(n,red)
    def apow(x,k):
        for _ in range(k): x=a(x)
        return x
    def apinv(x,k):
        for _ in range(k): x=ai(x)
        return x
    def Sval(state):
        s=0
        for i in range(w): s=(s+eps[i]*rotl(state[i],rho[i]))%(1<<n)
        return s
    def rnd(state,rc=0,rl=0):
        ws=list(state); ws[rl]=(ws[rl]^rc)&m
        u=[rotl(ws[i],rho[i]) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S)
        v=[(u[i]+t)&m for i in range(w)]
        y=[rotr(v[i],beta) for i in range(w)]
        for (ln,k) in sigma: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    def inv(state,rc=0,rl=0):
        out=list(state); y=[0]*w
        for i in range(w): y[P[i]]=out[i]
        for (ln,k) in sigma: y[ln]=apinv(y[ln],k)
        v=[rotl(y[i],beta) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*v[i])%(1<<n)
        t=F(S)
        u=[(v[i]-t)&m for i in range(w)]
        ws=[rotr(u[i],rho[i]) for i in range(w)]
        ws[rl]=(ws[rl]^rc)&m
        return tuple(ws)
    return rnd,inv,Sval,m

if __name__=="__main__":
    random.seed(11)
    rnd,inv,Sval,m=build(N,W,RHO,EPS,SIGMA,PI,BETA,RED)
    # ---- invertibility roundtrip at full size ----
    bad=0
    for _ in range(50000):
        st=tuple(random.randint(0,m) for _ in range(W))
        r=random.randint(0,3); rc=random.randint(0,m)
        if inv(rnd(st,rc=rc,rl=r),rc=rc,rl=r)!=st: bad+=1
    print(f"[invert] full-size n=32 roundtrip 50000: mismatches={bad}")

    # ---- multi-round permutation sanity (chain R rounds) ----
    def perm_chain(state,R):
        for r in range(R):
            state=rnd(state,rc=0,rl=r%W)
        return state
    def inv_chain(state,R):
        for r in reversed(range(R)):
            state=inv(state,rc=0,rl=r%W)
        return state
    bad2=0
    for _ in range(20000):
        st=tuple(random.randint(0,m) for _ in range(W))
        R=random.randint(1,6)
        if inv_chain(perm_chain(st,R),R)!=st: bad2+=1
    print(f"[invert] multi-round chain (1..6) 20000: mismatches={bad2}")
