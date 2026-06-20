#!/usr/bin/env python3
"""
GF(2)-LA가 보고한 'inactive' 차분이 *실제 (additive) 라운드*에서도 prob-1 inactive인가?
가설: 아니다. GF(2)-LA의 ⊕-sum 비활성 차분은 ⊞-reduction에서 carry로 깨져
       실제 통과확률 << 1. (그래서 GF(2)-LA R*=9는 무관한 proxy.)
작은 n=8,w=8 은 state 2^64 전수 불가 → 무작위 표본으로 통과확률(prob) 측정.
구체적으로: GF(2)-LA의 비활성 부분공간 기저(R=1) 차분 하나를 골라,
random x 다수에 대해 'ΔS_additive=0' 비율 측정.
"""
import random
def mk(n):
    m=(1<<n)-1
    def rotl(x,k):
        k%=n; return ((x<<k)|(x>>(n-k)))&m if k else x&m
    return m,rotl
def make_alpha_g(n,red):
    def alpha(v): return (((v<<1)&((1<<n)-1))^(red if (v>>(n-1)) else 0))
    return alpha
def gf2_basis(cols):
    basis=[]
    for v in cols:
        cur=v
        for b in basis: cur=min(cur,cur^b)
        if cur: basis.append(cur); basis.sort(reverse=True)
    return basis

RHO32=[0,5,11,17,23,3,13,29]; EPS=[1,-1,1,-1,1,-1,1,-1]
PPI=[7,4,1,6,3,0,5,2]; SIG=[(0,1),(2,3),(4,5),(6,7)]

def find_inactive_delta(n,w,red,sigma,P,rho,R):
    """return one nonzero delta in the GF(2)-LA inactive subspace at depth R (kernel of cols map)."""
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
        for i in range(w): r^=rotl(ws[i],rho[i])
        return r
    N=n*w
    # Build matrix rows = output bits (R*n), columns = input bits (N). Solve for kernel via
    # representing as: for each input basis e_k -> image vector; find nonzero v with M v =0.
    # M is (R*n) x N over GF2. Compute kernel by Gaussian elimination on rows.
    # image of e_k:
    img=[]
    for k in range(N):
        col=0; cur=1<<k
        for r in range(R):
            col|=redsum(cur)<<(r*n); cur=Lin(cur)
        img.append(col)   # column vector (R*n bits) for input bit k
    # kernel: find x (N bits) with XOR_k x_k * img[k] = 0
    # set up basis of input space, reduce.
    rows=R*n
    # represent each input bit by (img[k], onehot k). reduce by img to find combos giving 0.
    red_basis=[]  # list of (imgval, inputmask)
    kernel=[]
    for k in range(N):
        iv=img[k]; im=1<<k
        for (bv,bm) in red_basis:
            if (iv ^ bv) < iv:
                iv^=bv; im^=bm
        if iv==0:
            kernel.append(im)  # nonzero input combo with zero image
        else:
            red_basis.append((iv,im)); red_basis.sort(reverse=True)
    return kernel  # list of input-bit masks (each is an inactive delta)

def additive_pass_prob(n,w,rho,eps,delta,trials=20000):
    m,rotl=mk(n)
    def Sval(state):
        s=0
        for i in range(w): s=(s+eps[i]*rotl(state[i],rho[i]))%(1<<n)
        return s
    D=[(delta>>(i*n))&m for i in range(w)]
    cnt=0
    for _ in range(trials):
        x=[random.randint(0,m) for _ in range(w)]
        xd=[x[i]^D[i] for i in range(w)]
        if Sval(xd)==Sval(x): cnt+=1
    return cnt/trials

if __name__=="__main__":
    random.seed(5)
    n,w=32,8
    ker=find_inactive_delta(n,w,0x400007,SIG,PPI,RHO32,1)
    print(f"GF(2)-LA inactive subspace (R=1) dim={len(ker)} (XOR-sum proxy)")
    print("실제 additive reduction에서 이 '비활성' 차분들의 prob-1 통과확률 측정:")
    rho8=[r%n for r in RHO32]
    shown=0
    for km in ker[:8]:
        p=additive_pass_prob(n,w,rho8,EPS,km,trials=20000)
        print(f"  delta(GF2-inactive)=0x{km:016X}...  additive ΔS=0 prob = {p:.5f}")
        shown+=1
    # also a TRUE additive-inactive delta for contrast: delta on a +/- pair with SAME rho => cancels
    # find two lanes i,j with eps opposite and rho equal? rho all distinct so none cancel trivially.
    # Construct delta that IS additive-inactive: need eps_i rotl(d_i,rho_i)+eps_j rotl(d_j,rho_j)=0 ∀x... hard.
    print()
    print("대조: ⊕-broadcast(구 σ-GLM)이었다면 같은 차분이 prob=1.0 이었음(carry 없음).")
