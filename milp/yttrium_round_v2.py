#!/usr/bin/env python3
"""
yttrium round v2: distinct per-lane pre-rotations in the zero-sum reduction.
목적: additive prob-1 inactive subspace를 R≤2에 죽이면서 가역 유지.

reduction:   S = Σ_i ε_i · ROTL_{ρ_i}(x_i)  (mod 2^n),  Σ ε_i = 0
  ρ_i 가 lane마다 distinct → (d,d,0..) 같은 상수쌍 차분이 더는 자동 상쇄되지 않음.
combiner:    y_i = ROTR_β( ROTL_{ρ_i}(x_i) ⊞ t ),  t=F(S)     (회전 framing per-lane ρ_i)
  핵심: 결합기에 들어가는 회전을 reduction과 같은 ρ_i 로 쓰면 가역 항등식 유지:
     v_i = ROTL_β(y_i) = ROTL_{ρ_i}(x_i) ⊞ t
     Σ ε_i v_i = S ⊞ (Σε_i) t = S  (보존!)  → S 복원 → t → x_i = ROTR_{ρ_i}(v_i ⊟ t)
σ:  α-mult on selected lanes (⊕-orthomorphism; Farfalle mask-roll bridge 유지)
π:  word permutation

테스트: (1) 가역 전수(작은 state), (2) additive prob-1 inactive depth.
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

def build(n,w,rho,beta,eps,sigma_lanes,red,P):
    m,rotl,rotr=mk(n); F=make_F(n); a=make_alpha(n,red)
    ainv={a(x):x for x in range(1<<n)}
    def apow(x,k):
        for _ in range(k): x=a(x)
        return x
    def apinv(x,k):
        for _ in range(k): x=ainv[x]
        return x
    def Sval(state):
        s=0
        for i in range(w): s=(s+eps[i]*rotl(state[i],rho[i]))%(1<<n)
        return s
    def rnd(state,rc=0,rl=0):
        ws=list(state); ws[rl]^=rc; ws[rl]&=m
        u=[rotl(ws[i],rho[i]) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S)
        v=[(u[i]+t)&m for i in range(w)]
        y=[rotr(v[i],beta) for i in range(w)]
        for (ln,k) in sigma_lanes: y[ln]=apow(y[ln],k)
        return tuple(y[P[i]] for i in range(w))
    def inv(state,rc=0,rl=0):
        out=list(state); y=[0]*w
        for i in range(w): y[P[i]]=out[i]
        for (ln,k) in sigma_lanes: y[ln]=apinv(y[ln],k)
        v=[rotl(y[i],beta) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*v[i])%(1<<n)
        t=F(S)
        u=[(v[i]-t)&m for i in range(w)]
        ws=[rotr(u[i],rho[i]) for i in range(w)]
        ws[rl]^=rc; ws[rl]&=m
        return tuple(ws)
    return rnd,inv,Sval

def test_perm(n,w,rho,beta,eps,sigma_lanes,red,P):
    bits=n*w
    if bits>20:
        print(f"  perm: skip ({bits}b)"); return None
    rnd,inv,_=build(n,w,rho,beta,eps,sigma_lanes,red,P)
    m=(1<<n)-1; seen=set()
    for code in range(1<<bits):
        st=tuple((code>>(i*n))&m for i in range(w))
        seen.add(rnd(st))
    ok=len(seen)==(1<<bits)
    print(f"  perm(state {bits}b): {len(seen)}/{1<<bits} perm={ok}")
    return ok

def test_roundtrip(n,w,rho,beta,eps,sigma_lanes,red,P,trials=20000):
    rnd,inv,_=build(n,w,rho,beta,eps,sigma_lanes,red,P); m=(1<<n)-1; bad=0
    for _ in range(trials):
        st=tuple(random.randint(0,m) for _ in range(w)); rc=random.randint(0,m)
        if inv(rnd(st,rc=rc),rc=rc)!=st: bad+=1
    print(f"  roundtrip {trials}: mismatches={bad}")
    return bad

def additive_inactive_depth(n,w,rho,beta,eps,sigma_lanes,red,P,Rmax=5):
    """exact, small state: count nonzero Δ that remain prob-1 inactive (ΔS=0 ∀x) through R rounds
       with x-independent propagation."""
    m=(1<<n)-1; full=(n*w)<=16
    rnd,inv,Sval=build(n,w,rho,beta,eps,sigma_lanes,red,P)
    def xs():
        if full:
            for code in range(1<<(n*w)): yield tuple((code>>(i*n))&m for i in range(w))
        else:
            for _ in range(2000): yield tuple(random.randint(0,m) for _ in range(w))
    # R=1 survivors: Δ!=0 with Sval(x⊕Δ)=Sval(x) ∀x
    surv=[]
    for code in range(1,1<<(n*w)):
        D=tuple((code>>(i*n))&m for i in range(w)); ok=True
        for x in xs():
            xd=tuple(x[i]^D[i] for i in range(w))
            if Sval(xd)!=Sval(x): ok=False;break
        if ok: surv.append(code)
    res={1:len(surv)}; cur=surv; Rstar=1 if len(surv)==0 else None
    for R in range(2,Rmax+1):
        nxt=[]
        for code in cur:
            D=tuple((code>>(i*n))&m for i in range(w)); outd=None; cons=True; cnt=0
            for x in xs():
                ox=rnd(x); xd=tuple(x[i]^D[i] for i in range(w)); oxd=rnd(xd)
                od=tuple(ox[i]^oxd[i] for i in range(w))
                if outd is None: outd=od
                elif od!=outd: cons=False;break
                cnt+=1
                if cnt>=128 and not full: break
            if cons and outd is not None and any(outd):
                nxt.append(0|sum(outd[i]<<(i*n) for i in range(w)))
        # dedup & require still inactive
        nxt2=[]
        for oc in set(nxt):
            D=tuple((oc>>(i*n))&m for i in range(w)); ok=True
            for x in xs():
                if Sval(tuple(x[i]^D[i] for i in range(w)))!=Sval(x): ok=False;break
            if ok: nxt2.append(oc)
        res[R]=len(nxt2); cur=nxt2
        if len(nxt2)==0 and Rstar is None: Rstar=R
        if len(nxt2)==0: break
    return res,Rstar

if __name__=="__main__":
    random.seed(3)
    print("== v2 (distinct per-lane ρ_i reduction) ==")
    # small configs; rho distinct per lane
    cfgs=[
        ("n4w2 ρ=[0,1]", 4,2,[0,1],1,[1,-1],[(0,1)],0x3,[1,0]),
        ("n5w2 ρ=[0,2]", 5,2,[0,2],2,[1,-1],[(0,1)],0x5,[1,0]),
        ("n4w4 ρ=[0,1,2,3]",4,4,[0,1,2,3],1,[1,-1,1,-1],[(0,1),(2,1)],0x3,[3,0,1,2]),
        ("n5w4 ρ=[0,1,2,3]",5,4,[0,1,2,3],2,[1,-1,1,-1],[(0,1),(2,1)],0x5,[3,0,1,2]),
    ]
    for name,n,w,rho,beta,eps,sig,red,P in cfgs:
        print(f"[{name}]")
        test_perm(n,w,rho,beta,eps,sig,red,P)
        test_roundtrip(n,w,rho,beta,eps,sig,red,P,trials=15000)
        res,Rstar=additive_inactive_depth(n,w,rho,beta,eps,sig,red,P,5)
        print(f"  additive prob-1 inactive survivors/R: {res}  => R*(additive)={Rstar}")
        print()
