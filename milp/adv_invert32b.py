import random

def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n
        return ((x<<k)|(x>>(n-k)))&m if k else x&m
    def rotr(x,k): return rotl(x,(n-(k%n))%n)
    return m,rotl,rotr

def alpha_mat(n,red):
    cols=[]
    for k in range(n):
        x=1<<k; top=(x>>(n-1))&1
        cols.append(((x<<1)&((1<<n)-1))^(red if top else 0))
    return cols
def applym(cols,x,n):
    y=0
    for k in range(n):
        if (x>>k)&1: y^=cols[k]
    return y&((1<<n)-1)
def matmul(A,B,n): return [applym(A,B[j],n) for j in range(n)]
def matpow(A,e,n):
    R=[1<<j for j in range(n)]; base=A
    while e:
        if e&1: R=matmul(base,R,n)
        base=matmul(base,base,n); e>>=1
    return R

def make_F(n):
    m,rotl,_=mk(n); pp=[(7%n,17%n),(3%n,21%n),(9%n,29%n)]
    def F(s):
        acc=s
        for a,b in pp: acc^=rotl(s,a)&rotl(s,b)
        return acc&m
    return F

def build(n,w,rho,beta,eps,sigma,red,P,RC):
    m,rotl,rotr=mk(n); F=make_F(n); M=m
    A=alpha_mat(n,red)
    order=(1<<n)-1
    sig_fwd={}; sig_inv={}
    for (ln,k) in sigma:
        sig_fwd[ln]=matpow(A,k,n)
        sig_inv[ln]=matpow(A,(order-k)%order,n)  # alpha^{-k}
    def rnd(state,r):
        st=list(state); st[r%w]^=RC[r%len(RC)]
        u=[rotl(st[i],rho[i]) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*u[i])%(1<<n)
        t=F(S)
        v=[(u[i]+t)&M for i in range(w)]
        y=[rotr(v[i],beta) for i in range(w)]
        for ln,mat in sig_fwd.items(): y[ln]=applym(mat,y[ln],n)
        return tuple(y[P[i]] for i in range(w))
    def rinv(state,r):
        y=[0]*w
        for i in range(w): y[P[i]]=state[i]
        for ln,mat in sig_inv.items(): y[ln]=applym(mat,y[ln],n)
        v=[rotl(y[i],beta) for i in range(w)]
        S=0
        for i in range(w): S=(S+eps[i]*v[i])%(1<<n)
        t=F(S)
        u=[(v[i]-t)&M for i in range(w)]
        st=[rotr(u[i],rho[i]) for i in range(w)]
        st[r%w]^=RC[r%len(RC)]
        return tuple(st)
    return rnd,rinv,M

random.seed(999)
PI=[7,4,1,6,3,0,5,2]; rho8=[8]*8
configs=[
    ("sigma{0,4}=a1,a3", [(0,1),(4,3)]),
    ("sigma all k=1..8", [(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7),(7,8)]),
]
eps=[1,-1,1,-1,1,-1,1,-1]
print("=== invertibility: full n=32 w=8 roundtrip (matrix alpha^-1) ===", flush=True)
for name,sig in configs:
    RC=[random.randint(0,(1<<32)-1) for _ in range(64)]
    rnd,rinv,M=build(32,8,rho8,9,eps,sig,0x400007,PI,RC)
    bad=0; ex=None
    for _ in range(30000):
        st=tuple(random.randint(0,M) for _ in range(8)); r=random.randint(0,200)
        if rinv(rnd(st,r),r)!=st:
            bad+=1
            if ex is None: ex=(st,r)
    print(f"  {name}: 30000 single-round roundtrips, mismatches={bad} ex={ex}", flush=True)
    bad=0
    for _ in range(10000):
        st=tuple(random.randint(0,M) for _ in range(8)); cur=st
        for r in range(6): cur=rnd(cur,r)
        for r in range(5,-1,-1): cur=rinv(cur,r)
        if cur!=st: bad+=1
    print(f"  {name}: 10000 6-round roundtrips, mismatches={bad}", flush=True)
