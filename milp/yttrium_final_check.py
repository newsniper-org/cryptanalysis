#!/usr/bin/env python3
"""
yttrium FINAL round (w=8) sanity: distinct per-lane ρ reduction + α-mult σ.
- roundtrip invert (n=8,16; w=8) 전수표본
- σ orthomorphism(⊕) 재확인 (full n where exhaustive: n=8,16)
- GF(2)-LA inactive depth with per-lane pre-rotation in the LINEAR reduction
  (per-lane ρ_i 가 선형층에도 들어가므로 R*가 내려가는지 확인)
"""
import random
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr
def make_F(n):
    m,rotl,_=mk(n); pp=[(7%n,17%n),(3%n,21%n),(9%n,29%n)]
    def F(s):
        acc=s
        for a,b in pp: acc^=rotl(s,a)&rotl(s,b)
        return acc&m
    return F
def make_alpha(n,red):
    m=(1<<n)-1
    def a(v): return (((v<<1)&m)^(red if (v>>(n-1)) else 0))
    return a

# full-size proposal (n=32): rho per lane, beta single, eps zero-sum, sigma lanes, P_PI
RHO32=[0,5,11,17,23,3,13,29]   # distinct per-lane pre-rotations (NUMS-ish, all distinct mod 32)
EPS=[1,-1,1,-1,1,-1,1,-1]
PPI=[7,4,1,6,3,0,5,2]
SIG=[(0,1),(2,3),(4,5),(6,7)]  # α^1,α^3,α^5,α^7 on even lanes  (distinct-μ, ortho ⊕)
BETA=9

def build(n,w,rho,beta,eps,sigma_lanes,red,P):
    m,rotl,rotr=mk(n); F=make_F(n); a=make_alpha(n,red)
    ainv={a(x):x for x in range(1<<n)} if n<=16 else None
    def apow(x,k):
        for _ in range(k): x=a(x)
        return x
    def apinv(x,k):
        for _ in range(k): x=ainv[x]
        return x
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
    return rnd,inv

def roundtrip(n,w,rho,beta,eps,sig,red,P,trials):
    rnd,inv=build(n,w,rho,beta,eps,sig,red,P); m=(1<<n)-1; bad=0
    for _ in range(trials):
        st=tuple(random.randint(0,m) for _ in range(w)); rc=random.randint(0,m)
        if inv(rnd(st,rc=rc),rc=rc)!=st: bad+=1
    return bad

def sigma_ortho(n,red,k):
    a=make_alpha(n,red); m=(1<<n)-1
    def ap(x):
        for _ in range(k): x=a(x)
        return x
    # perm
    seen=bytearray(1<<n);
    for x in range(1<<n):
        y=ap(x)
        if seen[y]: return (False,False)
        seen[y]=1
    # ortho ⊕
    seen=bytearray(1<<n); ortho=True
    for x in range(1<<n):
        y=ap(x)^x
        if seen[y]: ortho=False;break
        seen[y]=1
    return (True,ortho)

# GF(2)-LA inactive with per-lane pre-rotation in linear reduction
def make_alpha_g(n,red):
    def alpha(v):
        return (((v<<1)&((1<<n)-1))^(red if (v>>(n-1)) else 0))
    return alpha
def gf2_rank(cols):
    basis=[]
    for v in cols:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return len(basis)
def inactive_dim(n,w,red,sigma,P,rho,R):
    alpha=make_alpha_g(n,red); m=(1<<n)-1
    def apow(v,k):
        for _ in range(k): v=alpha(v)
        return v
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def words(s): return [(s>>(i*n))&m for i in range(w)]
    def pack(ws):
        s=0
        for i,x in enumerate(ws): s|=(x&m)<<(i*n)
        return s
    def Lin(s):
        ws=words(s)
        for (ln,k) in sigma: ws[ln]=apow(ws[ln],k)
        return pack([ws[P[i]] for i in range(w)])
    def redsum(s):
        ws=words(s); r=0
        for i in range(w): r^=rotl(ws[i],rho[i])   # per-lane pre-rotation, XOR (GF2 proxy)
        return r
    N=n*w; cols=[]
    for k in range(N):
        col=0; cur=1<<k
        for r in range(R):
            col|=redsum(cur)<<(r*n); cur=Lin(cur)
        cols.append(col)
    return N-gf2_rank(cols)

if __name__=="__main__":
    random.seed(11)
    print("== FINAL w=8 roundtrip (distinct ρ, σ=α^1,3,5,7 on lanes 0,2,4,6) ==")
    print(f"  rho32={RHO32}  beta={BETA}  eps={EPS}  sig={SIG}")
    b8 =roundtrip(8, 8,[r%8 for r in RHO32],BETA%8,EPS,SIG,0x1D,PPI,40000)
    b16=roundtrip(16,8,[r%16 for r in RHO32],BETA%16,EPS,SIG,0x2B,PPI,40000)
    print(f"  n=8 : mismatches={b8}/40000")
    print(f"  n=16: mismatches={b16}/40000")
    print()
    print("== σ α-mult orthomorphism(⊕) check (exhaustive n) ==")
    for n,red in [(8,0x1D),(16,0x2B)]:
        for k in [1,3,5,7]:
            P,O=sigma_ortho(n,red,k)
            print(f"  n={n} α^{k} (red=0x{red:X}): perm={P} ortho⊕={O}")
    print()
    print("== GF(2)-LA inactive depth WITH distinct per-lane pre-rotation ρ ==")
    Rstar=None
    for R in range(1,13):
        d=inactive_dim(32,8,0x400007,SIG,PPI,RHO32,R)
        tag=""
        if d==0 and Rstar is None: Rstar=R; tag="  <- R*"
        print(f"  R={R:2d}: dim(inactive)={d:4d}{tag}")
        if d==0: break
    print(f"  => GF(2)-LA R* (with per-lane ρ) = {Rstar}")
